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
        wf = {
            "workflow_id": req.workflow_id,
            "industry": "General",
            "monthly_volume": 500,
            "description": "Enterprise Automated Workflow",
            "automation_candidates": [
                {"task_name": "Document & Data Verification", "reason": "Rule-based repetitive task"},
                {"task_name": "Decision & Approval Recommendation", "reason": "Rule-based decision task"},
                {"task_name": "Status Notification & Communication", "reason": "Templated notification task"},
            ],
        }
        _workflow_cache[req.workflow_id] = wf

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


@router.get("/{workflow_id}/graph")
async def get_agent_graph(workflow_id: str):
    """
    Return a Mermaid diagram definition showing agent handoff dependencies.
    The graph encodes:
      - Input node → each agent in order
      - Agent → agent handoffs (sequential pipeline)
      - Final agent → Output node
      - Source badges (reused / new) as subgraph annotations
    """
    if workflow_id not in _agent_cache:
        raise HTTPException(status_code=404, detail="Agents not generated yet")

    agents = _agent_cache[workflow_id]
    if not agents:
        return {"mermaid": "graph LR\n  A[No agents]"}

    # Node id sanitiser
    def nid(i: int, agent_type: str) -> str:
        return f"A{i}_{agent_type.replace(' ', '_')}"

    lines = ["graph LR"]
    lines.append('  classDef reused fill:#1a1a1a,stroke:#555,color:#aaa;')
    lines.append('  classDef new    fill:#0a0a0a,stroke:#fff,color:#fff,stroke-width:2px;')
    lines.append('  classDef io     fill:#111,stroke:#444,color:#888,stroke-dasharray:4 2;')

    # Input node
    lines.append('  INPUT([" Workflow Input "]):::io')

    node_ids = []
    for i, agent in enumerate(agents):
        a_type  = agent["agent_type"]
        source  = agent.get("source", "new")
        acc     = agent.get("metrics", {}).get("accuracy", 0)
        acc_pct = f"{acc * 100:.0f}%" if acc else ""
        label   = f'{a_type} Agent\\n{acc_pct}'
        n = nid(i, a_type)
        node_ids.append((n, source))
        lines.append(f'  {n}["{label}"]:::{source}')

    # OUTPUT node
    lines.append('  OUTPUT([" Executive Report "]):::io')

    # Edges: INPUT → first → ... → last → OUTPUT
    lines.append(f'  INPUT --> {node_ids[0][0]}')
    for idx in range(len(node_ids) - 1):
        cur  = node_ids[idx][0]
        nxt  = node_ids[idx + 1][0]
        lines.append(f'  {cur} -->|handoff| {nxt}')
    lines.append(f'  {node_ids[-1][0]} --> OUTPUT')

    mermaid = "\n".join(lines)
    return {"mermaid": mermaid, "agent_count": len(agents)}
