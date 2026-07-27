"""Workflow Understanding Engine — calls Granite to parse a raw workflow description."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from app.config import get_settings
from app.models.schemas import AutomationCandidate, Task, WorkflowResponse
from app.prompts.templates import WORKFLOW_UNDERSTANDING_SYSTEM, WORKFLOW_UNDERSTANDING_USER

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── Mock data for DEMO_MODE ──────────────────────────────────────────────────
MOCK_WORKFLOW = {
    "tasks": [
        {"name": "Application Submission", "description": "Student submits application form online", "actor": "Applicant"},
        {"name": "Document Collection", "description": "Collect required documents (transcripts, ID)", "actor": "Admin Staff"},
        {"name": "Document Verification", "description": "Verify authenticity of submitted documents", "actor": "Verification Officer"},
        {"name": "Fee Payment", "description": "Student pays application fee", "actor": "Finance Dept"},
        {"name": "Admission Review", "description": "Panel reviews verified application", "actor": "Admissions Committee"},
        {"name": "Decision & Notification", "description": "Send acceptance or rejection letter", "actor": "Admin Staff"},
    ],
    "stakeholders": ["Applicant", "Admin Staff", "Verification Officer", "Finance Dept", "Admissions Committee"],
    "automation_candidates": [
        {"task_name": "Document Verification", "reason": "Rule-based, high volume, error-prone when manual"},
        {"task_name": "Fee Payment", "reason": "Already digital, can be fully automated with payment gateway"},
        {"task_name": "Decision & Notification", "reason": "Template-driven, suitable for Communication Agent"},
    ],
    "current_bottlenecks": [
        "Manual document verification creates 3–5 day delay",
        "High admin workload during peak admission season",
        "Inconsistent verification outcomes between officers",
    ],
}


def _build_dynamic_fallback_workflow(industry: str, description: str) -> dict:
    raw_lines = [s.strip() for s in description.replace('\n', '.').split('.') if s.strip()]
    tasks = []
    candidates = []
    for i, line in enumerate(raw_lines[:6]):
        task_name = f"Step {i+1}: {line[:30]}..." if len(line) > 30 else line
        tasks.append({"name": task_name, "description": line, "actor": f"{industry} Specialist"})
        if i % 2 == 1 or any(w in line.lower() for w in ["verify", "check", "review", "send", "confirm", "update"]):
            candidates.append({"task_name": task_name, "reason": "Rule-based repetitive task suitable for agent automation"})

    if not tasks:
        tasks = MOCK_WORKFLOW["tasks"]
    if not candidates:
        candidates = MOCK_WORKFLOW["automation_candidates"]

    return {
        "tasks": tasks,
        "stakeholders": [f"{industry} Customer", f"{industry} Admin", "Verification Officer", "Operations Lead"],
        "automation_candidates": candidates,
        "current_bottlenecks": [
            f"Manual processing delays in {industry} workflow",
            "High labor hours spent on manual document/data verification",
            "Lack of real-time status tracking for end users",
        ],
    }


async def analyze_workflow(
    industry: str,
    monthly_volume: int,
    description: str,
    workflow_id: str | None = None,
    tenant_id: str | None = None,
) -> WorkflowResponse:
    wf_id = workflow_id or str(uuid.uuid4())
    t_id = tenant_id or str(uuid.uuid4())

    if settings.DEMO_MODE:
        data = MOCK_WORKFLOW
    else:
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

