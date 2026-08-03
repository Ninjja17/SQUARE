"""
Admin router — GET /api/admin/*
Internal read-only monitoring dashboard for the SQUARE backend.

All endpoints require the header:
    X-Admin-Token: <ADMIN_DASHBOARD_TOKEN from .env>

Never expose secrets in responses.
"""
from __future__ import annotations

import time
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/admin", tags=["admin (internal)"])

_SERVER_START = time.time()


# ─── Auth dependency ──────────────────────────────────────────────────────────

def require_admin(x_admin_token: str = Header(default="")) -> None:
    """Dependency — raises 401 if X-Admin-Token header is missing or wrong."""
    expected = settings.ADMIN_DASHBOARD_TOKEN
    if not expected or not x_admin_token:
        raise HTTPException(status_code=401, detail="Missing X-Admin-Token header")
    # Constant-time compare to avoid timing attacks
    import hmac
    if not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Invalid admin token")


# ─── Safe summary helpers ─────────────────────────────────────────────────────

def _wf_summary(wf: dict) -> dict:
    return {
        "workflow_id": wf.get("workflow_id", ""),
        "industry":    wf.get("industry", ""),
        "monthly_volume": wf.get("monthly_volume", 0),
        "task_count":  len(wf.get("tasks", [])),
        "automation_candidate_count": len(wf.get("automation_candidates", [])),
        "created_at":  wf.get("created_at", ""),
    }


def _agent_summary(agent: dict) -> dict:
    return {
        "agent_id":      agent.get("agent_id", ""),
        "agent_type":    agent.get("agent_type", ""),
        "source":        agent.get("source", ""),
        "status":        agent.get("status", ""),
        "accuracy":      agent.get("metrics", {}).get("accuracy", 0),
        "uptime":        agent.get("metrics", {}).get("uptime", 0),
    }


def _sim_summary(sim: dict) -> dict:
    return {
        "scenario":         sim.get("scenario", ""),
        "status":           sim.get("status", ""),
        "success_rate":     sim.get("success_rate", 0),
        "avg_response_time_s": sim.get("avg_response_time_s", 0),
    }


def _gov_summary(gov: dict) -> dict:
    return {
        "workflow_id": gov.get("workflow_id", ""),
        "agent_count": len(gov.get("agents", [])),
        "summary":     gov.get("summary", ""),
    }


def _report_summary(rep: dict) -> dict:
    return {
        "workflow_id":     rep.get("workflow_id", ""),
        "automation_score": rep.get("automation_score", 0),
        "go_no_go":        rep.get("go_no_go", ""),
        "overall_risk":    rep.get("risk_report", {}).get("overall_score", 0),
        "roi_year1":       rep.get("roi_report", {}).get("roi_percent_year1", 0),
        "annual_savings":  rep.get("roi_report", {}).get("annual_savings", 0),
    }


# ─── Cache accessors (lazy import to avoid circular deps) ─────────────────────

def _get_caches() -> dict[str, dict]:
    from app.routers.workflow   import _cache           as _wf_cache
    from app.routers.agents     import _agent_cache
    from app.routers.simulate   import _sim_cache
    from app.routers.governance import _gov_cache
    from app.routers.risk       import _risk_cache
    from app.routers.roi        import _roi_cache
    from app.routers.report     import _report_cache
    return {
        "workflows":   _wf_cache,
        "agents":      _agent_cache,
        "simulations": _sim_cache,
        "governance":  _gov_cache,
        "risk":        _risk_cache,
        "roi":         _roi_cache,
        "reports":     _report_cache,
    }


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/overview",
    summary="Pipeline counts + server info",
    description="High-level snapshot of all cached data and server config. No secrets returned.",
)
async def overview(_: None = Depends(require_admin)) -> dict[str, Any]:
    caches = _get_caches()

    total_agents = sum(len(v) for v in caches["agents"].values())
    total_sims   = sum(len(v) for v in caches["simulations"].values())

    return {
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - _SERVER_START, 1),
        "model":       settings.GROQ_MODEL,
        "provider":    "Groq (Llama 3.3 70B)",
        "counts": {
            "workflows":          len(caches["workflows"]),
            "agents_generated":   total_agents,
            "simulations_run":    total_sims,
            "governance_reports": len(caches["governance"]),
            "risk_reports":       len(caches["risk"]),
            "roi_reports":        len(caches["roi"]),
            "executive_reports":  len(caches["reports"]),
        },
        "config": {
            "rate_limit_per_hour": settings.RATE_LIMIT_PER_HOUR,
            "chroma_db_path":      settings.CHROMA_DB_PATH,
            "orchestrate_configured": bool(
                settings.ORCHESTRATE_INSTANCE_URL and settings.ORCHESTRATE_API_KEY
            ),
            "groq_key_set": bool(settings.GROQ_API_KEY),
        },
    }


@router.get(
    "/workflows",
    summary="List all cached workflows",
    description="Returns safe summaries. Pass ?full=true for complete payloads (no secrets added).",
)
async def list_workflows(
    full: bool = Query(False, description="Return full workflow payload instead of summary"),
    _: None = Depends(require_admin),
) -> dict[str, Any]:
    caches = _get_caches()
    workflows = caches["workflows"]
    items = list(workflows.values()) if full else [_wf_summary(w) for w in workflows.values()]
    return {"count": len(items), "workflows": items}


@router.get(
    "/agents",
    summary="List all cached agents grouped by workflow",
    description="Returns safe summaries per workflow. Pass ?full=true for complete agent payloads.",
)
async def list_agents(
    full: bool = Query(False),
    _: None = Depends(require_admin),
) -> dict[str, Any]:
    caches = _get_caches()
    result = {}
    total = 0
    for wf_id, agent_list in caches["agents"].items():
        items = agent_list if full else [_agent_summary(a) for a in agent_list]
        result[wf_id] = items
        total += len(items)
    return {"total_agents": total, "by_workflow": result}


@router.get(
    "/simulations",
    summary="List all cached simulation results grouped by workflow",
)
async def list_simulations(
    full: bool = Query(False),
    _: None = Depends(require_admin),
) -> dict[str, Any]:
    caches = _get_caches()
    result = {}
    total = 0
    for wf_id, sim_list in caches["simulations"].items():
        items = sim_list if full else [_sim_summary(s) for s in sim_list]
        result[wf_id] = items
        total += len(items)
    return {"total_simulations": total, "by_workflow": result}


@router.get(
    "/governance",
    summary="List all cached governance reports",
)
async def list_governance(
    full: bool = Query(False),
    _: None = Depends(require_admin),
) -> dict[str, Any]:
    caches = _get_caches()
    items = (
        list(caches["governance"].values()) if full
        else [_gov_summary(g) for g in caches["governance"].values()]
    )
    return {"count": len(items), "reports": items}


@router.get(
    "/reports",
    summary="List all cached executive reports",
)
async def list_reports(
    full: bool = Query(False),
    _: None = Depends(require_admin),
) -> dict[str, Any]:
    caches = _get_caches()
    items = (
        list(caches["reports"].values()) if full
        else [_report_summary(r) for r in caches["reports"].values()]
    )
    return {"count": len(items), "reports": items}


@router.get(
    "/health",
    summary="Deep health diagnostics",
    description="Checks ChromaDB, compliance RAG, cache sizes, and module imports. Always returns JSON.",
)
async def admin_health(_: None = Depends(require_admin)) -> dict[str, Any]:
    status = "ok"
    checks: dict[str, Any] = {}

    # ── ChromaDB ────────────────────────────────────────────────────────
    try:
        from app.db.chroma_client import _get_chroma
        col = _get_chroma()
        checks["chroma_agent_registry"] = {"status": "ok", "doc_count": col.count()}
    except Exception as exc:
        checks["chroma_agent_registry"] = {"status": "degraded", "detail": str(exc)}
        status = "degraded"

    # ── Compliance RAG ──────────────────────────────────────────────────
    try:
        from app.db.compliance_rag import _get_compliance_collection
        rag_col = _get_compliance_collection()
        checks["compliance_rag"] = {"status": "ok", "doc_count": rag_col.count()}
    except Exception as exc:
        try:
            from app.db.compliance_rag import COMPLIANCE_DOCS
            checks["compliance_rag"] = {
                "status": "in-memory",
                "doc_count": len(COMPLIANCE_DOCS),
                "detail": str(exc),
            }
        except Exception:
            checks["compliance_rag"] = {"status": "degraded", "detail": str(exc)}
            status = "degraded"

    # ── Cache sizes ─────────────────────────────────────────────────────
    try:
        caches = _get_caches()
        checks["cache_sizes"] = {
            k: (sum(len(v) for v in c.values()) if all(isinstance(v, list) for v in c.values()) else len(c))
            for k, c in caches.items()
        }
    except Exception as exc:
        checks["cache_sizes"] = {"status": "error", "detail": str(exc)}
        status = "degraded"

    # ── Module imports ──────────────────────────────────────────────────
    module_checks = [
        ("workflow_engine",    "app.services.workflow_engine"),
        ("agent_generation",   "app.services.agent_generation"),
        ("simulation_engine",  "app.services.simulation_engine"),
        ("risk_engine",        "app.services.risk_engine"),
        ("roi_engine",         "app.services.roi_engine"),
        ("deployment_advisor", "app.services.deployment_advisor"),
        ("core_control_agent", "app.services.core_control_agent"),
    ]
    module_status: dict[str, str] = {}
    for label, mod in module_checks:
        try:
            __import__(mod)
            module_status[label] = "ok"
        except Exception as exc:
            module_status[label] = f"error: {exc}"
            status = "degraded"
    checks["modules"] = module_status

    return {
        "status":    status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - _SERVER_START, 1),
        **checks,
    }
