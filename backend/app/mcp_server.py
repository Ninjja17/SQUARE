"""
SQUARE MCP Server — Enterprise Model Context Protocol Implementation.

Exposes SQUARE's pre-production AI agent simulation, governance, and RAG capabilities as:
  1. MCP Tools (strict JSON schemas):
     - analyze_workflow
     - generate_agents
     - run_simulation
     - run_governance_check
     - analyze_risk
     - analyze_roi
     - generate_report
     - full_pipeline (with stepwise execution timings & audit metadata)

  2. MCP Resources (normalized, paginated, enterprise-safe):
     - compliance://snippets (Regulatory compliance RAG corpus)
     - agents://registry (Common Agent Vector Registry templates)

Transports Supported:
  - Stdio: python -m app.mcp_server
  - HTTP / SSE: Fast API router endpoint in app/routers/mcp.py
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from app.config import get_settings
from app.db.chroma_client import SEED_AGENTS, _registry
from app.db.compliance_rag import COMPLIANCE_DOCS

logger = logging.getLogger(__name__)
settings = get_settings()

MCP_VERSION = "2024-11-05"
SERVER_NAME = "square-mcp"
SERVER_VERSION = "1.0.0"


# ── JSON-RPC 2.0 Helpers ──────────────────────────────────────────────────────

def _ok(id_: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_: Any, code: int, message: str, data: Any = None) -> dict:
    err_obj: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err_obj["data"] = data
    return {"jsonrpc": "2.0", "id": id_, "error": err_obj}


# ── MCP Tool Definitions (Strict JSON Schemas) ────────────────────────────────

TOOLS = [
    {
        "name": "analyze_workflow",
        "description": (
            "Parse a plain-English business workflow description into structured tasks, "
            "stakeholders, automation candidates, and bottlenecks. "
            "Returns a workflow_id required by subsequent tools."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Plain-English description of the current business workflow (30–2000 chars).",
                },
                "industry": {
                    "type": "string",
                    "enum": ["HR", "BFSI", "Retail", "Manufacturing", "Telecom",
                             "Healthcare", "Education", "Government", "Other"],
                    "description": "Industry sector of the organization.",
                },
                "monthly_volume": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Expected number of workflow executions per month.",
                },
            },
            "required": ["description", "industry", "monthly_volume"],
            "additionalProperties": False,
        },
    },
    {
        "name": "generate_agents",
        "description": (
            "Generate an AI agent team for a previously analyzed workflow. "
            "Checks the Common Agent Registry for reusable agents first, "
            "then creates specialized new agents as needed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "Workflow ID returned by analyze_workflow.",
                },
            },
            "required": ["workflow_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_simulation",
        "description": (
            "Stress-test the agent team across 6 scenarios: happy_path, agent_failure, "
            "wrong_decision, high_workload, external_failure, human_override. "
            "Returns per-scenario pass/warning/critical status and notes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "Workflow ID returned by analyze_workflow.",
                },
                "scenarios": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["happy_path", "agent_failure", "wrong_decision",
                                 "high_workload", "external_failure", "human_override"],
                    },
                    "description": "Scenarios to run. Defaults to all 6 if omitted.",
                },
            },
            "required": ["workflow_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_governance_check",
        "description": (
            "Run Core Control Agent governance check: validates agent health, "
            "detects redundancies, and issues Keep / Dismiss / Promote decisions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "Workflow ID returned by analyze_workflow.",
                },
            },
            "required": ["workflow_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "analyze_risk",
        "description": (
            "Score security, compliance, operational, data quality, and agent dependency risk (0–100). "
            "Uses RAG-grounded regulatory snippets (GDPR, HIPAA, PCI-DSS, SOX, etc.)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "Workflow ID returned by analyze_workflow.",
                },
            },
            "required": ["workflow_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "analyze_roi",
        "description": (
            "Calculate annual financial savings, implementation cost, payback period, "
            "and Year 1 ROI with best/expected/worst case sensitivity analysis."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "Workflow ID returned by analyze_workflow.",
                },
            },
            "required": ["workflow_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "generate_report",
        "description": (
            "Produce the final Executive Readiness Report with risk, ROI, governance summary, "
            "and GO / PILOT_FIRST / NEEDS_CHANGES deployment recommendation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "Workflow ID returned by analyze_workflow.",
                },
            },
            "required": ["workflow_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "full_pipeline",
        "description": (
            "Run the complete SQUARE pipeline end-to-end in one call: "
            "analyze -> generate -> simulate -> govern -> risk -> roi -> report. "
            "Returns stepwise execution log, timing metrics (ms), audit metadata, and final report."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Plain-English description of business workflow.",
                },
                "industry": {
                    "type": "string",
                    "enum": ["HR", "BFSI", "Retail", "Manufacturing", "Telecom",
                             "Healthcare", "Education", "Government", "Other"],
                },
                "monthly_volume": {
                    "type": "integer",
                    "minimum": 1,
                },
            },
            "required": ["description", "industry", "monthly_volume"],
            "additionalProperties": False,
        },
    },
]


# ── MCP Resource Definitions ──────────────────────────────────────────────────

RESOURCES = [
    {
        "uri": "compliance://snippets",
        "name": "Compliance RAG Corpus",
        "description": "Regulatory compliance requirement snippets (GDPR, HIPAA, PCI-DSS, SOX, FERPA, FedRAMP, ISO 27001, Basel III, CCPA, EEOC).",
        "mimeType": "application/json",
    },
    {
        "uri": "agents://registry",
        "name": "Common Agent Vector Registry",
        "description": "Reusable AI agent templates stored in ChromaDB vector registry for cross-industry workflow automation.",
        "mimeType": "application/json",
    },
]

RESOURCE_TEMPLATES = [
    {
        "uriTemplate": "compliance://snippets/{framework}",
        "name": "Compliance Framework Snippets",
        "description": "Filter regulatory compliance snippets by framework name (e.g. GDPR, HIPAA, PCI-DSS, SOX).",
        "mimeType": "application/json",
    },
    {
        "uriTemplate": "agents://registry/{agent_id}",
        "name": "Agent Registry Template",
        "description": "Look up a specific reusable agent template by ID.",
        "mimeType": "application/json",
    },
]


# ── Resource Read Helpers ─────────────────────────────────────────────────────

def get_compliance_resources(framework_filter: str | None = None, page: int = 1, page_size: int = 10) -> dict:
    """Fetch and paginate compliance RAG snippets."""
    docs = COMPLIANCE_DOCS
    if framework_filter:
        fw_upper = framework_filter.upper()
        docs = [d for d in docs if fw_upper in d["framework"].upper()]

    total = len(docs)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = docs[start:end]

    return {
        "resource_uri": f"compliance://snippets/{framework_filter}" if framework_filter else "compliance://snippets",
        "total_count": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        "items": paginated,
    }


def get_agent_registry_resources(agent_id_filter: str | None = None, page: int = 1, page_size: int = 10) -> dict:
    """Fetch and paginate agent registry templates."""
    agents = _registry if _registry else SEED_AGENTS
    if agent_id_filter:
        matched = [a for a in agents if a["id"] == agent_id_filter]
        return {
            "resource_uri": f"agents://registry/{agent_id_filter}",
            "total_count": len(matched),
            "page": 1,
            "page_size": page_size,
            "items": matched,
        }

    total = len(agents)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = agents[start:end]

    return {
        "resource_uri": "agents://registry",
        "total_count": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        "items": paginated,
    }


# ── HTTP Dispatch Helper with Retry & Backoff ─────────────────────────────────

BASE_URL = "http://localhost:8000"


def _http_post_with_retry(url: str, payload: dict, max_retries: int = 3) -> dict:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if settings.MCP_API_KEY:
        headers["X-MCP-API-Key"] = settings.MCP_API_KEY

    last_exc = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                time.sleep(0.5 * (2 ** attempt))  # exponential backoff
            else:
                raise exc

    raise last_exc or RuntimeError("HTTP request failed")


# ── Tool Dispatch Logic ───────────────────────────────────────────────────────

def _dispatch_tool(tool_name: str, args: dict) -> dict:
    """Execute tool call against SQUARE FastAPI backend with structured error responses."""
    call_id = str(uuid.uuid4())
    start_time = time.time()

    if tool_name == "analyze_workflow":
        res = _http_post_with_retry(f"{BASE_URL}/api/workflow/analyze", {
            "description": args["description"],
            "industry": args["industry"],
            "monthly_volume": args["monthly_volume"],
        })
        res["_mcp_meta"] = {"call_id": call_id, "duration_ms": round((time.time() - start_time) * 1000, 2)}
        return res

    if tool_name == "generate_agents":
        res = _http_post_with_retry(f"{BASE_URL}/api/agents/generate", {
            "workflow_id": args["workflow_id"],
        })
        res["_mcp_meta"] = {"call_id": call_id, "duration_ms": round((time.time() - start_time) * 1000, 2)}
        return res

    if tool_name == "run_simulation":
        scenarios = args.get("scenarios") or [
            "happy_path", "agent_failure", "wrong_decision",
            "high_workload", "external_failure", "human_override",
        ]
        res = _http_post_with_retry(f"{BASE_URL}/api/simulate/run", {
            "workflow_id": args["workflow_id"],
            "scenarios": scenarios,
        })
        res["_mcp_meta"] = {"call_id": call_id, "duration_ms": round((time.time() - start_time) * 1000, 2)}
        return res

    if tool_name == "run_governance_check":
        res = _http_post_with_retry(f"{BASE_URL}/api/governance/check", {
            "workflow_id": args["workflow_id"],
        })
        res["_mcp_meta"] = {"call_id": call_id, "duration_ms": round((time.time() - start_time) * 1000, 2)}
        return res

    if tool_name == "analyze_risk":
        res = _http_post_with_retry(f"{BASE_URL}/api/risk/analyze", {
            "workflow_id": args["workflow_id"],
        })
        res["_mcp_meta"] = {"call_id": call_id, "duration_ms": round((time.time() - start_time) * 1000, 2)}
        return res

    if tool_name == "analyze_roi":
        res = _http_post_with_retry(f"{BASE_URL}/api/roi/analyze", {
            "workflow_id": args["workflow_id"],
        })
        res["_mcp_meta"] = {"call_id": call_id, "duration_ms": round((time.time() - start_time) * 1000, 2)}
        return res

    if tool_name == "generate_report":
        res = _http_post_with_retry(f"{BASE_URL}/api/report/generate", {
            "workflow_id": args["workflow_id"],
        })
        res["_mcp_meta"] = {"call_id": call_id, "duration_ms": round((time.time() - start_time) * 1000, 2)}
        return res

    if tool_name == "full_pipeline":
        pipeline_start = time.time()
        steps_log = []

        # Step 1: Analyze workflow
        t0 = time.time()
        wf = _http_post_with_retry(f"{BASE_URL}/api/workflow/analyze", {
            "description": args["description"],
            "industry": args["industry"],
            "monthly_volume": args["monthly_volume"],
        })
        wf_id = wf["workflow_id"]
        t1_ms = round((time.time() - t0) * 1000, 2)
        steps_log.append({"step": "analyze_workflow", "status": "completed", "duration_ms": t1_ms})

        # Step 2: Generate agents
        t0 = time.time()
        ag = _http_post_with_retry(f"{BASE_URL}/api/agents/generate", {"workflow_id": wf_id})
        t2_ms = round((time.time() - t0) * 1000, 2)
        steps_log.append({
            "step": "generate_agents",
            "status": "completed",
            "duration_ms": t2_ms,
            "agents_created": len(ag.get("agents", [])),
        })

        # Step 3: Run simulation (all 6)
        t0 = time.time()
        sim = _http_post_with_retry(f"{BASE_URL}/api/simulate/run", {
            "workflow_id": wf_id,
            "scenarios": ["happy_path", "agent_failure", "wrong_decision",
                          "high_workload", "external_failure", "human_override"],
        })
        t3_ms = round((time.time() - t0) * 1000, 2)
        steps_log.append({
            "step": "run_simulation",
            "status": "completed",
            "duration_ms": t3_ms,
            "scenarios_passed": sim.get("overall_pass_rate", 0.0),
        })

        # Step 4: Governance check
        t0 = time.time()
        gov = _http_post_with_retry(f"{BASE_URL}/api/governance/check", {"workflow_id": wf_id})
        t4_ms = round((time.time() - t0) * 1000, 2)
        steps_log.append({
            "step": "run_governance_check",
            "status": "completed",
            "duration_ms": t4_ms,
            "kept_agents": len(gov.get("kept_agents", [])),
        })

        # Step 5: Risk & ROI analysis
        t0 = time.time()
        risk_res = _http_post_with_retry(f"{BASE_URL}/api/risk/analyze", {"workflow_id": wf_id})
        roi_res = _http_post_with_retry(f"{BASE_URL}/api/roi/analyze", {"workflow_id": wf_id})
        t5_ms = round((time.time() - t0) * 1000, 2)
        steps_log.append({
            "step": "risk_and_roi_analysis",
            "status": "completed",
            "duration_ms": t5_ms,
            "overall_risk_score": risk_res.get("overall_score", 0),
            "expected_payback_months": roi_res.get("expected_case", {}).get("payback_months", 0),
        })

        # Step 6: Generate executive report
        t0 = time.time()
        report = _http_post_with_retry(f"{BASE_URL}/api/report/generate", {"workflow_id": wf_id})
        t6_ms = round((time.time() - t0) * 1000, 2)
        steps_log.append({"step": "generate_report", "status": "completed", "duration_ms": t6_ms})

        total_ms = round((time.time() - pipeline_start) * 1000, 2)

        return {
            "workflow_id": wf_id,
            "pipeline_summary": {
                "recommendation": report.get("deployment_recommendation", "GO"),
                "total_duration_ms": total_ms,
                "steps_completed": len(steps_log),
            },
            "stepwise_execution": steps_log,
            "audit_metadata": {
                "call_id": call_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "llm_provider": "Groq",
                "llm_model": settings.GROQ_MODEL,
                "orchestrate_integrated": bool(settings.ORCHESTRATE_INSTANCE_URL),
            },
            "executive_report": report,
            "pdf_download_url": f"{BASE_URL}/api/report/{wf_id}/pdf",
        }

    raise ValueError(f"Unknown MCP tool: {tool_name}")


# ── MCP Request Handler (JSON-RPC) ────────────────────────────────────────────

def handle_mcp_request(raw_msg: dict) -> dict:
    """Process incoming JSON-RPC MCP request and return response dict."""
    id_ = raw_msg.get("id")
    method = raw_msg.get("method", "")
    params = raw_msg.get("params", {})

    # ── Protocol Lifecycle ─────────────────────────────────────────────────
    if method == "initialize":
        return _ok(id_, {
            "protocolVersion": MCP_VERSION,
            "capabilities": {
                "tools": {},
                "resources": {},
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
        })

    if method == "initialized":
        return {}  # notification, no response required

    if method == "ping":
        return _ok(id_, {})

    # ── Tool Discovery & Invocations ───────────────────────────────────────
    if method == "tools/list":
        return _ok(id_, {"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        try:
            result = _dispatch_tool(tool_name, tool_args)
            return _ok(id_, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                "isError": False,
            })
        except Exception as exc:
            logger.error("MCP tool %s execution error: %s", tool_name, exc, exc_info=True)
            return _ok(id_, {
                "content": [{"type": "text", "text": f"Error executing tool '{tool_name}': {exc}"}],
                "isError": True,
            })

    # ── Resource Discovery & Read ──────────────────────────────────────────
    if method == "resources/list":
        return _ok(id_, {"resources": RESOURCES})

    if method == "resources/templates/list":
        return _ok(id_, {"resourceTemplates": RESOURCE_TEMPLATES})

    if method == "resources/read":
        uri = params.get("uri", "")
        if uri.startswith("compliance://snippets"):
            parts = uri.replace("compliance://snippets", "").strip("/").split("/")
            fw_filter = parts[0] if parts and parts[0] else None
            data = get_compliance_resources(framework_filter=fw_filter)
            return _ok(id_, {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(data, indent=2),
                    }
                ]
            })

        if uri.startswith("agents://registry"):
            parts = uri.replace("agents://registry", "").strip("/").split("/")
            agent_id = parts[0] if parts and parts[0] else None
            data = get_agent_registry_resources(agent_id_filter=agent_id)
            return _ok(id_, {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(data, indent=2),
                    }
                ]
            })

        return _err(id_, -32602, f"Unknown resource URI: {uri}")

    # ── Unknown Method ─────────────────────────────────────────────────────
    return _err(id_, -32601, f"Method not found: {method}")


# ── Stdio Transport Loop ──────────────────────────────────────────────────────

def run_stdio() -> None:
    """Main stdio transport loop for CLI / Cursor / Claude Desktop integration."""
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = handle_mcp_request(req)
            if res:  # Only output if not a notification
                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps(_err(None, -32700, "Parse error")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_stdio()
