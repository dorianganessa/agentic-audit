"""Tests for MCP server tools and risk checker."""

import httpx
from agentaudit import AgentAudit
from agentaudit_mcp.risk_checker import check_risk
from starlette.testclient import TestClient

import agentaudit_mcp.server as server_mod


def _wire_mcp_client(app, api_key: str):
    """Wire the MCP server's singleton client to a test app.

    Calls the real AgentAudit constructor so env var defaults, timeout,
    and base_url logic are exercised, then swaps the transport.
    """
    tc = TestClient(app)
    audit = AgentAudit(api_key=api_key, base_url=str(tc.base_url))
    audit._client = httpx.Client(
        transport=tc._transport,
        base_url=audit._base_url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=audit._client.timeout,
    )
    server_mod._client = audit
    return tc


# ── risk_checker (offline, no API needed) ────────────────────────────


def test_check_risk_low():
    """Low risk: simple echo command."""
    result = check_risk("shell_command", {"command": "echo hello"})
    assert result["risk_level"] == "low"
    assert result["pii_detected"] is False
    assert "dry-run" in result["note"]


def test_check_risk_high_prod():
    """High risk: command with 'prod' keyword."""
    result = check_risk("shell_command", {"command": "psql -h prod -c 'SELECT 1'"})
    assert result["risk_level"] == "high"


def test_check_risk_critical_rm():
    """Critical risk: rm -rf command."""
    result = check_risk("shell_command", {"command": "rm -rf /var/data"})
    assert result["risk_level"] == "critical"


def test_check_risk_medium_pii():
    """Medium risk: PII in data."""
    result = check_risk("access_record", {"email": "user@example.com"})
    assert result["risk_level"] == "medium"
    assert result["pii_detected"] is True
    assert "email" in result["pii_fields"]


def test_check_risk_critical_credentials():
    """Critical risk: credential indicators."""
    result = check_risk("shell_command", {"command": "export API_KEY=sk_live_abc123"})
    assert result["risk_level"] == "critical"


# ── check_action_risk MCP tool ───────────────────────────────────────


def test_mcp_check_action_risk():
    """MCP tool check_action_risk runs risk checker."""
    from agentaudit_mcp.server import check_action_risk

    result = check_action_risk(
        action="shell_command",
        data={"command": "psql -h prod -c 'SELECT 1'"},
    )
    assert result["risk_level"] == "high"
    assert "dry-run" in result["note"]


# ── get_my_audit_events MCP tool ─────────────────────────────────────


def test_mcp_get_my_audit_events(app, api_key_raw):
    """MCP tool get_my_audit_events returns events via SDK."""
    from agentaudit_mcp.server import get_my_audit_events

    tc = _wire_mcp_client(app, api_key_raw)
    headers = {"Authorization": f"Bearer {api_key_raw}"}

    tc.put("/v1/org/policy", json={"logging_level": "full"}, headers=headers)

    # Count before
    before = tc.get("/v1/events", headers=headers).json()["total"]

    tc.post(
        "/v1/events",
        json={"agent_id": "mcp-test", "action": "shell_command", "data": {"command": "ls"}},
        headers=headers,
    )

    try:
        result = get_my_audit_events(limit=10)
        assert result["total"] == before + 1
        assert result["events"][0]["action"] == "shell_command"
        assert result["events"][0]["data"]["command"] == "ls"
    finally:
        server_mod._client = None


def test_mcp_get_my_audit_events_filter_action(app, api_key_raw):
    """get_my_audit_events filters by action."""
    from agentaudit_mcp.server import get_my_audit_events

    tc = _wire_mcp_client(app, api_key_raw)
    headers = {"Authorization": f"Bearer {api_key_raw}"}

    tc.put("/v1/org/policy", json={"logging_level": "full"}, headers=headers)

    tc.post(
        "/v1/events",
        json={"agent_id": "mcp-test", "action": "shell_command", "data": {"command": "ls"}},
        headers=headers,
    )
    tc.post(
        "/v1/events",
        json={"agent_id": "mcp-test", "action": "file_read", "data": {"file_path": "/tmp/x"}},
        headers=headers,
    )

    try:
        result = get_my_audit_events(action="file_read", limit=10)
        assert result["total"] >= 1
        for event in result["events"]:
            assert event["action"] == "file_read"
    finally:
        server_mod._client = None


def test_mcp_get_my_audit_events_with_session_id(app, api_key_raw, monkeypatch):
    """get_my_audit_events uses AGENTAUDIT_SESSION_ID to scope queries."""
    from agentaudit_mcp.server import get_my_audit_events

    tc = _wire_mcp_client(app, api_key_raw)
    headers = {"Authorization": f"Bearer {api_key_raw}"}

    tc.put("/v1/org/policy", json={"logging_level": "full"}, headers=headers)

    tc.post(
        "/v1/events",
        json={
            "agent_id": "mcp-test",
            "action": "shell_command",
            "data": {"command": "ls"},
            "context": {"session_id": "sess_A"},
        },
        headers=headers,
    )
    tc.post(
        "/v1/events",
        json={
            "agent_id": "mcp-test",
            "action": "file_read",
            "data": {"file_path": "/tmp/x"},
            "context": {"session_id": "sess_B"},
        },
        headers=headers,
    )

    try:
        monkeypatch.setenv("AGENTAUDIT_SESSION_ID", "sess_A")
        result = get_my_audit_events(limit=50)
        assert result["total"] >= 1
        # Verify sess_B events are excluded — sess_B only has file_read
        actions = [e["action"] for e in result["events"]]
        assert "file_read" not in actions, "sess_B event leaked through session filter"
        assert "shell_command" in actions
    finally:
        server_mod._client = None


# ── get_session_risk_summary MCP tool ────────────────────────────────


def test_mcp_get_session_risk_summary(app, api_key_raw):
    """get_session_risk_summary returns aggregate stats."""
    from agentaudit_mcp.server import get_session_risk_summary

    tc = _wire_mcp_client(app, api_key_raw)
    headers = {"Authorization": f"Bearer {api_key_raw}"}

    tc.put("/v1/org/policy", json={"logging_level": "full"}, headers=headers)

    # Seed specific events so we can assert exact counts
    tc.post(
        "/v1/events",
        json={"agent_id": "mcp-test", "action": "shell_command", "data": {"command": "ls"}},
        headers=headers,
    )
    tc.post(
        "/v1/events",
        json={
            "agent_id": "mcp-test",
            "action": "shell_command",
            "data": {"command": "psql -h prod -c 'SELECT 1'"},
        },
        headers=headers,
    )

    try:
        result = get_session_risk_summary()
        assert result["total_events"] >= 2
        assert isinstance(result["by_risk_level"], dict)
        assert "low" in result["by_risk_level"]
        # The prod command should produce at least one high-risk event
        assert result["by_risk_level"].get("high", 0) >= 1
    finally:
        server_mod._client = None


# ── Tool registration ────────────────────────────────────────────────


def test_mcp_tools_registered():
    """All 3 MCP tools are registered on the FastMCP server."""
    from agentaudit_mcp.server import server

    tool_names = [t.name for t in server._tool_manager.list_tools()]
    assert "get_my_audit_events" in tool_names
    assert "get_session_risk_summary" in tool_names
    assert "check_action_risk" in tool_names
