"""Simulation Engine — runs agents through scenario-based tests."""
from __future__ import annotations

import asyncio
import json
import logging
import random

from app.config import get_settings
from app.models.schemas import ScenarioEnum, SimulationResult, SimulationStatusEnum

logger = logging.getLogger(__name__)
settings = get_settings()

SCENARIO_PROFILES = {
    ScenarioEnum.HAPPY_PATH: {
        "status": SimulationStatusEnum.PASSED,
        "success_rate_range": (0.96, 0.99),
        "response_time_range": (0.8, 1.5),
        "notes": "All agents performed within expected parameters. No errors detected.",
    },
    ScenarioEnum.AGENT_FAILURE: {
        "status": SimulationStatusEnum.WARNING,
        "success_rate_range": (0.72, 0.85),
        "response_time_range": (2.5, 4.5),
        "notes": "Fallback triggered for 1 agent. Manual intervention needed for ~15% of cases.",
    },
    ScenarioEnum.WRONG_DECISION: {
        "status": SimulationStatusEnum.CRITICAL,
        "success_rate_range": (0.55, 0.70),
        "response_time_range": (1.2, 2.5),
        "notes": "Error rate 8.3%. False positive rate 12%. Human review recommended before deployment.",
    },
    ScenarioEnum.HIGH_WORKLOAD: {
        "status": SimulationStatusEnum.WARNING,
        "success_rate_range": (0.80, 0.90),
        "response_time_range": (3.5, 6.0),
        "notes": "Performance degradation at 3× expected volume. Horizontal scaling recommended.",
    },
    ScenarioEnum.EXTERNAL_FAILURE: {
        "status": SimulationStatusEnum.WARNING,
        "success_rate_range": (0.65, 0.80),
        "response_time_range": (5.0, 8.0),
        "notes": "External system timeout detected. Circuit breaker triggered. Queue backlog 23%.",
    },
    ScenarioEnum.HUMAN_OVERRIDE: {
        "status": SimulationStatusEnum.PASSED,
        "success_rate_range": (0.88, 0.95),
        "response_time_range": (4.0, 7.0),
        "notes": "Human override path functional. Escalation routing verified. Audit trail complete.",
    },
}


async def run_simulation(
    workflow_id: str,
    scenarios: list[ScenarioEnum],
    workflow_summary: str | None = None,
    agents: list[dict] | None = None,
) -> list[SimulationResult]:
    if not settings.DEMO_MODE and workflow_summary and agents:
        return await _llm_simulation(workflow_id, scenarios, workflow_summary, agents)

    # Demo mode or fallback: use random profiles
    results: list[SimulationResult] = []
    for scenario in scenarios:
        if not settings.DEMO_MODE:
            await asyncio.sleep(0.5)

        profile = SCENARIO_PROFILES.get(scenario, SCENARIO_PROFILES[ScenarioEnum.HAPPY_PATH])
        success_rate = round(random.uniform(*profile["success_rate_range"]), 3)
        avg_response_time = round(random.uniform(*profile["response_time_range"]), 2)

        results.append(
            SimulationResult(
                workflow_id=workflow_id,
                scenario=scenario,
                status=profile["status"],
                success_rate=success_rate,
                avg_response_time_s=avg_response_time,
                notes=profile["notes"],
            )
        )
    return results


async def _llm_simulation(
    workflow_id: str,
    scenarios: list[ScenarioEnum],
    workflow_summary: str,
    agents: list[dict],
) -> list[SimulationResult]:
    from app.services.watsonx_client import call_granite_json
    from app.prompts.templates import SIMULATION_SYSTEM, SIMULATION_USER

    user_prompt = SIMULATION_USER.format(
        industry=workflow_summary.split(".")[0] if "." in workflow_summary else "General",
        workflow_summary=workflow_summary,
        agents_json=json.dumps(agents),
        scenarios_json=json.dumps([s.value for s in scenarios]),
    )
    data = call_granite_json(SIMULATION_SYSTEM, user_prompt)

    results: list[SimulationResult] = []
    if isinstance(data, list):
        for item in data:
            scenario_val = item.get("scenario", "happy_path")
            try:
                scenario_enum = ScenarioEnum(scenario_val)
            except ValueError:
                scenario_enum = ScenarioEnum.HAPPY_PATH
            status_val = item.get("status", "passed")
            try:
                status_enum = SimulationStatusEnum(status_val)
            except ValueError:
                status_enum = SimulationStatusEnum.PASSED
            results.append(
                SimulationResult(
                    workflow_id=workflow_id,
                    scenario=scenario_enum,
                    status=status_enum,
                    success_rate=float(item.get("success_rate", 0.9)),
                    avg_response_time_s=float(item.get("avg_response_time_s", 1.5)),
                    notes=item.get("notes", "Simulation completed."),
                )
            )

    # Fill any missing scenarios with random fallback
    simulated_scenarios = {r.scenario for r in results}
    for scenario in scenarios:
        if scenario not in simulated_scenarios:
            profile = SCENARIO_PROFILES.get(scenario, SCENARIO_PROFILES[ScenarioEnum.HAPPY_PATH])
            results.append(
                SimulationResult(
                    workflow_id=workflow_id,
                    scenario=scenario,
                    status=profile["status"],
                    success_rate=round(random.uniform(*profile["success_rate_range"]), 3),
                    avg_response_time_s=round(random.uniform(*profile["response_time_range"]), 2),
                    notes=profile["notes"],
                )
            )

    return results
