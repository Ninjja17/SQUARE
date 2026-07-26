"""Agents router — POST /api/agents/generate, GET /api/agents/{workflow_id}."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.models.schemas import AgentResponse
from app.routers.workflow import _cache as _workflow_cache
from app.services.agent_generation import generate_agents

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])

_agent_cache: dict[str, list[dict]] = {}


class GenerateRequest(BaseModel):
    workflow_id: str


@router.post("/generate", response_model=list[AgentResponse])
async def generate(req: GenerateRequest):
    wf = _workflow_cache.get(req.workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found — analyze it first")

    agents = await generate_agents(
        workflow_id=req.workflow_id,
        automation_candidates=wf.get("automation_candidates", []),
    )
    _agent_cache[req.workflow_id] = [a.model_dump(mode="json") for a in agents]
    return agents


@router.get("/{workflow_id}", response_model=list[AgentResponse])
async def get_agents(workflow_id: str):
    if workflow_id not in _agent_cache:
        raise HTTPException(status_code=404, detail="Agents not generated yet")
    return [AgentResponse(**a) for a in _agent_cache[workflow_id]]
