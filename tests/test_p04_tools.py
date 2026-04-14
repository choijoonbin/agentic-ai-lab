"""
P04 MCP Server — Tool Tests

Tests the connector model:
  Read    : always succeed, no side effects
  Write   : succeed for analyst/admin, fail for viewer
  Action  : fail without approval_granted, succeed with it
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "mcp_server"))

import pytest
from tools.read_connectors   import web_search, get_metrics, crm_lookup, finance_query
from tools.write_connectors  import db_write, create_ticket
from tools.action_connectors import send_email
from tools.registry          import get_tool, list_tools


# ─── Read connectors ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_web_search_returns_results():
    result = await web_search({"query": "enterprise AI"}, {})
    assert result["connector_type"] == "read"
    assert len(result["results"]) > 0


@pytest.mark.asyncio
async def test_get_metrics_contains_cpu():
    result = await get_metrics({}, {})
    assert "cpu_usage_pct" in result["metrics"]
    assert result["connector_type"] == "read"


@pytest.mark.asyncio
async def test_crm_lookup_returns_customer():
    result = await crm_lookup({"query": "ACME"}, {"tenant_id": "acme"})
    assert "customer" in result
    assert result["connector_type"] == "read"


@pytest.mark.asyncio
async def test_finance_query_returns_revenue():
    result = await finance_query({"query": "Q1"}, {})
    assert "revenue" in result["data"]


# ─── Write connectors ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_db_write_viewer_denied():
    with pytest.raises(PermissionError):
        await db_write({"table": "users"}, {"role": "viewer"})


@pytest.mark.asyncio
async def test_db_write_analyst_allowed():
    result = await db_write({"table": "users"}, {"role": "analyst", "trace_id": "t1"})
    assert result["status"] == "written"
    assert result["connector_type"] == "write"


@pytest.mark.asyncio
async def test_create_ticket_succeeds():
    result = await create_ticket({"subject": "login issue", "priority": "high"}, {})
    assert result["status"] == "created"
    assert result["ticket_id"].startswith("TICK-")


# ─── Action connectors ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_email_without_approval_raises():
    with pytest.raises(PermissionError):
        await send_email(
            {"to": "mgr@acme.com", "subject": "alert"},
            {"approval_granted": False},
        )


@pytest.mark.asyncio
async def test_send_email_with_approval_succeeds():
    result = await send_email(
        {"to": "mgr@acme.com", "subject": "Q1 report"},
        {"approval_granted": True, "trace_id": "trace-abc"},
    )
    assert result["status"] == "sent"
    assert result["connector_type"] == "action"


# ─── Registry ──────────────────────────────────────────────────────────────

def test_registry_contains_all_tools():
    tools = list_tools()
    for name in ["web_search", "get_metrics", "crm_lookup", "finance_query",
                 "db_write", "create_ticket", "send_email"]:
        assert name in tools, f"Tool '{name}' missing from registry"


def test_registry_returns_none_for_unknown():
    assert get_tool("nonexistent_tool") is None
