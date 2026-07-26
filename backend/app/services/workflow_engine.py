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
        from app.services.watsonx_client import call_granite_json

        user_prompt = WORKFLOW_UNDERSTANDING_USER.format(
            industry=industry,
            volume=monthly_volume,
            workflow_description=description,
        )
        data = call_granite_json(WORKFLOW_UNDERSTANDING_SYSTEM, user_prompt)

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
