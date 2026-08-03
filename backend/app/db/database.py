"""SQLAlchemy ORM models + async session factory.

The engine is lazily created — only initialised when get_db() is first called
by a route that needs it.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class WorkflowORM(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    industry: Mapped[str] = mapped_column(String(64))
    monthly_volume: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    tasks: Mapped[dict] = mapped_column(JSON, default=list)
    stakeholders: Mapped[dict] = mapped_column(JSON, default=list)
    automation_candidates: Mapped[dict] = mapped_column(JSON, default=list)
    current_bottlenecks: Mapped[dict] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentORM(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id: Mapped[str] = mapped_column(String(36), index=True)
    agent_type: Mapped[str] = mapped_column(String(32))
    responsibility: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16))
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    processing_time_s: Mapped[float] = mapped_column(Float, default=0.0)
    uptime: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="created")


class SimulationResultORM(Base):
    __tablename__ = "simulation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id: Mapped[str] = mapped_column(String(36), index=True)
    scenario: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    success_rate: Mapped[float] = mapped_column(Float)
    avg_response_time_s: Mapped[float] = mapped_column(Float)
    notes: Mapped[str] = mapped_column(Text)


class ReportORM(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    automation_score: Mapped[float] = mapped_column(Float)
    risk_report: Mapped[dict] = mapped_column(JSON)
    roi_report: Mapped[dict] = mapped_column(JSON)
    deployment_plan: Mapped[dict] = mapped_column(JSON)
    go_no_go: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ─── Lazy engine — only created when actually needed ─────────────────────────

_engine = None
_async_session_factory = None


def _get_engine():
    global _engine, _async_session_factory
    if _engine is None:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from app.config import get_settings
        settings = get_settings()
        _engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
        _async_session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine, _async_session_factory


async def get_db() -> AsyncGenerator:
    _, factory = _get_engine()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables():
    engine, _ = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
