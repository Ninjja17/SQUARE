"""Core Control Agent — governance layer that validates, prunes, and promotes agents."""
from __future__ import annotations

import logging

from app.config import get_settings
from app.db.chroma_client import add_agent_to_registry
from app.models.schemas import (
    AgentResponse,
    AgentStatusEnum,
    GovernanceAgentResult,
    GovernanceReport,
    SimulationResult,
    SimulationStatusEnum,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Human oversight recommendations by agent type
OVERSIGHT_RECOMMENDATIONS = {
    "Decision": "Require human approval for decisions above confidence threshold 0.85",
    "Risk": "Human review required for risk scores above 70",
    "Verification": "Spot-check 10% of automated verifications monthly",
}
DEFAULT_OVERSIGHT = "Quarterly performance audit recommended"


async def run_governance_check(
    workflow_id: str,
    agents: list[AgentResponse],
    simulation_results: list[SimulationResult],
) -> GovernanceReport:
    """
    For each agent:
      - Mark as created + healthy (health check)
      - If simulation shows >2 critical/warning scenarios → Dismiss
      - If agent type is generic and new → Promote to Registry
      - Otherwise → Keep
      - Generate human oversight recommendation and LLM justification
    """
    critical_or_warning_count = sum(
        1 for r in simulation_results
        if r.status in (SimulationStatusEnum.CRITICAL, SimulationStatusEnum.WARNING)
    )

    GENERIC_TYPES = {"Communication", "Planner", "Risk", "Verification", "Analyzer"}

    results: list[GovernanceAgentResult] = []
    kept = dismissed = promoted = 0

    for agent in agents:
        created = True
        healthy = agent.metrics.uptime >= 0.99

        # Determine human oversight recommendation
        oversight = OVERSIGHT_RECOMMENDATIONS.get(agent.agent_type.value, DEFAULT_OVERSIGHT)

        # Determine decision — smarter dismiss using simulation results
        if not healthy:
            decision = "Dismiss"
            dismissed += 1
            updated_status = AgentStatusEnum.DISMISSED
        elif critical_or_warning_count > 2:
            decision = "Dismiss"
            healthy = False  # mark unhealthy — simulation scenarios indicate poor performance
            dismissed += 1
            updated_status = AgentStatusEnum.DISMISSED
        elif agent.agent_type.value in GENERIC_TYPES and agent.source.value == "new":
            decision = "Promote to Registry"
            promoted += 1
            updated_status = AgentStatusEnum.PROMOTED
            if not settings.DEMO_MODE:
                add_agent_to_registry(agent.agent_type.value, agent.responsibility, [])
        else:
            decision = "Keep"
            kept += 1
            updated_status = AgentStatusEnum.HEALTHY

        # Generate LLM justification if not in demo mode
        justification = ""
        if not settings.DEMO_MODE:
            justification = await _get_llm_justification(agent, decision, simulation_results)

        results.append(
            GovernanceAgentResult(
                agent_id=agent.agent_id,
                agent_name=f"{agent.agent_type.value} Agent",
                created=created,
                healthy=healthy,
                decision=decision + (f" — {justification}" if justification else ""),
                human_oversight_recommendation=oversight,
            )
        )

    summary = (
        f"{kept} agent(s) kept, "
        f"{dismissed} agent(s) dismissed for speed/accuracy, "
        f"{promoted} agent(s) promoted to Common Agent Registry for future reuse."
    )

    return GovernanceReport(
        workflow_id=workflow_id,
        agents=results,
        summary=summary,
    )


async def _get_llm_justification(
    agent: AgentResponse,
    decision: str,
    simulation_results: list[SimulationResult],
) -> str:
    try:
        from app.services.watsonx_client import call_granite_json
        from app.prompts.templates import GOVERNANCE_JUSTIFICATION_SYSTEM, GOVERNANCE_JUSTIFICATION_USER

        sim_summary = "; ".join(
            f"{r.scenario.value}: {r.status.value} ({r.success_rate:.0%})"
            for r in simulation_results
        )
        user_prompt = GOVERNANCE_JUSTIFICATION_USER.format(
            agent_name=f"{agent.agent_type.value} Agent",
            agent_type=agent.agent_type.value,
            responsibility=agent.responsibility,
            decision=decision,
            sim_summary=sim_summary,
        )
        data = call_granite_json(GOVERNANCE_JUSTIFICATION_SYSTEM, user_prompt)
        return data.get("justification", "")
    except Exception as exc:
        logger.warning("LLM justification failed for %s: %s", agent.agent_id, exc)
        return ""
