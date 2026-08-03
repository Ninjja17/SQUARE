"""Governance router — POST /api/governance/check."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.schemas import AgentResponse, GovernanceReport, SimulationResult
from app.routers.agents import _agent_cache
from app.routers.simulate import _sim_cache
from app.services.core_control_agent import run_governance_check

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/governance", tags=["governance"])

_gov_cache: dict[str, dict] = {}
# Stores Orchestrate registration results keyed by workflow_id
_orchestrate_cache: dict[str, list[dict]] = {}


class GovernanceRequest(BaseModel):
    workflow_id: str


@router.post("/check", response_model=GovernanceReport)
async def check(req: GovernanceRequest):
    agents_raw = _agent_cache.get(req.workflow_id)
    sim_raw = _sim_cache.get(req.workflow_id)

    if not agents_raw:
        raise HTTPException(status_code=404, detail="Agents not found — run /api/agents/generate first")
    if not sim_raw:
        raise HTTPException(status_code=404, detail="Simulation results not found — run /api/simulate/run first")

    agents = [AgentResponse(**a) for a in agents_raw]
    sim_results = [SimulationResult(**s) for s in sim_raw]

    report = await run_governance_check(
        workflow_id=req.workflow_id,
        agents=agents,
        simulation_results=sim_results,
    )
    _gov_cache[req.workflow_id] = report.model_dump(mode="json")

    # ── Register kept/promoted agents as Orchestrate skills (non-blocking) ──
    # Build agent dicts enriched with governance decisions for the batch call.
    # decision field contains only the strict enum value (Keep | Dismiss | Promote to Registry).
    gov_by_id = {ga.agent_id: ga.decision for ga in report.agents}
    agents_for_reg = []
    for a in agents:
        raw_decision = gov_by_id.get(a.agent_id, "Keep")
        # Guard: strip any legacy " — explanation" suffix so batch registration
        # can do a reliable string comparison against "Dismiss".
        bare_decision = raw_decision.split(" — ")[0].strip()
        agents_for_reg.append({
            "agent_id":       a.agent_id,
            "agent_type":     a.agent_type.value,
            "responsibility":  a.responsibility,
            "metrics":        a.metrics.model_dump(),
            "decision":       bare_decision,
        })

    def _register():
        from app.services.orchestrate_client import register_agents_batch
        results = register_agents_batch(agents_for_reg, req.workflow_id)
        _orchestrate_cache[req.workflow_id] = results

    # Run in a thread so it never blocks the HTTP response
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _register)

    return report


@router.get("/{workflow_id}/orchestrate")
async def get_orchestrate_registrations(workflow_id: str):
    """Return Orchestrate skill registration results for a workflow."""
    results = _orchestrate_cache.get(workflow_id)
    if results is None:
        raise HTTPException(status_code=404, detail="No Orchestrate registration data yet — run /check first")
    return {"workflow_id": workflow_id, "registrations": results}
