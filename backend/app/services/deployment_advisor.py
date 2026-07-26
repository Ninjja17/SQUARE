"""Deployment Advisor — produces phased rollout plan and Go/No-Go recommendation."""
from __future__ import annotations

import json
import logging

from app.config import get_settings
from app.models.schemas import (
    DeploymentPhase,
    DeploymentPlan,
    GoNoGoEnum,
    RiskReport,
    ROIReport,
    SimulationResult,
    SimulationStatusEnum,
)

logger = logging.getLogger(__name__)
settings = get_settings()

MOCK_PLAN = {
    "phases": [
        {
            "name": "Phase 1 — Pilot",
            "scope_percent": 10,
            "human_oversight_percent": 80,
            "success_criteria": "Error rate < 2%, zero compliance incidents, all agents healthy for 30 days",
        },
        {
            "name": "Phase 2 — Limited Rollout",
            "scope_percent": 40,
            "human_oversight_percent": 40,
            "success_criteria": "Automation rate > 80%, escalation rate < 10%, SLA met in 95% of cases",
        },
        {
            "name": "Phase 3 — Full Deployment",
            "scope_percent": 100,
            "human_oversight_percent": 10,
            "success_criteria": "Full volume with automated monitoring, quarterly audits, payback period achieved",
        },
    ],
    "go_no_go": "GO",
    "justification": (
        "Risk score is moderate (38/100) and simulation Happy Path passed with >96% success rate. "
        "ROI is compelling (265% Year 1). Recommend phased rollout starting with 10% pilot volume "
        "under 80% human oversight to validate live performance before scaling."
    ),
}


async def generate_deployment_plan(
    workflow_id: str,
    risk_report: RiskReport,
    roi_report: ROIReport,
    simulation_results: list[SimulationResult],
) -> DeploymentPlan:
    if settings.DEMO_MODE:
        data = MOCK_PLAN
    else:
        from app.services.watsonx_client import call_granite_json
        from app.prompts.templates import DEPLOYMENT_ADVISOR_SYSTEM, DEPLOYMENT_ADVISOR_USER

        user_prompt = DEPLOYMENT_ADVISOR_USER.format(
            risk_report_json=json.dumps(risk_report.model_dump()),
            roi_report_json=json.dumps(roi_report.model_dump()),
            simulation_results_json=json.dumps(
                [r.model_dump() for r in simulation_results], default=str
            ),
        )
        data = call_granite_json(DEPLOYMENT_ADVISOR_SYSTEM, user_prompt)

    # Override go_no_go if risk is too high
    has_critical = any(r.status == SimulationStatusEnum.CRITICAL for r in simulation_results)
    if risk_report.overall_score >= 75 or (has_critical and risk_report.overall_score >= 60):
        go_no_go = GoNoGoEnum.NEEDS_CHANGES
    elif risk_report.overall_score >= 50 or has_critical:
        go_no_go = GoNoGoEnum.PILOT_FIRST
    else:
        go_no_go = GoNoGoEnum(data.get("go_no_go", "GO"))

    return DeploymentPlan(
        phases=[DeploymentPhase(**p) for p in data["phases"]],
        go_no_go=go_no_go,
        justification=data["justification"],
    )
