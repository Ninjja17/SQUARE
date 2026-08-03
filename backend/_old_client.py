"""
IBM watsonx Orchestrate integration ΓÇö registers generated SQUARE agents as Orchestrate skills.

On governance completion (when an agent is "Kept" or "Promoted"), this service
fires a non-blocking registration call to Orchestrate so the agent becomes
immediately usable inside any Orchestrate-powered digital employee.

References:
  - https://developer.ibm.com/tutorials/awb-use-rest-api-with-ibm-watsonx-orchestrate/
  - Orchestrate REST API: POST /v1/skills

If ORCHESTRATE_INSTANCE_URL or ORCHESTRATE_API_KEY are not set, calls are
gracefully skipped and a clear warning is logged ΓÇö the rest of the pipeline
continues normally.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ΓöÇΓöÇ Skill schema helpers ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

_AGENT_DESCRIPTIONS = {
    "Analyzer":      "Analyzes business workflows and extracts structured insights from unstructured input.",
    "Verification":  "Validates documents, records, and data quality against defined business rules.",
    "Decision":      "Makes accept, reject, or approve recommendations based on verified workflow data.",
    "Communication": "Sends notifications, status updates, and manages user interactions across channels.",
    "Risk":          "Identifies operational, compliance, and security risks in automated workflows.",
    "Planner":       "Generates phased rollout strategies and implementation plans for AI deployments.",
}

_AGENT_PARAMETERS = {
    "Analyzer": {
        "input": {"type": "string", "description": "Unstructured workflow description or business process text"},
    },
    "Verification": {
        "document_data": {"type": "string", "description": "Document content or reference to validate"},
        "rules": {"type": "string", "description": "Validation rules to apply (JSON or plain text)"},
    },
    "Decision": {
        "application_data": {"type": "string", "description": "Structured data for the decision"},
        "threshold": {"type": "number", "description": "Confidence threshold for approval (0.0ΓÇô1.0)"},
    },
    "Communication": {
        "recipient": {"type": "string", "description": "Email address or user ID"},
        "message": {"type": "string", "description": "Notification message content"},
        "channel": {"type": "string", "description": "Delivery channel: email, sms, webhook"},
    },
    "Risk": {
        "workflow_summary": {"type": "string", "description": "Workflow description and agent list to assess"},
        "industry": {"type": "string", "description": "Industry sector for compliance framework selection"},
    },
    "Planner": {
        "risk_score": {"type": "number", "description": "Overall risk score (0ΓÇô100)"},
        "roi_percent": {"type": "number", "description": "Projected Year 1 ROI"},
        "industry": {"type": "string", "description": "Target industry for the rollout plan"},
    },
}


def _build_skill_payload(
    agent_id: str,
    agent_type: str,
    responsibility: str,
    accuracy: float,
    workflow_id: str,
) -> dict[str, Any]:
    """Build an Orchestrate-compatible skill registration payload."""
    parameters = _AGENT_PARAMETERS.get(agent_type, {
        "input": {"type": "string", "description": "Task input data"},
    })
    return {
        "name": f"square_{agent_type.lower()}_{agent_id[:8]}",
        "display_name": f"SQUARE {agent_type} Agent",
        "description": (
            f"{_AGENT_DESCRIPTIONS.get(agent_type, responsibility)} "
            f"(Registered from SQUARE workflow {workflow_id[:8]}, accuracy {accuracy*100:.0f}%)"
        ),
        "type": "custom",
        "version": "1.0.0",
        "tags": ["square", "ai-agent", agent_type.lower(), "auto-generated"],
        "metadata": {
            "source": "SQUARE",
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "agent_type": agent_type,
            "accuracy": accuracy,
            "registered_at": datetime.utcnow().isoformat() + "Z",
        },
        "input": {
            "type": "object",
            "properties": {p: {"type": v["type"], "description": v["description"]}
                          for p, v in parameters.items()},
            "required": list(parameters.keys()),
        },
        "output": {
            "type": "object",
            "properties": {
                "result": {"type": "string", "description": "Agent output / decision"},
                "confidence": {"type": "number", "description": "Confidence score 0.0ΓÇô1.0"},
                "metadata": {"type": "object", "description": "Additional output metadata"},
            },
        },
    }


def _get_iam_token() -> str:
    """Exchange IBM Cloud API key for a short-lived IAM bearer token."""
    url = "https://iam.cloud.ibm.com/identity/token"
    data = f"grant_type=urn%3Aibm%3Aparams%3Aoauth%3Agrant-type%3Aapikey&apikey={settings.ORCHESTRATE_API_KEY}"
    req = urllib.request.Request(
        url,
        data=data.encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode())
    return body["access_token"]


def _post_skill(payload: dict, token: str) -> dict:
    """POST the skill payload to Orchestrate's /v1/skills endpoint."""
    url = f"{settings.ORCHESTRATE_INSTANCE_URL.rstrip('/')}/v1/skills"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        raise RuntimeError(f"Orchestrate returned {exc.code}: {body}") from exc


# ΓöÇΓöÇ Public API ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

def register_agent_as_skill(
    agent_id: str,
    agent_type: str,
    responsibility: str,
    accuracy: float,
    workflow_id: str,
) -> dict[str, Any]:
    """
    Register a single SQUARE agent as an IBM watsonx Orchestrate skill.

    Returns a result dict with keys:
      - registered (bool)  ΓÇö whether the call succeeded
      - skill_id (str)     ΓÇö Orchestrate skill ID if registered
      - message (str)      ΓÇö human-readable outcome
    """
    if not settings.ORCHESTRATE_INSTANCE_URL or not settings.ORCHESTRATE_API_KEY:
        msg = (
            "Orchestrate not configured (ORCHESTRATE_INSTANCE_URL / ORCHESTRATE_API_KEY missing). "
            f"Agent '{agent_type}' ({agent_id[:8]}) would be registered as skill "
            f"'square_{agent_type.lower()}_{agent_id[:8]}' when credentials are provided."
        )
        logger.warning(msg)
        return {
            "registered": False,
            "skill_id": None,
            "message": msg,
        }

    try:
        payload = _build_skill_payload(agent_id, agent_type, responsibility, accuracy, workflow_id)
        token   = _get_iam_token()
        result  = _post_skill(payload, token)
        skill_id = result.get("id") or result.get("skill_id", "unknown")
        logger.info(
            "Orchestrate skill registered: %s ΓåÆ skill_id=%s",
            payload["name"], skill_id,
        )
        return {
            "registered": True,
            "skill_id": skill_id,
            "message": f"Registered as Orchestrate skill '{payload['name']}' (id={skill_id})",
        }
    except Exception as exc:
        logger.error("Orchestrate skill registration failed for %s: %s", agent_id, exc)
        return {
            "registered": False,
            "skill_id": None,
            "message": f"Registration failed: {exc}",
        }


def register_agents_batch(
    agents: list[dict],
    workflow_id: str,
) -> list[dict]:
    """
    Register multiple agents at once.
    Only registers agents with decision 'Keep' or 'Promote to Registry'.
    Returns a list of registration result dicts (one per agent).
    """
    results = []
    for agent in agents:
        decision = agent.get("decision", "Keep")
        if decision == "Dismiss":
            results.append({
                "agent_id": agent.get("agent_id", ""),
                "agent_type": agent.get("agent_type", ""),
                "registered": False,
                "skill_id": None,
                "message": "Skipped ΓÇö agent was dismissed by Core Control Agent",
            })
            continue

        reg = register_agent_as_skill(
            agent_id=agent.get("agent_id", ""),
            agent_type=agent.get("agent_type", ""),
            responsibility=agent.get("responsibility", ""),
            accuracy=agent.get("metrics", {}).get("accuracy", 0.90),
            workflow_id=workflow_id,
        )
        reg["agent_id"]   = agent.get("agent_id", "")
        reg["agent_type"] = agent.get("agent_type", "")
        results.append(reg)

    registered = sum(1 for r in results if r["registered"])
    logger.info(
        "Orchestrate batch registration complete: %d/%d agents registered for workflow %s",
        registered, len(agents), workflow_id[:8],
    )
    return results
