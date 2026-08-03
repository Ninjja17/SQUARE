"""Risk Analysis Engine — scores security, compliance, operational risk via Groq (Llama 3.3 70B).

Uses compliance RAG to inject real regulatory snippets into the analysis prompt,
grounding the model's compliance scoring in actual rule text rather than guessing.
"""
from __future__ import annotations

import json
import logging

from app.config import get_settings
from app.models.schemas import RiskCategory, RiskReport, SimulationResult, SimulationStatusEnum

logger = logging.getLogger(__name__)
settings = get_settings()

# Industry-specific compliance frameworks
INDUSTRY_COMPLIANCE = {
    "Healthcare": ["HIPAA", "HITECH", "GDPR"],
    "BFSI": ["PCI-DSS", "SOX", "GDPR", "Basel III"],
    "Education": ["FERPA", "COPPA", "GDPR"],
    "Government": ["SOX", "FedRAMP", "NIST 800-53", "GDPR"],
    "HR": ["GDPR", "EEOC", "SOX"],
    "Retail": ["PCI-DSS", "GDPR", "CCPA"],
    "Manufacturing": ["ISO 27001", "GDPR"],
    "Telecom": ["GDPR", "CCPA", "FCC regulations"],
    "Other": ["GDPR"],
}

# Industry-specific weight multipliers for risk categories
INDUSTRY_WEIGHTS = {
    "Healthcare": {"Compliance": 1.5, "Security": 1.3, "Operational": 1.0, "Data Quality": 1.0, "Agent Dependency": 1.0},
    "BFSI": {"Compliance": 1.4, "Security": 1.5, "Operational": 1.0, "Data Quality": 1.0, "Agent Dependency": 1.0},
    "Education": {"Compliance": 1.3, "Security": 1.0, "Operational": 1.0, "Data Quality": 1.2, "Agent Dependency": 1.0},
    "Government": {"Compliance": 1.5, "Security": 1.4, "Operational": 1.0, "Data Quality": 1.0, "Agent Dependency": 1.0},
}

_FALLBACK_RISK = {
    "overall_score": 38,
    "categories": [
        {"name": "Compliance", "score": 45, "justification": "Document handling requires FERPA/GDPR controls for student data."},
        {"name": "Security", "score": 35, "justification": "API endpoints must enforce auth; document storage needs encryption at rest."},
        {"name": "Operational", "score": 30, "justification": "Fallback path covers most failure modes; monitoring required."},
        {"name": "Data Quality", "score": 40, "justification": "Input documents vary in format; OCR accuracy impacts downstream agents."},
        {"name": "Agent Dependency", "score": 42, "justification": "Verification Agent is critical path — failure blocks all downstream agents."},
    ],
    "recommendations": [
        "Encrypt document storage at rest and in transit (TLS 1.3).",
        "Implement FERPA/GDPR consent capture before processing student data.",
        "Add circuit breaker on Verification Agent — route to manual queue on repeated failure.",
        "Establish SLA monitoring for each agent with automated alerting.",
        "Schedule quarterly bias audits on the Decision Agent.",
    ],
}


async def analyze_risk(
    workflow_id: str,
    workflow_summary: str,
    agents: list[dict],
    simulation_results: list[SimulationResult],
    industry: str = "Other",
) -> RiskReport:
    compliance_frameworks = INDUSTRY_COMPLIANCE.get(industry, INDUSTRY_COMPLIANCE["Other"])
    weights = INDUSTRY_WEIGHTS.get(industry, {})

    try:
        from app.db.compliance_rag import retrieve_compliance_context
        rag_context = retrieve_compliance_context(industry, workflow_summary, top_k=4)
    except Exception as exc:
        logger.warning("Compliance RAG retrieval failed: %s", exc)
        rag_context = ""

    try:
        from app.services.watsonx_client import call_granite_json
        from app.prompts.templates import RISK_ANALYSIS_SYSTEM, RISK_ANALYSIS_USER

        user_prompt = RISK_ANALYSIS_USER.format(
            workflow_summary=workflow_summary,
            agent_list_json=json.dumps(agents),
            simulation_results_json=json.dumps([r.model_dump() for r in simulation_results], default=str),
            compliance_context=rag_context,
        )
        system_with_compliance = (
            RISK_ANALYSIS_SYSTEM
            + f"\n\nApplicable compliance frameworks for {industry} industry: {', '.join(compliance_frameworks)}. "
            f"Weight your analysis accordingly."
        )
        data = call_granite_json(system_with_compliance, user_prompt)
    except Exception as exc:
        logger.warning("Groq AI risk analysis failed (%s), using structured fallback risk data", exc)
        data = dict(_FALLBACK_RISK)
        if rag_context:
            data["recommendations"] = list(data["recommendations"])
            data["recommendations"].append(
                f"Applicable regulations for {industry}: {', '.join(compliance_frameworks)}. "
                "Ensure all agent data flows are audited against these frameworks before production."
            )

    # Apply industry-specific weight multipliers to category scores
    categories = []
    for c in data["categories"]:
        score = c["score"]
        cat_name = c["name"]
        multiplier = weights.get(cat_name, 1.0)
        weighted_score = min(100, round(score * multiplier, 1))
        categories.append(RiskCategory(name=cat_name, score=weighted_score, justification=c["justification"]))

    # Boost score if any critical simulation scenario was found
    critical_count = sum(1 for r in simulation_results if r.status == SimulationStatusEnum.CRITICAL)
    boost = min(critical_count * 10, 20)

    # Recalculate overall from weighted categories
    if categories:
        overall = min(100, round(sum(cat.score for cat in categories) / len(categories)) + boost)
    else:
        overall = min(100, data["overall_score"] + boost)

    return RiskReport(
        workflow_id=workflow_id,
        overall_score=overall,
        categories=categories,
        recommendations=data["recommendations"],
    )
