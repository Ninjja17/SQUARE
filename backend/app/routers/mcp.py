"""
FastAPI Router for Model Context Protocol (MCP).

Exposes:
  - GET  /api/mcp/sse            : Server-Sent Events stream for MCP connections
  - POST /api/mcp/messages       : JSON-RPC message endpoint for SSE transport
  - GET  /api/mcp/tools          : REST endpoint listing registered MCP tools
  - GET  /api/mcp/resources      : REST endpoint listing available MCP resources
  - POST /api/mcp/tools/call     : Direct REST tool execution with API key security
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.mcp_server import (
    RESOURCES,
    RESOURCE_TEMPLATES,
    TOOLS,
    get_agent_registry_resources,
    get_compliance_resources,
    handle_mcp_request,
    _dispatch_tool,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

# Simple in-memory queue store for active SSE sessions
_sse_sessions: dict[str, asyncio.Queue[str]] = {}


def verify_mcp_api_key(x_mcp_api_key: str | None = Header(None)) -> None:
    """Verify optional API key for security when configured."""
    if settings.MCP_API_KEY and x_mcp_api_key != settings.MCP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid or missing X-MCP-API-Key header"},
        )


@router.get("/tools", summary="List MCP Tools")
async def list_tools():
    """List all registered MCP tools and their strict JSON schemas."""
    return {"tools": TOOLS}


@router.get("/resources", summary="List MCP Resources")
async def list_resources():
    """List all available MCP resources and templates."""
    return {
        "resources": RESOURCES,
        "resourceTemplates": RESOURCE_TEMPLATES,
    }


@router.get("/resources/compliance", summary="Read Compliance Resources")
async def read_compliance(
    framework: str | None = Query(None, description="Framework filter (e.g. GDPR, HIPAA, PCI-DSS)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    """Query normalized and paginated compliance RAG snippets."""
    return get_compliance_resources(framework_filter=framework, page=page, page_size=page_size)


@router.get("/resources/agents", summary="Read Agent Registry Resources")
async def read_agent_registry(
    agent_id: str | None = Query(None, description="Specific agent registry ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    """Query normalized and paginated Common Agent Registry templates."""
    return get_agent_registry_resources(agent_id_filter=agent_id, page=page, page_size=page_size)


@router.post("/tools/call", summary="Execute MCP Tool")
async def call_tool(
    name: str = Query(..., description="Tool name to execute"),
    payload: dict[str, Any] = None,
    _auth: None = Depends(verify_mcp_api_key),
):
    """Execute an MCP tool with API key security and return structured result."""
    payload = payload or {}
    try:
        result = await asyncio.to_thread(_dispatch_tool, name, payload)
        return {
            "success": True,
            "tool": name,
            "result": result,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_TOOL", "message": str(exc)})
    except Exception as exc:
        logger.error("Tool execution failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail={"code": "TOOL_EXECUTION_ERROR", "message": str(exc)})


@router.post("/messages", summary="Post MCP JSON-RPC Message")
async def post_message(
    request: Request,
    _auth: None = Depends(verify_mcp_api_key),
):
    """JSON-RPC message processing endpoint for MCP HTTP clients."""
    try:
        raw_msg = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail={"code": "PARSE_ERROR", "message": "Invalid JSON"})

    response = await asyncio.to_thread(handle_mcp_request, raw_msg)
    return response


@router.get("/sse", summary="MCP Server-Sent Events Stream")
async def sse_endpoint(request: Request):
    """Server-Sent Events endpoint for streaming MCP messages."""

    async def event_generator():
        yield "event: endpoint\ndata: /api/mcp/messages\n\n"
        while True:
            if await request.is_disconnected():
                break
            await asyncio.sleep(15)
            yield "event: ping\ndata: {}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
