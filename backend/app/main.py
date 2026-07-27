"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.middleware.session import SessionMiddleware
from app.routers import admin, agents, governance, report, risk, roi, simulate, workflow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Square backend starting — DEMO_MODE=%s", settings.DEMO_MODE)
    # Pre-warm in-memory agent registry
    try:
        from app.db.chroma_client import _registry
        logger.info("Agent registry ready — %d seed agents loaded", len(_registry))
    except Exception as exc:
        logger.warning("Registry init skipped: %s", exc)
    # Pre-warm ChromaDB embedding model
    try:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        ef = DefaultEmbeddingFunction()
        ef(["warmup"])  # trigger model download/load at startup
        logger.info("ChromaDB embedding model pre-warmed")
    except Exception as exc:
        logger.warning("ChromaDB embedding pre-warm skipped: %s", exc)
    # Seed compliance RAG collection
    try:
        from app.db.compliance_rag import _get_compliance_collection
        col = _get_compliance_collection()
        logger.info("Compliance RAG ready — %d documents in collection", col.count())
    except Exception as exc:
        logger.warning("Compliance RAG init skipped: %s", exc)
    yield
    logger.info("Square backend shutting down")


limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.RATE_LIMIT_PER_HOUR}/hour"])

app = FastAPI(
    title="Square API",
    description="Enterprise Agent Engineering Platform — pre-deployment AI agent simulation & governance",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── Middleware ────────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SessionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "https://*.vercel.app"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Admin-Token"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(workflow.router)
app.include_router(agents.router)
app.include_router(simulate.router)
app.include_router(governance.router)
app.include_router(risk.router)
app.include_router(roi.router)
app.include_router(report.router)
app.include_router(admin.router)


# ─── Root ─────────────────────────────────────────────────────────────────────
@app.get("/", tags=["health"], summary="Service info")
async def root():
    """Welcome endpoint — confirms the API is reachable and shows key links."""
    return {
        "service": "SQUARE API",
        "description": "Enterprise Agent Engineering Platform — pre-deployment AI agent simulation & governance",
        "status": "ok",
        "demo_mode": settings.DEMO_MODE,
        "docs": "/docs",
        "health": "/health",
        "version": "1.0.0",
    }


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"], summary="Health check")
async def health():
    """Lightweight liveness probe — returns ok when the server is running."""
    return {"status": "ok", "demo_mode": settings.DEMO_MODE}


# ─── Global error handler ─────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=502,
        content={"error": {"code": "UPSTREAM_ERROR", "message": str(exc)}},
    )
