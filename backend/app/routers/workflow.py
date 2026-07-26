"""Workflow router — POST /api/workflow/analyze, GET /api/workflow/{id}."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.models.schemas import WorkflowRequest, WorkflowResponse
from app.services.workflow_engine import analyze_workflow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workflow", tags=["workflow"])

# In-memory cache keyed by workflow_id (sufficient for hackathon; replace with Redis in prod)
_cache: dict[str, dict] = {}


@router.post("/analyze", response_model=WorkflowResponse, status_code=status.HTTP_200_OK)
async def analyze(req: WorkflowRequest, request: Request):
    session_id = getattr(request.state, "session_id", "anon")
    result = await analyze_workflow(
        industry=req.industry.value,
        monthly_volume=req.monthly_volume,
        description=req.description,
    )
    _cache[result.workflow_id] = result.model_dump(mode="json")
    logger.info("Workflow analyzed: %s (session=%s)", result.workflow_id, session_id)
    return result


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str):
    if workflow_id not in _cache:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return WorkflowResponse(**_cache[workflow_id])
