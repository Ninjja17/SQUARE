"""
Orchestrate router — persistent agent lifecycle management endpoints.

POST /api/orchestrate/bootstrap-core
    Ensure all 6 SQUARE core skills exist in Orchestrate (Skills API).
    Idempotent — safe to call multiple times; existing skills are never duplicated.

GET  /api/orchestrate/core-status
    Return presence/absence of each core skill in Orchestrate.

POST /api/orchestrate/bootstrap-core-agents
    Ensure all 6 SQUARE core agents exist in Orchestrate as real Agents (Agents API).
    Idempotent — safe to call multiple times; existing agents are never duplicated.

GET  /api/orchestrate/core-agents-status
    Return presence/absence of each core agent in Orchestrate.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/orchestrate", tags=["orchestrate"])


@router.post("/bootstrap-core", summary="Ensure all 6 SQUARE core skills exist in Orchestrate")
async def bootstrap_core():
    """
    Guarantee that all SQUARE core agent skills are present in Orchestrate.

    Idempotent — already-present skills are left untouched (``status: already_exists``).
    Missing skills are created (``status: created``).

    Response per core agent type::

        {
            "agent_type": "Analyzer",
            "skill_name": "square_core_analyzer",
            "status":     "created" | "already_exists" | "failed" | "skipped",
            "skill_id":   "...",
            "message":    "..."
        }
    """
    from app.services.orchestrate_client import bootstrap_core_skills

    loop    = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, bootstrap_core_skills)

    created  = sum(1 for r in results if r["status"] == "created")
    existing = sum(1 for r in results if r["status"] == "already_exists")
    failed   = sum(1 for r in results if r["status"] == "failed")
    skipped  = sum(1 for r in results if r["status"] == "skipped")

    return {
        "bootstrap_results": results,
        "summary": {
            "total":          len(results),
            "created":        created,
            "already_exists": existing,
            "failed":         failed,
            "skipped":        skipped,
        },
    }


@router.get("/core-status", summary="Check which SQUARE core skills are present in Orchestrate")
async def core_status():
    """
    Return the presence status of all 6 SQUARE core skills in Orchestrate.

    Response per core agent type::

        {
            "agent_type": "Risk",
            "skill_name": "square_core_risk",
            "present":    true,
            "skill_id":   "...",
            "message":    "Present in Orchestrate (id=...)"
        }
    """
    from app.services.orchestrate_client import get_core_status

    loop    = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, get_core_status)

    present = sum(1 for r in results if r.get("present"))
    return {
        "core_skills": results,
        "summary": {
            "total":   len(results),
            "present": present,
            "missing": len(results) - present,
        },
    }


@router.post("/bootstrap-core-agents", summary="Ensure all 6 SQUARE core agents exist in Orchestrate (Agents API)")
async def bootstrap_core_agents_endpoint():
    """
    Create all 6 SQUARE core agents in Orchestrate as real AI Agents using the
    ``POST /v1/orchestrate/agents`` endpoint.

    Idempotent — already-present agents are left untouched (``status: already_exists``).
    Missing agents are created with full instructions, LLM binding, and metadata.

    Response per core agent type::

        {
            "agent_type":           "Analyzer",
            "agent_name":           "square-core-analyzer",
            "status":               "created" | "already_exists" | "failed" | "skipped",
            "orchestrate_agent_id": "...",
            "message":              "..."
        }
    """
    from app.services.orchestrate_client import bootstrap_core_agents

    loop    = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, bootstrap_core_agents)

    created  = sum(1 for r in results if r["status"] == "created")
    existing = sum(1 for r in results if r["status"] == "already_exists")
    failed   = sum(1 for r in results if r["status"] == "failed")
    skipped  = sum(1 for r in results if r["status"] == "skipped")

    return {
        "bootstrap_results": results,
        "summary": {
            "total":          len(results),
            "created":        created,
            "already_exists": existing,
            "failed":         failed,
            "skipped":        skipped,
        },
    }


@router.get("/core-agents-status", summary="Check which SQUARE core agents are present in Orchestrate")
async def core_agents_status():
    """
    Return the presence status of all 6 SQUARE core agents in Orchestrate (Agents API).

    Response per core agent type::

        {
            "agent_type":           "Risk",
            "agent_name":           "square-core-risk",
            "present":              true,
            "orchestrate_agent_id": "...",
            "message":              "Present in Orchestrate (id=...)"
        }
    """
    from app.services.orchestrate_client import get_core_agents_status

    loop    = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, get_core_agents_status)

    present = sum(1 for r in results if r.get("present"))
    return {
        "core_agents": results,
        "summary": {
            "total":   len(results),
            "present": present,
            "missing": len(results) - present,
        },
    }
