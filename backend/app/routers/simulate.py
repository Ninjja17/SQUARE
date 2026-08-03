"""Simulation router — POST /api/simulate/run, POST /api/simulate/narrative."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.models.schemas import ScenarioEnum, SimulationRequest, SimulationResult
from app.routers.agents import _agent_cache
from app.routers.workflow import _cache as _workflow_cache
from app.services.simulation_engine import run_simulation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/simulate", tags=["simulation"])

_sim_cache: dict[str, list[dict]] = {}

SCENARIO_DESCRIPTIONS = {
    "happy_path": "All agents perform under normal conditions with expected input",
    "agent_failure": "One agent goes down mid-processing — test fallback and recovery",
    "wrong_decision": "Decision Agent produces an incorrect output — test error handling",
    "high_workload": "3× expected monthly volume hits all agents simultaneously",
    "external_failure": "Downstream API or database becomes unavailable",
    "human_override": "Human operator manually escalates and overrides agent decision",
}


class NarrativeRequest(BaseModel):
    workflow_id: str
    scenario: ScenarioEnum


@router.post("/run", response_model=list[SimulationResult])
async def simulate(req: SimulationRequest):
    if req.workflow_id not in _agent_cache:
        from app.services.agent_generation import generate_agents
        logger.info("Agents missing for %s in simulate/run, auto-generating agents", req.workflow_id)
        agents_objs = await generate_agents(req.workflow_id, [])
        _agent_cache[req.workflow_id] = [a.model_dump(mode="json") for a in agents_objs]

    scenarios = req.scenarios if req.scenarios else [ScenarioEnum.HAPPY_PATH]

    # Build context for LLM-powered simulation
    wf = _workflow_cache.get(req.workflow_id)
    workflow_summary = None
    agents = None
    if wf:
        workflow_summary = f"Industry: {wf.get('industry', 'Other')}. Description: {wf.get('description', '')[:500]}"
        agents_raw = _agent_cache.get(req.workflow_id, [])
        agents = [{"agent_type": a.get("agent_type"), "responsibility": a.get("responsibility")} for a in agents_raw]

    results = await run_simulation(
        workflow_id=req.workflow_id,
        scenarios=scenarios,
        workflow_summary=workflow_summary,
        agents=agents,
    )
    _sim_cache[req.workflow_id] = [r.model_dump(mode="json") for r in results]
    return results


@router.post("/narrative")
async def simulate_narrative(req: NarrativeRequest):
    """Generate a detailed agent interaction narrative for a specific scenario."""
    wf = _workflow_cache.get(req.workflow_id)
    if not wf:
        wf = {
            "workflow_id": req.workflow_id,
            "industry": "General",
            "monthly_volume": 500,
            "description": "Enterprise Automated Workflow",
        }
        _workflow_cache[req.workflow_id] = wf

    agents_raw = _agent_cache.get(req.workflow_id)
    if not agents_raw:
        from app.services.agent_generation import generate_agents
        agents_objs = await generate_agents(req.workflow_id, [])
        agents_raw = [a.model_dump(mode="json") for a in agents_objs]
        _agent_cache[req.workflow_id] = agents_raw

    workflow_summary = f"Industry: {wf.get('industry', 'Other')}. Description: {wf.get('description', '')[:500]}"
    agents = [{"agent_type": a.get("agent_type"), "responsibility": a.get("responsibility")} for a in agents_raw]
    scenario_desc = SCENARIO_DESCRIPTIONS.get(req.scenario.value, "Standard scenario")

    fallback_narrative = {
        "timeline": [
            {"timestamp": "00:00.0s", "agent": "Verification", "action": "Receives incoming document", "status": "processing", "detail": "Document payload received", "target_agent": None},
            {"timestamp": "00:00.3s", "agent": "Verification", "action": "Extracts key fields via OCR", "status": "processing", "detail": "Identifiers & data fields extracted", "target_agent": None},
            {"timestamp": "00:01.1s", "agent": "Verification", "action": "Validates against verification rules", "status": "success", "detail": "Document authenticity verified", "target_agent": "Decision"},
            {"timestamp": "00:01.4s", "agent": "Decision", "action": "Receives verification result", "status": "processing", "detail": "All checks passed, confidence score 0.94", "target_agent": None},
            {"timestamp": "00:01.8s", "agent": "Decision", "action": "Approves transaction request", "status": "success", "detail": "Auto-approved: confidence > 0.85 threshold", "target_agent": "Planner"},
            {"timestamp": "00:02.1s", "agent": "Planner", "action": "Calculates execution schedule", "status": "processing", "detail": "Determining execution window", "target_agent": None},
            {"timestamp": "00:02.8s", "agent": "Planner", "action": "Selects optimal execution plan", "status": "success", "detail": "Execution plan finalized", "target_agent": "Communication"},
            {"timestamp": "00:03.0s", "agent": "Communication", "action": "Generates status notification", "status": "processing", "detail": "Notification template prepared", "target_agent": None},
            {"timestamp": "00:03.4s", "agent": "Communication", "action": "Sends notification to recipient", "status": "success", "detail": "Status notification dispatched successfully", "target_agent": None},
        ],
        "outcome": f"Scenario {req.scenario.value} completed — agents processed workflow steps smoothly in 3.4 seconds.",
        "total_time": "3.4s",
    }

    try:
        from app.services.watsonx_client import call_granite_json
        from app.prompts.templates import SIMULATION_NARRATIVE_SYSTEM, SIMULATION_NARRATIVE_USER

        user_prompt = SIMULATION_NARRATIVE_USER.format(
            workflow_summary=workflow_summary,
            agents_json=json.dumps(agents),
            scenario_name=req.scenario.value.replace("_", " ").title(),
            scenario_description=scenario_desc,
        )
        data = call_granite_json(SIMULATION_NARRATIVE_SYSTEM, user_prompt)
        return data
    except Exception as exc:
        logger.warning("Groq AI simulation narrative call failed (%s), using structured fallback narrative", exc)
        return fallback_narrative
