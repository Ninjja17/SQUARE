"""ROI router — POST /api/roi/analyze."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.schemas import AgentResponse, ROIReport
from app.routers.agents import _agent_cache
from app.routers.workflow import _cache as _workflow_cache
from app.services.roi_engine import analyze_roi

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/roi", tags=["roi"])

_roi_cache: dict[str, dict] = {}


class ROIRequest(BaseModel):
    workflow_id: str


@router.post("/analyze", response_model=ROIReport)
async def roi_analyze(req: ROIRequest):
    wf = _workflow_cache.get(req.workflow_id)
    agents_raw = _agent_cache.get(req.workflow_id)

    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if not agents_raw:
        raise HTTPException(status_code=404, detail="Agents not found")

    agents = [AgentResponse(**a).model_dump() for a in agents_raw]

    report = await analyze_roi(
        workflow_id=req.workflow_id,
        industry=wf["industry"],
        monthly_volume=wf["monthly_volume"],
        agents=agents,
    )
    _roi_cache[req.workflow_id] = report.model_dump(mode="json")
    return report
