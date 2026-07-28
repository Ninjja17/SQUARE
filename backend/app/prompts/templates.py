"""Prompt templates for IBM Granite via watsonx.ai."""

WORKFLOW_UNDERSTANDING_SYSTEM = (
    "You are a business process analyst. Extract structured data from a workflow description. "
    "Always respond in valid JSON matching the given schema. "
    "Do not invent systems or steps that were not mentioned or reasonably implied."
)

WORKFLOW_UNDERSTANDING_USER = """Industry: {industry}
Expected monthly volume: {volume}
Workflow description: "<user_workflow>{workflow_description}</user_workflow>"

Return JSON with:
- tasks: ordered list of {{ "name": str, "description": str, "actor": str }}
- stakeholders: list of strings
- automation_candidates: list of {{ "task_name": str, "reason": str }}
- current_bottlenecks: list of strings
"""

# ─────────────────────────────────────────────────────────────────────────────

AGENT_GENERATION_SYSTEM = (
    "You are an AI agent architect. Given a list of tasks flagged for automation, "
    "select the minimal set of UNIQUE agent types from this fixed set: "
    "Analyzer, Verification, Decision, Communication, Risk, Planner. "
    "Each agent type must appear AT MOST ONCE in your output. "
    "If multiple tasks share a role (e.g. data ingestion and calculation), combine them under one agent or assign distinct appropriate types (e.g., Decision for calculations, Planner for reporting). "
    "Do not invent new agent types."
)

AGENT_GENERATION_USER = """Automation candidates: {automation_candidates_json}
Industry: {industry}

Return a JSON array of UNIQUE agents (no duplicate agent_types). Each item:
{{ "task_name": str, "agent_type": "Analyzer"|"Verification"|"Decision"|"Communication"|"Risk"|"Planner", "responsibility": str, "suggested_metrics": {{ "accuracy": float, "processing_time_s": float, "uptime": float }} }}
"""

# ─────────────────────────────────────────────────────────────────────────────

RISK_ANALYSIS_SYSTEM = (
    "You are an enterprise risk assessor for AI automation projects. "
    "Score risk 0-100 (0=no risk, 100=critical) across exactly these categories: "
    "security, compliance, operational, data_quality, agent_dependency. "
    "Justify each score in one sentence."
)

RISK_ANALYSIS_USER = """Workflow: {workflow_summary}
Generated agents: {agent_list_json}
Simulation results: {simulation_results_json}

{compliance_context}

Your recommendations must reference the specific compliance frameworks above where relevant.
Return JSON: {{ "overall_score": float, "categories": [{{"name": str, "score": float, "justification": str}}], "recommendations": [str] }}
"""

# ─────────────────────────────────────────────────────────────────────────────

ROI_ANALYSIS_SYSTEM = (
    "You are a financial analyst for automation business cases. "
    "Use conservative, defensible estimates. Show your assumptions."
)

ROI_ANALYSIS_USER = """Industry: {industry}
Monthly volume: {volume}
Current manual cost per transaction: {manual_cost_estimate}
Agent team: {agent_list_json}

Return JSON: {{
  "annual_savings": float,
  "implementation_cost": float,
  "ai_infra_cost_per_year": float,
  "fte_reduction": float,
  "payback_period_months": float,
  "roi_percent_year1": float,
  "assumptions": [str]
}}
"""

# ─────────────────────────────────────────────────────────────────────────────

SIMULATION_SYSTEM = (
    "You are an enterprise AI simulation analyst. Given a workflow context, agent team, "
    "and test scenarios, produce realistic simulation outcomes. "
    "Be conservative — real-world agents often struggle with edge cases."
)

SIMULATION_USER = """Industry: {industry}
Workflow: {workflow_summary}
Agent team: {agents_json}
Scenarios to simulate: {scenarios_json}

For EACH scenario, return a JSON array where each item has:
{{ "scenario": str, "status": "passed"|"warning"|"critical", "success_rate": float (0-1), "avg_response_time_s": float, "notes": str (one sentence specific to this workflow) }}
"""

# ─────────────────────────────────────────────────────────────────────────────

GOVERNANCE_JUSTIFICATION_SYSTEM = (
    "You are a governance auditor for AI agent deployments. "
    "Given an agent's details and simulation performance, provide a one-sentence justification "
    "for the governance decision (Keep, Dismiss, or Promote)."
)

GOVERNANCE_JUSTIFICATION_USER = """Agent: {agent_name} ({agent_type})
Responsibility: {responsibility}
Decision: {decision}
Simulation summary: {sim_summary}

Return JSON: {{ "justification": str }}
"""

# ─────────────────────────────────────────────────────────────────────────────

DEPLOYMENT_ADVISOR_SYSTEM = (
    "You are a deployment strategist for enterprise AI rollouts. "
    "Recommend a phased rollout with explicit human-in-the-loop percentages."
)

DEPLOYMENT_ADVISOR_USER = """Risk report: {risk_report_json}
ROI report: {roi_report_json}
Simulation results: {simulation_results_json}

Return JSON: {{
  "phases": [{{"name": str, "scope_percent": float, "human_oversight_percent": float, "success_criteria": str}}],
  "go_no_go": "GO" | "PILOT_FIRST" | "NEEDS_CHANGES",
  "justification": str
}}
"""

# ─────────────────────────────────────────────────────────────────────────────

SIMULATION_NARRATIVE_SYSTEM = (
    "You are narrating a realistic simulation of AI agents processing a business workflow. "
    "Show step-by-step how each agent handles its task, including inter-agent communication, "
    "decisions made, data passed between agents, and any issues encountered. "
    "Make it read like a live execution log with timestamps."
)

SIMULATION_NARRATIVE_USER = """Workflow: {workflow_summary}
Agents: {agents_json}
Scenario: {scenario_name} — {scenario_description}

Generate a detailed interaction timeline showing how each agent processes one transaction under this scenario.
Return JSON: {{
  "timeline": [
    {{
      "timestamp": str (relative like "00:00.0s"),
      "agent": str (agent type name),
      "action": str (what the agent does),
      "status": "success" | "processing" | "error" | "handoff",
      "detail": str (brief detail or data passed),
      "target_agent": str | null (if handing off to another agent)
    }}
  ],
  "outcome": str (one sentence overall result),
  "total_time": str (e.g. "2.3s")
}}

Generate 8-12 timeline steps showing realistic agent interactions for this scenario.
"""
