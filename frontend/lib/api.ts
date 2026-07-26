/**
 * Square API client — thin wrapper over fetch that calls the FastAPI backend.
 * All endpoints match the API Endpoint List in the build brief.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(opts.headers ?? {}),
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.error?.message ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// ─── Types (mirrors Pydantic schemas) ────────────────────────────────────────

export type Industry =
  | "HR" | "BFSI" | "Retail" | "Manufacturing" | "Telecom"
  | "Healthcare" | "Education" | "Government" | "Other";

export interface Task { name: string; description: string; actor: string; }
export interface AutomationCandidate { task_name: string; reason: string; }

export interface Workflow {
  workflow_id: string;
  tenant_id: string;
  industry: string;
  monthly_volume: number;
  description: string;
  tasks: Task[];
  stakeholders: string[];
  automation_candidates: AutomationCandidate[];
  current_bottlenecks: string[];
  created_at: string;
}

export interface AgentMetrics { accuracy: number; processing_time_s: number; uptime: number; }
export interface Agent {
  agent_id: string;
  workflow_id: string;
  agent_type: string;
  responsibility: string;
  source: "reused" | "new";
  metrics: AgentMetrics;
  status: string;
}

export type ScenarioKey =
  | "happy_path" | "agent_failure" | "wrong_decision"
  | "high_workload" | "external_failure" | "human_override";

export interface SimulationResult {
  workflow_id: string;
  scenario: ScenarioKey;
  status: "passed" | "warning" | "critical";
  success_rate: number;
  avg_response_time_s: number;
  notes: string;
}

export interface GovernanceAgentResult {
  agent_id: string;
  agent_name: string;
  created: boolean;
  healthy: boolean;
  decision: string;
  human_oversight_recommendation: string;
}
export interface GovernanceReport {
  workflow_id: string;
  agents: GovernanceAgentResult[];
  summary: string;
}

export interface RiskCategory { name: string; score: number; justification: string; }
export interface RiskReport {
  workflow_id: string;
  overall_score: number;
  categories: RiskCategory[];
  recommendations: string[];
}

export interface ROIReport {
  workflow_id: string;
  annual_savings: number;
  implementation_cost: number;
  ai_infra_cost_per_year: number;
  fte_reduction: number;
  payback_period_months: number;
  roi_percent_year1: number;
  assumptions: string[];
  sensitivity: {
    best_case: { roi_percent: number; payback_months: number };
    expected: { roi_percent: number; payback_months: number };
    worst_case: { roi_percent: number; payback_months: number };
  };
}

export interface DeploymentPhase {
  name: string;
  scope_percent: number;
  human_oversight_percent: number;
  success_criteria: string;
}
export interface DeploymentPlan {
  phases: DeploymentPhase[];
  go_no_go: "GO" | "PILOT_FIRST" | "NEEDS_CHANGES";
  justification: string;
}

export interface ExecutiveReport {
  workflow_id: string;
  automation_score: number;
  risk_report: RiskReport;
  roi_report: ROIReport;
  deployment_plan: DeploymentPlan;
  go_no_go: "GO" | "PILOT_FIRST" | "NEEDS_CHANGES";
}

// ─── API calls ────────────────────────────────────────────────────────────────

export const api = {
  analyzeWorkflow: (body: { industry: Industry; monthly_volume: number; description: string }) =>
    request<Workflow>("/api/workflow/analyze", { method: "POST", body: JSON.stringify(body) }),

  getWorkflow: (id: string) => request<Workflow>(`/api/workflow/${id}`),

  generateAgents: (workflow_id: string) =>
    request<Agent[]>("/api/agents/generate", { method: "POST", body: JSON.stringify({ workflow_id }) }),

  getAgents: (workflow_id: string) => request<Agent[]>(`/api/agents/${workflow_id}`),

  runSimulation: (workflow_id: string, scenarios: ScenarioKey[]) =>
    request<SimulationResult[]>("/api/simulate/run", {
      method: "POST",
      body: JSON.stringify({ workflow_id, scenarios }),
    }),

  runGovernance: (workflow_id: string) =>
    request<GovernanceReport>("/api/governance/check", {
      method: "POST",
      body: JSON.stringify({ workflow_id }),
    }),

  analyzeRisk: (workflow_id: string) =>
    request<RiskReport>("/api/risk/analyze", { method: "POST", body: JSON.stringify({ workflow_id }) }),

  analyzeROI: (workflow_id: string) =>
    request<ROIReport>("/api/roi/analyze", { method: "POST", body: JSON.stringify({ workflow_id }) }),

  generateReport: (workflow_id: string) =>
    request<ExecutiveReport>("/api/report/generate", {
      method: "POST",
      body: JSON.stringify({ workflow_id }),
    }),

  downloadPDF: (workflow_id: string) =>
    `${BASE}/api/report/${workflow_id}/pdf`,
};
