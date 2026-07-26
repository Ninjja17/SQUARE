"""Risk router — POST /api/risk/analyze."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.schemas import AgentResponse, RiskReport, SimulationResult
from app.routers.agents import _agent_cache
from app.routers.simulate import _sim_cache
from app.routers.workflow import _cache as _workflow_cache
from app.services.risk_engine import analyze_risk

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/risk", tags=["risk"])

_risk_cache: dict[str, dict] = {}


class RiskRequest(BaseModel):
    workflow_id: str


@router.post("/analyze", response_model=RiskReport)
async def risk_analyze(req: RiskRequest):
    wf = _workflow_cache.get(req.workflow_id)
    agents_raw = _agent_cache.get(req.workflow_id)
    sim_raw = _sim_cache.get(req.workflow_id)

    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if not agents_raw:
        raise HTTPException(status_code=404, detail="Agents not found")
    if not sim_raw:
        raise HTTPException(status_code=404, detail="Simulation results not found")

    agents = [AgentResponse(**a).model_dump() for a in agents_raw]
    sim_results = [SimulationResult(**s) for s in sim_raw]
    workflow_summary = f"Industry: {wf['industry']}. Description: {wf['description'][:500]}"

    report = await analyze_risk(
        workflow_id=req.workflow_id,
        workflow_summary=workflow_summary,
        agents=agents,
        simulation_results=sim_results,
        industry=wf.get("industry", "Other"),
    )
    _risk_cache[req.workflow_id] = report.model_dump(mode="json")
    return report
