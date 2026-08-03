"""
IBM watsonx Orchestrate integration — registers generated SQUARE agents as Orchestrate skills.

On governance completion (when an agent is "Kept" or "Promoted"), this service
fires a non-blocking registration call to Orchestrate so the agent becomes
immediately usable inside any Orchestrate-powered digital employee.

References:
  - https://developer.ibm.com/tutorials/awb-use-rest-api-with-ibm-watsonx-orchestrate/
  - Orchestrate REST API: POST /v1/skills

If ORCHESTRATE_INSTANCE_URL or ORCHESTRATE_API_KEY are not set, calls are
gracefully skipped and a clear warning is logged — the rest of the pipeline
continues normally.

Lifecycle metadata policy:
  - Core skills:            lifecycle=core,      core_persistent=True
  - Promoted reusable:      lifecycle=reusable,  reusable_persistent=True
  - Workflow-scoped skills: lifecycle=workflow,  core_persistent=False, reusable_persistent=False

Non-deletion rule:
  can_delete_skill(metadata) returns False when core_persistent or reusable_persistent is True.
  No delete endpoint ever fires for protected skills.
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

# ── Core agent definitions ─────────────────────────────────────────────────────

#: Stable skill names for the 6 required SQUARE core agents.
CORE_SKILL_NAMES: dict[str, str] = {
    "Analyzer":      "square_core_analyzer",
    "Verification":  "square_core_verification",
    "Decision":      "square_core_decision",
    "Communication": "square_core_communication",
    "Risk":          "square_core_risk",
    "Planner":       "square_core_planner",
}

#: Stable agent names for the 6 required SQUARE core agents (Agents API).
#: Orchestrate requires alphanumeric + underscores only — no hyphens.
CORE_AGENT_NAMES: dict[str, str] = {
    "Analyzer":      "square_core_analyzer",
    "Verification":  "square_core_verification",
    "Decision":      "square_core_decision",
    "Communication": "square_core_communication",
    "Risk":          "square_core_risk",
    "Planner":       "square_core_planner",
}

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
        "threshold": {"type": "number", "description": "Confidence threshold for approval (0.0–1.0)"},
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
        "risk_score": {"type": "number", "description": "Overall risk score (0–100)"},
        "roi_percent": {"type": "number", "description": "Projected Year 1 ROI"},
        "industry": {"type": "string", "description": "Target industry for the rollout plan"},
    },
}


# ── Lifecycle / persistence helpers ───────────────────────────────────────────

def _make_metadata(
    agent_type: str,
    agent_id: str,
    workflow_id: str,
    accuracy: float,
    lifecycle: str = "workflow",
) -> dict[str, Any]:
    """Build skill metadata with lifecycle and persistence flags."""
    is_core     = lifecycle == "core"
    is_reusable = lifecycle == "reusable"
    return {
        "source":               "SQUARE",
        "created_by":           "square",
        "workflow_id":          workflow_id,
        "agent_id":             agent_id,
        "agent_type":           agent_type,
        "accuracy":             accuracy,
        "registered_at":        datetime.utcnow().isoformat() + "Z",
        "lifecycle":            lifecycle,           # core | reusable | workflow
        "core_persistent":      is_core,
        "reusable_persistent":  is_reusable,
    }


def can_delete_skill(metadata: dict[str, Any]) -> bool:
    """
    Return True only if the skill is safe to delete.

    Core and reusable skills are protected — this guard must be checked before
    any future delete endpoint is wired up.
    """
    if metadata.get("core_persistent") or metadata.get("reusable_persistent"):
        return False
    return True


# ── Skill schema helpers ───────────────────────────────────────────────────────

def _build_skill_payload(
    agent_id: str,
    agent_type: str,
    responsibility: str,
    accuracy: float,
    workflow_id: str,
    skill_name: str | None = None,
    lifecycle: str = "workflow",
) -> dict[str, Any]:
    """Build an Orchestrate-compatible skill registration payload."""
    parameters = _AGENT_PARAMETERS.get(agent_type, {
        "input": {"type": "string", "description": "Task input data"},
    })
    name = skill_name or f"square_{agent_type.lower()}_{agent_id[:8]}"
    return {
        "name": name,
        "display_name": f"SQUARE {agent_type} Agent",
        "description": (
            f"{_AGENT_DESCRIPTIONS.get(agent_type, responsibility)} "
            f"(Registered from SQUARE workflow {workflow_id[:8]}, accuracy {accuracy*100:.0f}%)"
        ),
        "type": "custom",
        "version": "1.0.0",
        "tags": ["square", "ai-agent", agent_type.lower(), "auto-generated"],
        "metadata": _make_metadata(agent_type, agent_id, workflow_id, accuracy, lifecycle),
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
                "confidence": {"type": "number", "description": "Confidence score 0.0–1.0"},
                "metadata": {"type": "object", "description": "Additional output metadata"},
            },
        },
    }


def _build_core_skill_payload(agent_type: str) -> dict[str, Any]:
    """Build a core-lifecycle payload for one of the 6 core SQUARE agents."""
    from app.db.chroma_client import SEED_AGENTS

    seed = next((a for a in SEED_AGENTS if a["agent_type"] == agent_type), None)
    responsibility = seed["responsibility"] if seed else _AGENT_DESCRIPTIONS.get(agent_type, "")
    accuracy       = seed["accuracy"]       if seed else 0.95

    return _build_skill_payload(
        agent_id=f"core-{agent_type.lower()}",
        agent_type=agent_type,
        responsibility=responsibility,
        accuracy=accuracy,
        workflow_id="core-bootstrap",
        skill_name=CORE_SKILL_NAMES[agent_type],
        lifecycle="core",
    )


# ── Orchestrate HTTP primitives ────────────────────────────────────────────────

def _get_iam_token() -> str:
    """Exchange IBM Cloud API key for a short-lived IAM bearer token."""
    url  = "https://iam.cloud.ibm.com/identity/token"
    data = (
        f"grant_type=urn%3Aibm%3Aparams%3Aoauth%3Agrant-type%3Aapikey"
        f"&apikey={settings.ORCHESTRATE_API_KEY}"
    )
    req = urllib.request.Request(
        url,
        data=data.encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode())
    return body["access_token"]


def _list_skills(token: str) -> list[dict]:
    """GET /v1/skills — return the raw list of skill objects."""
    url = f"{settings.ORCHESTRATE_INSTANCE_URL.rstrip('/')}/v1/skills"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
        # Orchestrate may return {"skills": [...]} or a bare list
        if isinstance(body, list):
            return body
        return body.get("skills") or body.get("items") or []
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        raise RuntimeError(f"Orchestrate list-skills returned {exc.code}: {body}") from exc


def _find_skill_by_name(name: str, token: str) -> dict | None:
    """Return the first skill whose `name` field matches exactly, or None."""
    skills = _list_skills(token)
    for skill in skills:
        if skill.get("name") == name:
            return skill
    return None


def _post_skill(payload: dict, token: str) -> dict:
    """POST the skill payload to Orchestrate's /v1/skills endpoint."""
    url  = f"{settings.ORCHESTRATE_INSTANCE_URL.rstrip('/')}/v1/skills"
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url, data=data,
        headers={
            "Content-Type":  "application/json",
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


# ── Upsert / ensure helpers ────────────────────────────────────────────────────

def ensure_skill_exists(name: str, payload: dict, token: str) -> dict[str, Any]:
    """
    Idempotent skill creation.

    Returns::
        {
            "status":   "already_exists" | "created" | "failed",
            "skill_id": str | None,
            "message":  str,
        }
    """
    try:
        existing = _find_skill_by_name(name, token)
        if existing:
            skill_id = existing.get("id") or existing.get("skill_id", "unknown")
            logger.debug("Orchestrate skill already exists: %s (id=%s)", name, skill_id)
            return {
                "status":   "already_exists",
                "skill_id": skill_id,
                "message":  f"Skill '{name}' already present in Orchestrate (id={skill_id})",
            }
        result   = _post_skill(payload, token)
        skill_id = result.get("id") or result.get("skill_id", "unknown")
        logger.info("Orchestrate skill created: %s → id=%s", name, skill_id)
        return {
            "status":   "created",
            "skill_id": skill_id,
            "message":  f"Skill '{name}' created in Orchestrate (id={skill_id})",
        }
    except Exception as exc:
        logger.error("ensure_skill_exists failed for '%s': %s", name, exc)
        return {
            "status":   "failed",
            "skill_id": None,
            "message":  f"Failed to ensure skill '{name}': {exc}",
        }


# ── Core bootstrap ─────────────────────────────────────────────────────────────

def bootstrap_core_skills() -> list[dict[str, Any]]:
    """
    Ensure all 6 SQUARE core skills exist in Orchestrate.

    Returns one result dict per core agent type::
        {
            "agent_type": str,
            "skill_name": str,
            "status":     "created" | "already_exists" | "failed" | "skipped",
            "skill_id":   str | None,
            "message":    str,
        }
    """
    if not settings.ORCHESTRATE_INSTANCE_URL or not settings.ORCHESTRATE_API_KEY:
        msg = (
            "Orchestrate not configured (ORCHESTRATE_INSTANCE_URL / ORCHESTRATE_API_KEY missing). "
            "Core bootstrap skipped."
        )
        logger.warning(msg)
        return [
            {
                "agent_type": agent_type,
                "skill_name": skill_name,
                "status":     "skipped",
                "skill_id":   None,
                "message":    msg,
            }
            for agent_type, skill_name in CORE_SKILL_NAMES.items()
        ]

    results: list[dict] = []
    try:
        token = _get_iam_token()
    except Exception as exc:
        error_msg = f"Orchestrate auth failed: {exc}"
        logger.error(error_msg)
        return [
            {
                "agent_type": agent_type,
                "skill_name": skill_name,
                "status":     "failed",
                "skill_id":   None,
                "message":    error_msg,
            }
            for agent_type, skill_name in CORE_SKILL_NAMES.items()
        ]

    for agent_type, skill_name in CORE_SKILL_NAMES.items():
        payload = _build_core_skill_payload(agent_type)
        outcome = ensure_skill_exists(skill_name, payload, token)
        results.append({
            "agent_type": agent_type,
            "skill_name": skill_name,
            "status":     outcome["status"],
            "skill_id":   outcome["skill_id"],
            "message":    outcome["message"],
        })

    created  = sum(1 for r in results if r["status"] == "created")
    existing = sum(1 for r in results if r["status"] == "already_exists")
    logger.info(
        "Core bootstrap complete: %d created, %d already existed, %d total",
        created, existing, len(results),
    )
    return results


def get_core_status() -> list[dict[str, Any]]:
    """
    Check which of the 6 core skills are currently present in Orchestrate.

    Returns one status dict per core agent type::
        {
            "agent_type": str,
            "skill_name": str,
            "present":    bool,
            "skill_id":   str | None,
            "message":    str,
        }
    """
    if not settings.ORCHESTRATE_INSTANCE_URL or not settings.ORCHESTRATE_API_KEY:
        return [
            {
                "agent_type": agent_type,
                "skill_name": skill_name,
                "present":    False,
                "skill_id":   None,
                "message":    "Orchestrate not configured",
            }
            for agent_type, skill_name in CORE_SKILL_NAMES.items()
        ]

    try:
        token  = _get_iam_token()
        skills = _list_skills(token)
    except Exception as exc:
        error_msg = f"Orchestrate auth/list failed: {exc}"
        logger.error(error_msg)
        return [
            {
                "agent_type": agent_type,
                "skill_name": skill_name,
                "present":    False,
                "skill_id":   None,
                "message":    error_msg,
            }
            for agent_type, skill_name in CORE_SKILL_NAMES.items()
        ]

    by_name = {s.get("name"): s for s in skills}
    results = []
    for agent_type, skill_name in CORE_SKILL_NAMES.items():
        existing = by_name.get(skill_name)
        if existing:
            skill_id = existing.get("id") or existing.get("skill_id", "unknown")
            results.append({
                "agent_type": agent_type,
                "skill_name": skill_name,
                "present":    True,
                "skill_id":   skill_id,
                "message":    f"Present in Orchestrate (id={skill_id})",
            })
        else:
            results.append({
                "agent_type": agent_type,
                "skill_name": skill_name,
                "present":    False,
                "skill_id":   None,
                "message":    "Not found in Orchestrate",
            })
    return results


# ── Core Agents bootstrap (Agents API) ────────────────────────────────────────

def _build_core_agent_payload(agent_type: str) -> dict[str, Any]:
    """Build a stable core agent creation payload for one of the 6 SQUARE core agents."""
    from app.db.chroma_client import SEED_AGENTS

    seed = next((a for a in SEED_AGENTS if a["agent_type"] == agent_type), None)
    responsibility = seed["responsibility"] if seed else _AGENT_DESCRIPTIONS.get(agent_type, "")
    accuracy       = seed["accuracy"]       if seed else 0.95

    agent_name = CORE_AGENT_NAMES[agent_type]
    instructions = (
        f"You are the SQUARE {agent_type} Agent — a core, persistent AI agent for the "
        f"SQUARE Enterprise Agent Engineering Platform. "
        f"Your primary responsibility: {responsibility}. "
        f"You operate across all enterprise workflows with a target accuracy of {accuracy*100:.0f}%. "
        f"Always apply enterprise compliance, governance, and data-handling standards. "
        f"Never expose sensitive user data. Follow the SQUARE agent protocol at all times."
    )
    return {
        "name":          agent_name,
        "display_name":  f"SQUARE {agent_type} Agent",
        "description":   (
            f"{_AGENT_DESCRIPTIONS.get(agent_type, responsibility)} "
            f"Core persistent agent — lifecycle: core, registered by SQUARE bootstrap."
        ),
        "instructions":  instructions,
        # Orchestrate Agents API requires style field; use default
        "style":         "default",
        # Orchestrate requires its own model identifier format
        "llm":           "groq/openai/gpt-oss-120b",
        "tools":         [],
        "collaborators": [],
        "knowledge_base": [],
    }


def _list_orchestrate_agents(token: str) -> list[dict]:
    """GET /v1/orchestrate/agents — return the raw list of agent objects."""
    url = f"{settings.ORCHESTRATE_INSTANCE_URL.rstrip('/')}/v1/orchestrate/agents"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
        if isinstance(body, list):
            return body
        return body.get("agents") or body.get("items") or []
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        raise RuntimeError(f"Orchestrate list-agents returned {exc.code}: {body}") from exc


def _find_orchestrate_agent_by_name(name: str, token: str) -> dict | None:
    """Return the first agent whose `name` field matches exactly, or None."""
    agents = _list_orchestrate_agents(token)
    for agent in agents:
        if agent.get("name") == name:
            return agent
    return None


def _ensure_orchestrate_agent_exists(name: str, payload: dict, token: str) -> dict[str, Any]:
    """
    Idempotent agent creation via the Orchestrate Agents API.

    Returns::
        {
            "status":               "already_exists" | "created" | "failed",
            "orchestrate_agent_id": str | None,
            "message":              str,
        }
    """
    try:
        existing = _find_orchestrate_agent_by_name(name, token)
        if existing:
            agent_id = existing.get("id") or existing.get("agent_id", "unknown")
            logger.debug("Orchestrate agent already exists: %s (id=%s)", name, agent_id)
            return {
                "status":               "already_exists",
                "orchestrate_agent_id": agent_id,
                "message":              f"Agent '{name}' already present in Orchestrate (id={agent_id})",
            }
        result   = _post_orchestrate_agent(payload, token)
        agent_id = result.get("id") or result.get("agent_id", "unknown")
        logger.info("Orchestrate agent created: %s → id=%s", name, agent_id)
        return {
            "status":               "created",
            "orchestrate_agent_id": agent_id,
            "message":              f"Agent '{name}' created in Orchestrate (id={agent_id})",
        }
    except Exception as exc:
        logger.error("_ensure_orchestrate_agent_exists failed for '%s': %s", name, exc)
        return {
            "status":               "failed",
            "orchestrate_agent_id": None,
            "message":              f"Failed to ensure agent '{name}': {exc}",
        }


def bootstrap_core_agents() -> list[dict[str, Any]]:
    """
    Ensure all 6 SQUARE core agents exist in Orchestrate as real Agents (not skills).

    Uses the Orchestrate Agents API (POST /v1/orchestrate/agents).
    Idempotent — already-present agents are left untouched (``status: already_exists``).
    Missing agents are created (``status: created``).

    Returns one result dict per core agent type::
        {
            "agent_type":           str,
            "agent_name":           str,
            "status":               "created" | "already_exists" | "failed" | "skipped",
            "orchestrate_agent_id": str | None,
            "message":              str,
        }
    """
    if not settings.ORCHESTRATE_INSTANCE_URL or not settings.ORCHESTRATE_API_KEY:
        msg = (
            "Orchestrate not configured (ORCHESTRATE_INSTANCE_URL / ORCHESTRATE_API_KEY missing). "
            "Core agents bootstrap skipped."
        )
        logger.warning(msg)
        return [
            {
                "agent_type":           agent_type,
                "agent_name":           agent_name,
                "status":               "skipped",
                "orchestrate_agent_id": None,
                "message":              msg,
            }
            for agent_type, agent_name in CORE_AGENT_NAMES.items()
        ]

    results: list[dict] = []
    try:
        token = _get_iam_token()
    except Exception as exc:
        error_msg = f"Orchestrate auth failed: {exc}"
        logger.error(error_msg)
        return [
            {
                "agent_type":           agent_type,
                "agent_name":           agent_name,
                "status":               "failed",
                "orchestrate_agent_id": None,
                "message":              error_msg,
            }
            for agent_type, agent_name in CORE_AGENT_NAMES.items()
        ]

    for agent_type, agent_name in CORE_AGENT_NAMES.items():
        payload = _build_core_agent_payload(agent_type)
        outcome = _ensure_orchestrate_agent_exists(agent_name, payload, token)
        results.append({
            "agent_type":           agent_type,
            "agent_name":           agent_name,
            "status":               outcome["status"],
            "orchestrate_agent_id": outcome["orchestrate_agent_id"],
            "message":              outcome["message"],
        })

    created  = sum(1 for r in results if r["status"] == "created")
    existing = sum(1 for r in results if r["status"] == "already_exists")
    logger.info(
        "Core agents bootstrap complete: %d created, %d already existed, %d total",
        created, existing, len(results),
    )
    return results


def get_core_agents_status() -> list[dict[str, Any]]:
    """
    Check which of the 6 core SQUARE agents are currently present in Orchestrate.

    Returns one status dict per core agent type::
        {
            "agent_type":           str,
            "agent_name":           str,
            "present":              bool,
            "orchestrate_agent_id": str | None,
            "message":              str,
        }
    """
    if not settings.ORCHESTRATE_INSTANCE_URL or not settings.ORCHESTRATE_API_KEY:
        return [
            {
                "agent_type":           agent_type,
                "agent_name":           agent_name,
                "present":              False,
                "orchestrate_agent_id": None,
                "message":              "Orchestrate not configured",
            }
            for agent_type, agent_name in CORE_AGENT_NAMES.items()
        ]

    try:
        token  = _get_iam_token()
        agents = _list_orchestrate_agents(token)
    except Exception as exc:
        error_msg = f"Orchestrate auth/list failed: {exc}"
        logger.error(error_msg)
        return [
            {
                "agent_type":           agent_type,
                "agent_name":           agent_name,
                "present":              False,
                "orchestrate_agent_id": None,
                "message":              error_msg,
            }
            for agent_type, agent_name in CORE_AGENT_NAMES.items()
        ]

    by_name = {a.get("name"): a for a in agents}
    results = []
    for agent_type, agent_name in CORE_AGENT_NAMES.items():
        existing = by_name.get(agent_name)
        if existing:
            agent_id = existing.get("id") or existing.get("agent_id", "unknown")
            results.append({
                "agent_type":           agent_type,
                "agent_name":           agent_name,
                "present":              True,
                "orchestrate_agent_id": agent_id,
                "message":              f"Present in Orchestrate (id={agent_id})",
            })
        else:
            results.append({
                "agent_type":           agent_type,
                "agent_name":           agent_name,
                "present":              False,
                "orchestrate_agent_id": None,
                "message":              "Not found in Orchestrate",
            })
    return results


def ensure_workflow_agent_skills(agent_types: list[str]) -> list[dict[str, Any]]:
    """
    Ensure Orchestrate skills exist for the given agent types before a workflow runs.

    For core agent types this reuses the stable core skill names.
    For non-core types a workflow-scoped skill is created idempotently.

    Returns a list of ensure results (one per type).
    Auth errors raise RuntimeError so callers can surface a clear error response.
    """
    if not settings.ORCHESTRATE_INSTANCE_URL or not settings.ORCHESTRATE_API_KEY:
        logger.warning("Orchestrate not configured — skipping workflow-time skill ensure")
        return []

    token   = _get_iam_token()   # may raise — caller catches and surfaces error
    results = []
    for agent_type in agent_types:
        if agent_type in CORE_SKILL_NAMES:
            skill_name = CORE_SKILL_NAMES[agent_type]
            payload    = _build_core_skill_payload(agent_type)
        else:
            skill_name = f"square_{agent_type.lower()}_workflow"
            payload    = _build_skill_payload(
                agent_id=f"wf-{agent_type.lower()}",
                agent_type=agent_type,
                responsibility=_AGENT_DESCRIPTIONS.get(agent_type, "Custom workflow agent"),
                accuracy=0.90,
                workflow_id="workflow-ensure",
                skill_name=skill_name,
                lifecycle="workflow",
            )
        outcome = ensure_skill_exists(skill_name, payload, token)
        results.append({
            "agent_type": agent_type,
            "skill_name": skill_name,
            **outcome,
        })
    return results


# ── Public API ─────────────────────────────────────────────────────────────────

def register_agent_as_skill(
    agent_id: str,
    agent_type: str,
    responsibility: str,
    accuracy: float,
    workflow_id: str,
    lifecycle: str = "workflow",
) -> dict[str, Any]:
    """
    Register a single SQUARE agent as an IBM watsonx Orchestrate skill.

    Uses upsert semantics — if a skill with the same name already exists it is
    not duplicated.  Promoted (reusable) agents get lifecycle='reusable' so they
    are protected from deletion.

    Returns a result dict with keys:
      - registered (bool)  — whether the call succeeded or already existed
      - skill_id (str)     — Orchestrate skill ID if registered
      - message (str)      — human-readable outcome
      - status  (str)      — "created" | "already_exists" | "failed" | "skipped"
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
            "skill_id":   None,
            "status":     "skipped",
            "message":    msg,
        }

    try:
        # Core agent types always use their stable name; others use instance-scoped names.
        if agent_type in CORE_SKILL_NAMES and lifecycle in ("core", "workflow"):
            skill_name = CORE_SKILL_NAMES[agent_type]
            payload    = _build_core_skill_payload(agent_type)
        else:
            skill_name = f"square_{agent_type.lower()}_{agent_id[:8]}"
            payload    = _build_skill_payload(
                agent_id, agent_type, responsibility, accuracy, workflow_id,
                skill_name=skill_name, lifecycle=lifecycle,
            )

        token   = _get_iam_token()
        outcome = ensure_skill_exists(skill_name, payload, token)
        registered = outcome["status"] in ("created", "already_exists")
        return {
            "registered": registered,
            "skill_id":   outcome["skill_id"],
            "status":     outcome["status"],
            "message":    outcome["message"],
        }
    except Exception as exc:
        logger.error("Orchestrate skill registration failed for %s: %s", agent_id, exc)
        return {
            "registered": False,
            "skill_id":   None,
            "status":     "failed",
            "message":    f"Registration failed: {exc}",
        }


def register_agents_batch(
    agents: list[dict],
    workflow_id: str,
) -> list[dict]:
    """
    Register multiple agents at once using upsert semantics.

    Only registers agents with decision 'Keep' or 'Promote to Registry'.
    Dismissed agents are skipped reliably.
    Returns a list of registration result dicts (one per agent).
    """
    results = []
    for agent in agents:
        decision = agent.get("decision", "Keep")
        # Strict enum check — only the bare decision word is used
        if decision == "Dismiss":
            results.append({
                "agent_id":  agent.get("agent_id", ""),
                "agent_type": agent.get("agent_type", ""),
                "registered": False,
                "skill_id":   None,
                "status":     "skipped",
                "message":    "Skipped — agent was dismissed by Core Control Agent",
            })
            continue

        # Promoted agents get reusable lifecycle so they are never deleted
        lifecycle = "reusable" if decision == "Promote to Registry" else "workflow"

        reg = register_agent_as_skill(
            agent_id=agent.get("agent_id", ""),
            agent_type=agent.get("agent_type", ""),
            responsibility=agent.get("responsibility", ""),
            accuracy=agent.get("metrics", {}).get("accuracy", 0.90),
            workflow_id=workflow_id,
            lifecycle=lifecycle,
        )
        reg["agent_id"]   = agent.get("agent_id", "")
        reg["agent_type"] = agent.get("agent_type", "")
        results.append(reg)

    registered = sum(1 for r in results if r.get("registered"))
    logger.info(
        "Orchestrate batch registration complete: %d/%d agents registered for workflow %s",
        registered, len(agents), workflow_id[:8],
    )
    return results


# ══════════════════════════════════════════════════════════════════════════════
# Orchestrate AGENTS API — POST /v1/orchestrate/agents
# Creates proper AI agents (not skills) with instructions, LLM, and tools.
# ══════════════════════════════════════════════════════════════════════════════

def _build_agent_payload(
    agent_id: str,
    agent_type: str,
    responsibility: str,
    accuracy: float,
    workflow_id: str,
) -> dict[str, Any]:
    """Build an Orchestrate-compatible agent creation payload."""
    name = f"square_{agent_type.lower()}_{agent_id[:8]}"
    instructions = (
        f"You are a SQUARE {agent_type} Agent. "
        f"Your responsibility: {responsibility}. "
        f"You operate within workflow {workflow_id[:8]} with a target accuracy of {accuracy*100:.0f}%. "
        f"Follow enterprise compliance and governance standards at all times."
    )
    return {
        "name":          name,
        "display_name":  f"SQUARE {agent_type} Agent",
        "description":   (
            f"{_AGENT_DESCRIPTIONS.get(agent_type, responsibility)} "
            f"(Auto-generated by SQUARE for workflow {workflow_id[:8]}, "
            f"accuracy {accuracy*100:.0f}%)"
        ),
        "instructions":  instructions,
        # Orchestrate Agents API requires style field; use default
        "style":         "default",
        # Orchestrate requires its own model identifier format
        "llm":           "groq/openai/gpt-oss-120b",
        "tools":         [],
        "collaborators": [],
        "knowledge_base": [],
    }


def _post_orchestrate_agent(payload: dict, token: str) -> dict:
    """POST the agent payload to Orchestrate's /v1/orchestrate/agents endpoint."""
    url = f"{settings.ORCHESTRATE_INSTANCE_URL.rstrip('/')}/v1/orchestrate/agents"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        raise RuntimeError(f"Orchestrate agents API returned {exc.code}: {body}") from exc


def create_orchestrate_agent(
    agent_id: str,
    agent_type: str,
    responsibility: str,
    accuracy: float,
    workflow_id: str,
) -> dict[str, Any]:
    """
    Create a single SQUARE agent in IBM watsonx Orchestrate via the Agents API.

    Returns::
        {
            "created":              bool,
            "orchestrate_agent_id": str | None,
            "status":               "created" | "failed" | "skipped",
            "message":              str,
        }
    """
    if not settings.ORCHESTRATE_INSTANCE_URL or not settings.ORCHESTRATE_API_KEY:
        msg = (
            "Orchestrate not configured (ORCHESTRATE_INSTANCE_URL / ORCHESTRATE_API_KEY missing). "
            f"Agent '{agent_type}' ({agent_id[:8]}) would be created when credentials are provided."
        )
        logger.warning(msg)
        return {
            "created": False,
            "orchestrate_agent_id": None,
            "status": "skipped",
            "message": msg,
        }

    try:
        payload = _build_agent_payload(
            agent_id, agent_type, responsibility, accuracy, workflow_id,
        )
        token = _get_iam_token()
        result = _post_orchestrate_agent(payload, token)
        orch_agent_id = result.get("id") or result.get("agent_id", "unknown")
        logger.info(
            "Orchestrate agent created: %s %s → id=%s",
            agent_type, agent_id[:8], orch_agent_id,
        )
        return {
            "created": True,
            "orchestrate_agent_id": orch_agent_id,
            "status": "created",
            "message": f"Agent '{agent_type}' created in Orchestrate (id={orch_agent_id})",
        }
    except Exception as exc:
        logger.error("Orchestrate agent creation failed for %s %s: %s", agent_type, agent_id[:8], exc)
        return {
            "created": False,
            "orchestrate_agent_id": None,
            "status": "failed",
            "message": f"Agent creation failed: {exc}",
        }


def create_agents_batch(
    agents: list[dict],
    workflow_id: str,
) -> list[dict]:
    """
    Create multiple agents in WatsonX Orchestrate via the Agents API.

    Each dict in `agents` should have keys:
        agent_id, agent_type, responsibility, metrics (with accuracy key).

    Returns a list of creation result dicts (one per agent).
    """
    results = []
    for agent in agents:
        res = create_orchestrate_agent(
            agent_id=agent.get("agent_id", ""),
            agent_type=agent.get("agent_type", ""),
            responsibility=agent.get("responsibility", ""),
            accuracy=agent.get("metrics", {}).get("accuracy", 0.90),
            workflow_id=workflow_id,
        )
        res["agent_id"] = agent.get("agent_id", "")
        res["agent_type"] = agent.get("agent_type", "")
        results.append(res)

    created = sum(1 for r in results if r.get("created"))
    logger.info(
        "Orchestrate agents batch: %d/%d agents created for workflow %s",
        created, len(agents), workflow_id[:8],
    )
    return results

