"""Simulation router — POST /api/simulate/run, POST /api/simulate/narrative."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings
from app.models.schemas import ScenarioEnum, SimulationRequest, SimulationResult
from app.routers.agents import _agent_cache
from app.routers.workflow import _cache as _workflow_cache
from app.services.simulation_engine import run_simulation

logger = logging.getLogger(__name__)
settings = get_settings()
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
        raise HTTPException(status_code=404, detail="Agents not generated yet — run /api/agents/generate first")

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
    agents_raw = _agent_cache.get(req.workflow_id)

    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if not agents_raw:
        raise HTTPException(status_code=404, detail="Agents not generated yet")

    workflow_summary = f"Industry: {wf.get('industry', 'Other')}. Description: {wf.get('description', '')[:500]}"
    agents = [{"agent_type": a.get("agent_type"), "responsibility": a.get("responsibility")} for a in agents_raw]
    scenario_desc = SCENARIO_DESCRIPTIONS.get(req.scenario.value, "Standard scenario")

    if settings.DEMO_MODE:
        return {
            "timeline": [
                {"timestamp": "00:00.0s", "agent": "Verification", "action": "Receives incoming document", "status": "processing", "detail": "Patient insurance form received", "target_agent": None},
                {"timestamp": "00:00.3s", "agent": "Verification", "action": "Extracts key fields via OCR", "status": "processing", "detail": "Policy number, patient ID, dates extracted", "target_agent": None},
                {"timestamp": "00:01.1s", "agent": "Verification", "action": "Validates against insurance DB", "status": "success", "detail": "Policy #INS-4832 confirmed active", "target_agent": "Decision"},
                {"timestamp": "00:01.4s", "agent": "Decision", "action": "Receives verification result", "status": "processing", "detail": "All checks passed, confidence 0.94", "target_agent": None},
                {"timestamp": "00:01.8s", "agent": "Decision", "action": "Approves appointment scheduling", "status": "success", "detail": "Auto-approved: confidence > 0.85 threshold", "target_agent": "Planner"},
                {"timestamp": "00:02.1s", "agent": "Planner", "action": "Checks doctor availability", "status": "processing", "detail": "Querying schedule for Dr. Smith, next 5 days", "target_agent": None},
                {"timestamp": "00:02.8s", "agent": "Planner", "action": "Selects optimal slot", "status": "success", "detail": "Slot found: Tue 10:30 AM — matches patient preference", "target_agent": "Communication"},
                {"timestamp": "00:03.0s", "agent": "Communication", "action": "Generates confirmation email", "status": "processing", "detail": "Template: appointment_confirmed_v2", "target_agent": None},
                {"timestamp": "00:03.4s", "agent": "Communication", "action": "Sends notification to patient", "status": "success", "detail": "Email sent to patient@email.com + SMS backup", "target_agent": None},
            ],
            "outcome": "Transaction completed successfully — all 4 agents processed without errors in 3.4 seconds.",
            "total_time": "3.4s",
        }

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
