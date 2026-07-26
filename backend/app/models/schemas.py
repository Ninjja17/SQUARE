"""Pydantic Data Contract models — shared between all layers."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ─── Enums ────────────────────────────────────────────────────────────────────

class IndustryEnum(str, Enum):
    HR = "HR"
    BFSI = "BFSI"
    RETAIL = "Retail"
    MANUFACTURING = "Manufacturing"
    TELECOM = "Telecom"
    HEALTHCARE = "Healthcare"
    EDUCATION = "Education"
    GOVERNMENT = "Government"
    OTHER = "Other"


class AgentTypeEnum(str, Enum):
    ANALYZER = "Analyzer"
    VERIFICATION = "Verification"
    DECISION = "Decision"
    COMMUNICATION = "Communication"
    RISK = "Risk"
    PLANNER = "Planner"


class AgentSourceEnum(str, Enum):
    REUSED = "reused"
    NEW = "new"


class AgentStatusEnum(str, Enum):
    CREATED = "created"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DISMISSED = "dismissed"
    PROMOTED = "promoted"


class ScenarioEnum(str, Enum):
    HAPPY_PATH = "happy_path"
    AGENT_FAILURE = "agent_failure"
    WRONG_DECISION = "wrong_decision"
    HIGH_WORKLOAD = "high_workload"
    EXTERNAL_FAILURE = "external_failure"
    HUMAN_OVERRIDE = "human_override"


class SimulationStatusEnum(str, Enum):
    PASSED = "passed"
    WARNING = "warning"
    CRITICAL = "critical"


class GoNoGoEnum(str, Enum):
    GO = "GO"
    PILOT_FIRST = "PILOT_FIRST"
    NEEDS_CHANGES = "NEEDS_CHANGES"


# ─── Sub-models ───────────────────────────────────────────────────────────────

class Task(BaseModel):
    name: str
    description: str
    actor: str


class AutomationCandidate(BaseModel):
    task_name: str
    reason: str


class AgentMetrics(BaseModel):
    accuracy: float = 0.0
    processing_time_s: float = 0.0
    uptime: float = 0.0


class RiskCategory(BaseModel):
    name: str
    score: float
    justification: str


class DeploymentPhase(BaseModel):
    name: str
    scope_percent: float
    human_oversight_percent: float
    success_criteria: str


# ─── Core schemas ─────────────────────────────────────────────────────────────

class WorkflowRequest(BaseModel):
    industry: IndustryEnum
    monthly_volume: int = Field(gt=0)
    description: str = Field(min_length=10, max_length=2000)


class WorkflowResponse(BaseModel):
    workflow_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    industry: str
    monthly_volume: int
    description: str
    tasks: list[Task] = []
    stakeholders: list[str] = []
    automation_candidates: list[AutomationCandidate] = []
    current_bottlenecks: list[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentResponse(BaseModel):
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str
    agent_type: AgentTypeEnum
    responsibility: str
    source: AgentSourceEnum
    metrics: AgentMetrics = Field(default_factory=AgentMetrics)
    status: AgentStatusEnum = AgentStatusEnum.CREATED


class SimulationRequest(BaseModel):
    workflow_id: str
    scenarios: list[ScenarioEnum]


class SimulationResult(BaseModel):
    workflow_id: str
    scenario: ScenarioEnum
    status: SimulationStatusEnum
    success_rate: float
    avg_response_time_s: float
    notes: str


class RiskReport(BaseModel):
    workflow_id: str
    overall_score: float
    categories: list[RiskCategory]
    recommendations: list[str]


class ROIReport(BaseModel):
    workflow_id: str
    annual_savings: float
    implementation_cost: float
    ai_infra_cost_per_year: float
    fte_reduction: float
    payback_period_months: float
    roi_percent_year1: float
    assumptions: list[str] = []
    sensitivity: dict = {}


class GovernanceAgentResult(BaseModel):
    agent_id: str
    agent_name: str
    created: bool
    healthy: bool
    decision: str  # Keep | Dismiss | Promote to Registry
    human_oversight_recommendation: str = ""


class GovernanceReport(BaseModel):
    workflow_id: str
    agents: list[GovernanceAgentResult]
    summary: str


class DeploymentPlan(BaseModel):
    phases: list[DeploymentPhase]
    go_no_go: GoNoGoEnum
    justification: str


class ExecutiveReport(BaseModel):
    workflow_id: str
    automation_score: float
    risk_report: RiskReport
    roi_report: ROIReport
    deployment_plan: DeploymentPlan
    go_no_go: GoNoGoEnum


# ─── Error shape ──────────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
