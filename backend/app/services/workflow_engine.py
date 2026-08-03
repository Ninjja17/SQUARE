"""Workflow Understanding Engine — calls Groq (Llama 3.3 70B) to parse a raw workflow description."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from app.models.schemas import AutomationCandidate, Task, WorkflowResponse
from app.prompts.templates import WORKFLOW_UNDERSTANDING_SYSTEM, WORKFLOW_UNDERSTANDING_USER

logger = logging.getLogger(__name__)

# ── Fallback: dynamically parse the user's description into structured data ───
def _build_dynamic_fallback_workflow(industry: str, description: str) -> dict:
    raw_lines = [s.strip() for s in description.replace('\n', '.').split('.') if s.strip()]
    tasks = []
    candidates = []
    fallback_tasks = [
        {"name": "Data Intake", "description": "Receive and log incoming data or documents", "actor": f"{industry} Staff"},
        {"name": "Verification", "description": "Check data accuracy and completeness", "actor": "Verification Officer"},
        {"name": "Processing", "description": "Apply business rules and process the request", "actor": f"{industry} Specialist"},
        {"name": "Approval", "description": "Review and approve/reject the processed request", "actor": "Manager"},
        {"name": "Notification", "description": "Inform stakeholders of the outcome", "actor": "Admin Staff"},
    ]
    for i, line in enumerate(raw_lines[:6]):
        task_name = f"Step {i+1}: {line[:30]}..." if len(line) > 30 else line
        tasks.append({"name": task_name, "description": line, "actor": f"{industry} Specialist"})
        if i % 2 == 1 or any(w in line.lower() for w in ["verify", "check", "review", "send", "confirm", "update"]):
            candidates.append({"task_name": task_name, "reason": "Rule-based repetitive task suitable for agent automation"})

    return {
        "tasks": tasks or fallback_tasks,
        "stakeholders": [f"{industry} Customer", f"{industry} Admin", "Verification Officer", "Operations Lead"],
        "automation_candidates": candidates or [
            {"task_name": "Verification", "reason": "Rule-based, high volume, error-prone when manual"},
            {"task_name": "Notification", "reason": "Template-driven, suitable for Communication Agent"},
        ],
        "current_bottlenecks": [
            f"Manual processing delays in {industry} workflow",
            "High labor hours spent on manual document/data verification",
            "Lack of real-time status tracking for end users",
        ],
    }


# ── All agent types that may be required by a standard SQUARE workflow ────────
_WORKFLOW_AGENT_TYPES = [
    "Analyzer",
    "Verification",
    "Decision",
    "Communication",
    "Risk",
    "Planner",
]


async def analyze_workflow(
    industry: str,
    monthly_volume: int,
    description: str,
    workflow_id: str | None = None,
    tenant_id: str | None = None,
) -> WorkflowResponse:
    wf_id = workflow_id or str(uuid.uuid4())
    t_id  = tenant_id or str(uuid.uuid4())

    try:
        from app.services.watsonx_client import call_granite_json

        user_prompt = WORKFLOW_UNDERSTANDING_USER.format(
            industry=industry,
            volume=monthly_volume,
            workflow_description=description,
        )
        data = call_granite_json(WORKFLOW_UNDERSTANDING_SYSTEM, user_prompt)
    except Exception as exc:
        logger.warning("Groq AI workflow call failed (%s), using dynamic parsed fallback", exc)
        data = _build_dynamic_fallback_workflow(industry, description)

    # ── Ensure required Orchestrate skills exist before returning ──────────────
    try:
        from app.services.orchestrate_client import ensure_workflow_agent_skills
        ensure_workflow_agent_skills(_WORKFLOW_AGENT_TYPES)
    except RuntimeError as exc:
        logger.warning(
            "Orchestrate auth failed during workflow-time skill ensure: %s — workflow proceeds without skill guarantee",
            exc,
        )
    except Exception as exc:
        logger.warning("Orchestrate workflow-time skill ensure skipped: %s", exc)

    return WorkflowResponse(
        workflow_id=wf_id,
        tenant_id=t_id,
        industry=industry,
        monthly_volume=monthly_volume,
        description=description,
        tasks=[Task(**t) for t in data.get("tasks", [])],
        stakeholders=data.get("stakeholders", []),
        automation_candidates=[AutomationCandidate(**c) for c in data.get("automation_candidates", [])],
        current_bottlenecks=data.get("current_bottlenecks", []),
        created_at=datetime.utcnow(),
    )
