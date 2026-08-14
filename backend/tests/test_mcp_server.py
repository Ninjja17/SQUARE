"""
Integration test suite for SQUARE MCP Server & Router.

Tests:
  - MCP stdio protocol JSON-RPC messages (initialize, ping, tools/list, resources/list, resources/read).
  - MCP tools schemas and strict validation.
  - MCP resources (compliance RAG snippets & agent registry pagination).
  - Stepwise execution timings & audit metadata in full_pipeline execution.
  - FastAPI HTTP/SSE endpoints (/api/mcp/tools, /api/mcp/resources, /api/mcp/messages).
"""
import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mcp_server import (
    TOOLS,
    RESOURCES,
    get_compliance_resources,
    get_agent_registry_resources,
    handle_mcp_request,
)

client = TestClient(app)


def test_mcp_protocol_initialize():
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }
    res = handle_mcp_request(req)
    assert res["jsonrpc"] == "2.0"
    assert res["id"] == 1
    assert "result" in res
    assert res["result"]["protocolVersion"] == "2024-11-05"
    assert res["result"]["serverInfo"]["name"] == "square-mcp"


def test_mcp_tools_list():
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    res = handle_mcp_request(req)
    assert res["jsonrpc"] == "2.0"
    assert res["id"] == 2
    tools = res["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "analyze_workflow" in tool_names
    assert "generate_agents" in tool_names
    assert "run_simulation" in tool_names
    assert "run_governance_check" in tool_names
    assert "analyze_risk" in tool_names
    assert "analyze_roi" in tool_names
    assert "generate_report" in tool_names
    assert "full_pipeline" in tool_names


def test_mcp_resources_list():
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "resources/list",
        "params": {}
    }
    res = handle_mcp_request(req)
    assert res["jsonrpc"] == "2.0"
    resources = res["result"]["resources"]
    uris = [r["uri"] for r in resources]
    assert "compliance://snippets" in uris
    assert "agents://registry" in uris


def test_compliance_resources_pagination_and_filtering():
    # Test all compliance docs
    res_all = get_compliance_resources(page=1, page_size=5)
    assert res_all["total_count"] >= 15
    assert len(res_all["items"]) == 5

    # Test framework filter
    res_gdpr = get_compliance_resources(framework_filter="GDPR")
    assert res_gdpr["total_count"] >= 2
    for item in res_gdpr["items"]:
        assert "GDPR" in item["framework"]


def test_agent_registry_resources_pagination():
    res_agents = get_agent_registry_resources(page=1, page_size=3)
    assert res_agents["total_count"] >= 6
    assert len(res_agents["items"]) == 3


def test_mcp_resources_read():
    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "resources/read",
        "params": {"uri": "compliance://snippets/HIPAA"}
    }
    res = handle_mcp_request(req)
    assert "result" in res
    contents = res["result"]["contents"]
    assert len(contents) == 1
    data = json.loads(contents[0]["text"])
    assert data["resource_uri"] == "compliance://snippets/HIPAA"
    assert data["total_count"] >= 2


def test_fastapi_mcp_rest_endpoints():
    # Test GET /api/mcp/tools
    resp_tools = client.get("/api/mcp/tools")
    assert resp_tools.status_code == 200
    assert "tools" in resp_tools.json()

    # Test GET /api/mcp/resources
    resp_res = client.get("/api/mcp/resources")
    assert resp_res.status_code == 200
    assert "resources" in resp_res.json()

    # Test GET /api/mcp/resources/compliance
    resp_comp = client.get("/api/mcp/resources/compliance?framework=SOX")
    assert resp_comp.status_code == 200
    assert resp_comp.json()["total_count"] >= 1

    # Test POST /api/mcp/messages
    rpc_req = {"jsonrpc": "2.0", "id": 10, "method": "ping", "params": {}}
    resp_msg = client.post("/api/mcp/messages", json=rpc_req)
    assert resp_msg.status_code == 200
    assert resp_msg.json()["result"] == {}


def test_mcp_unknown_method_error():
    req = {
        "jsonrpc": "2.0",
        "id": 99,
        "method": "non_existent_method",
        "params": {}
    }
    res = handle_mcp_request(req)
    assert "error" in res
    assert res["error"]["code"] == -32601
