"""Governance router — POST /api/governance/check."""
from __future__ import annotations

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
    return report
