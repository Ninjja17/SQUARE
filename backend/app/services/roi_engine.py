"""ROI Analysis Engine — estimates savings, cost, payback via Granite."""
from __future__ import annotations

import json
import logging

from app.config import get_settings
from app.models.schemas import ROIReport

logger = logging.getLogger(__name__)
settings = get_settings()

MOCK_ROI = {
    "annual_savings": 480000,
    "implementation_cost": 120000,
    "ai_infra_cost_per_year": 36000,
    "fte_reduction": 4.5,
    "payback_period_months": 5.4,
    "roi_percent_year1": 265,
    "assumptions": [
        "Baseline: 3 FTE @ $40k/year for document verification and notifications.",
        "Agent handles 85% of volume autonomously; 15% escalated to human review.",
        "watsonx.ai API cost estimated at $3,000/month at current volume.",
        "Implementation includes 4 weeks of integration work at $30k.",
        "Year 1 ROI excludes soft benefits (faster admissions cycle, applicant satisfaction).",
    ],
}


async def analyze_roi(
    workflow_id: str,
    industry: str,
    monthly_volume: int,
    agents: list[dict],
) -> ROIReport:
    if settings.DEMO_MODE:
        data = MOCK_ROI
    else:
        from app.services.watsonx_client import call_granite_json
        from app.prompts.templates import ROI_ANALYSIS_SYSTEM, ROI_ANALYSIS_USER

        # Rough manual cost estimate: varies by industry
        manual_cost_map = {
            "Education": 12,
            "BFSI": 18,
            "Healthcare": 22,
            "HR": 10,
            "Manufacturing": 8,
            "Telecom": 14,
            "Retail": 6,
            "Government": 15,
            "Other": 12,
        }
        manual_cost = manual_cost_map.get(industry, 12)

        user_prompt = ROI_ANALYSIS_USER.format(
            industry=industry,
            volume=monthly_volume,
            manual_cost_estimate=manual_cost,
            agent_list_json=json.dumps(agents),
        )
        data = call_granite_json(ROI_ANALYSIS_SYSTEM, user_prompt)

    roi = data["roi_percent_year1"]
    payback = data["payback_period_months"]

    sensitivity = {
        "best_case": {"roi_percent": round(roi * 1.3, 1), "payback_months": round(payback * 0.7, 1)},
        "expected": {"roi_percent": round(roi, 1), "payback_months": round(payback, 1)},
        "worst_case": {"roi_percent": round(roi * 0.6, 1), "payback_months": round(payback * 1.5, 1)},
    }

    return ROIReport(
        workflow_id=workflow_id,
        annual_savings=data["annual_savings"],
        implementation_cost=data["implementation_cost"],
        ai_infra_cost_per_year=data["ai_infra_cost_per_year"],
        fte_reduction=data["fte_reduction"],
        payback_period_months=payback,
        roi_percent_year1=roi,
        assumptions=data.get("assumptions", []),
        sensitivity=sensitivity,
    )
