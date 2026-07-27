"""
SQUARE MCP Server — exposes SQUARE's full pipeline as Model Context Protocol tools.

Any MCP-compatible AI (Claude, Cursor, IBM Bob, etc.) can:
  - analyze_workflow      : parse a workflow description
  - generate_agents       : build an AI agent team for a workflow
  - run_simulation        : stress-test agents across scenarios
  - run_governance_check  : validate agent health + keep/dismiss/promote
  - analyze_risk          : score risk with RAG-grounded compliance context
  - analyze_roi           : calculate ROI / payback period
  - generate_report       : produce the full Executive Readiness Report

Run standalone:
    python -m app.mcp_server          # stdio transport (default)
    python -m app.mcp_server --sse    # SSE transport on :8001

Or add to an MCP config:
    {
      "mcpServers": {
        "square": {
          "command": "python",
          "args": ["-m", "app.mcp_server"],
          "cwd": "<path-to-square-backend>"
        }
      }
    }
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)


# ── Tiny MCP protocol implementation (no external mcp package required) ───────
# Implements the JSON-RPC 2.0 + MCP 2024-11-05 spec over stdio.

MCP_VERSION = "2024-11-05"
SERVER_NAME = "square"
SERVER_VERSION = "1.0.0"


def _ok(id_: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


# ── Tool registry ─────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "analyze_workflow",
        "description": (
            "Parse a plain-English business workflow description into structured tasks, "
            "stakeholders, automation candidates, and bottlenecks. "
            "Returns a workflow_id that all subsequent tools require."
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
                    "description": "Expected number of workflow executions per month.",
                },
            },
            "required": ["description", "industry", "monthly_volume"],
        },
    },
    {
        "name": "generate_agents",
        "description": (
            "Generate an AI agent team for a previously analyzed workflow. "
            "Checks the Common Agent Registry for reusable agents first, "
            "then creates new agents as needed. "
            "Returns an array of agents with source (reused|new), metrics, and responsibilities."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string", "description": "ID returned by analyze_workflow."},
            },
            "required": ["workflow_id"],
        },
    },
    {
        "name": "run_simulation",
        "description": (
            "Stress-test the agent team across one or more scenarios: "
            "happy_path, agent_failure, wrong_decision, high_workload, "
            "external_failure, human_override. "
            "Returns per-scenario pass/warning/critical status with success rates and notes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string", "description": "ID returned by analyze_workflow."},
                "scenarios": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["happy_path", "agent_failure", "wrong_decision",
                                 "high_workload", "external_failure", "human_override"],
                    },
                    "description": "Scenarios to simulate. Defaults to all 6 if omitted.",
                },
            },
            "required": ["workflow_id"],
        },
    },
    {
        "name": "run_governance_check",
        "description": (
            "Run the Core Control Agent governance check: validates every agent was created, "
            "checks health, and decides Keep / Dismiss / Promote to Registry for each agent. "
            "Returns a per-agent governance table and a summary."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string", "description": "ID returned by analyze_workflow."},
            },
            "required": ["workflow_id"],
        },
    },
    {
        "name": "analyze_risk",
        "description": (
            "Score security, compliance, operational, data quality, and agent dependency risk (0–100). "
            "Uses RAG-grounded compliance snippets (GDPR, HIPAA, PCI-DSS, SOX, FERPA, etc.) "
            "for the industry. Returns an overall risk score, category breakdown, "
            "and specific recommendations."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string", "description": "ID returned by analyze_workflow."},
            },
            "required": ["workflow_id"],
        },
    },
    {
        "name": "analyze_roi",
        "description": (
            "Calculate annual savings, implementation cost, FTE reduction, payback period, "
            "and Year 1 ROI for the workflow automation. "
            "Includes sensitivity analysis (best/expected/worst case)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string", "description": "ID returned by analyze_workflow."},
            },
            "required": ["workflow_id"],
        },
    },
    {
        "name": "generate_report",
        "description": (
            "Generate the full Executive Readiness Report combining risk, ROI, governance, "
            "and deployment advice. Returns automation score, risk report, ROI report, "
            "3-phase deployment timeline, and a GO / PILOT_FIRST / NEEDS_CHANGES recommendation. "
            "Must call analyze_risk and analyze_roi before this tool."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string", "description": "ID returned by analyze_workflow."},
            },
            "required": ["workflow_id"],
        },
    },
    {
        "name": "full_pipeline",
        "description": (
            "Run the complete SQUARE pipeline end-to-end in one call: "
            "analyze_workflow → generate_agents → run_simulation (all 6 scenarios) → "
            "run_governance_check → analyze_risk → analyze_roi → generate_report. "
            "Returns the final Executive Readiness Report with the workflow_id for PDF download."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Plain-English workflow description.",
                },
                "industry": {
                    "type": "string",
                    "enum": ["HR", "BFSI", "Retail", "Manufacturing", "Telecom",
                             "Healthcare", "Education", "Government", "Other"],
                },
                "monthly_volume": {"type": "integer"},
            },
            "required": ["description", "industry", "monthly_volume"],
        },
    },
]


# ── HTTP client helper ────────────────────────────────────────────────────────

import urllib.request
import urllib.error


def _http_post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def _http_get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode())


# ── Tool dispatch ─────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:8000"


def _dispatch(tool_name: str, args: dict) -> Any:
    """Call the SQUARE FastAPI backend and return the result."""

    if tool_name == "analyze_workflow":
        return _http_post(f"{BASE_URL}/api/workflow/analyze", {
            "description":    args["description"],
            "industry":       args["industry"],
            "monthly_volume": args["monthly_volume"],
        })

    if tool_name == "generate_agents":
        return _http_post(f"{BASE_URL}/api/agents/generate", {
            "workflow_id": args["workflow_id"],
        })

    if tool_name == "run_simulation":
        scenarios = args.get("scenarios") or [
            "happy_path", "agent_failure", "wrong_decision",
            "high_workload", "external_failure", "human_override",
        ]
        return _http_post(f"{BASE_URL}/api/simulate/run", {
            "workflow_id": args["workflow_id"],
            "scenarios": scenarios,
        })

    if tool_name == "run_governance_check":
        return _http_post(f"{BASE_URL}/api/governance/check", {
            "workflow_id": args["workflow_id"],
        })

    if tool_name == "analyze_risk":
        return _http_post(f"{BASE_URL}/api/risk/analyze", {
            "workflow_id": args["workflow_id"],
        })

    if tool_name == "analyze_roi":
        return _http_post(f"{BASE_URL}/api/roi/analyze", {
            "workflow_id": args["workflow_id"],
        })

    if tool_name == "generate_report":
        return _http_post(f"{BASE_URL}/api/report/generate", {
            "workflow_id": args["workflow_id"],
        })

    if tool_name == "full_pipeline":
        # Step 1 — workflow
        wf = _http_post(f"{BASE_URL}/api/workflow/analyze", {
            "description":    args["description"],
            "industry":       args["industry"],
            "monthly_volume": args["monthly_volume"],
        })
        wf_id = wf["workflow_id"]

        # Step 2 — agents
        _http_post(f"{BASE_URL}/api/agents/generate", {"workflow_id": wf_id})

        # Step 3 — simulation (all 6)
        _http_post(f"{BASE_URL}/api/simulate/run", {
            "workflow_id": wf_id,
            "scenarios": ["happy_path", "agent_failure", "wrong_decision",
                          "high_workload", "external_failure", "human_override"],
        })

        # Step 4 — governance
        _http_post(f"{BASE_URL}/api/governance/check", {"workflow_id": wf_id})

        # Step 5 — risk + ROI in parallel (sequential here for simplicity)
        _http_post(f"{BASE_URL}/api/risk/analyze", {"workflow_id": wf_id})
        _http_post(f"{BASE_URL}/api/roi/analyze",  {"workflow_id": wf_id})

        # Step 6 — report
        report = _http_post(f"{BASE_URL}/api/report/generate", {"workflow_id": wf_id})
        report["pdf_download_url"] = f"{BASE_URL}/api/report/{wf_id}/pdf"
        return report

    raise ValueError(f"Unknown tool: {tool_name}")


# ── MCP stdio loop ────────────────────────────────────────────────────────────

def _write(msg: dict) -> None:
    line = json.dumps(msg)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _handle(raw: str) -> None:
    try:
        req = json.loads(raw)
    except json.JSONDecodeError:
        _write(_err(None, -32700, "Parse error"))
        return

    id_ = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {})

    # ── Lifecycle ──────────────────────────────────────────────────────────
    if method == "initialize":
        _write(_ok(id_, {
            "protocolVersion": MCP_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }))
        return

    if method == "initialized":
        return  # notification, no response

    if method == "ping":
        _write(_ok(id_, {}))
        return

    # ── Tool discovery ─────────────────────────────────────────────────────
    if method == "tools/list":
        _write(_ok(id_, {"tools": TOOLS}))
        return

    # ── Tool call ──────────────────────────────────────────────────────────
    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        try:
            result = _dispatch(tool_name, tool_args)
            _write(_ok(id_, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                "isError": False,
            }))
        except urllib.error.URLError as exc:
            _write(_ok(id_, {
                "content": [{"type": "text", "text": f"SQUARE backend unreachable: {exc}"}],
                "isError": True,
            }))
        except Exception as exc:
            logger.error("Tool %s failed: %s", tool_name, exc)
            _write(_ok(id_, {
                "content": [{"type": "text", "text": f"Error: {exc}"}],
                "isError": True,
            }))
        return

    # ── Unknown method ─────────────────────────────────────────────────────
    _write(_err(id_, -32601, f"Method not found: {method}"))


def run_stdio() -> None:
    """Main stdio loop — reads one JSON-RPC message per line."""
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if line:
            _handle(line)


if __name__ == "__main__":
    run_stdio()
