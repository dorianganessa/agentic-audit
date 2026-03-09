"""Tests for MCP server tools and risk checker."""

from agentaudit_mcp.risk_checker import check_risk


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


def test_mcp_get_my_audit_events(app, api_key_raw):
    """MCP tool get_my_audit_events returns events via SDK."""
    import httpx
    from agentaudit_mcp.server import get_my_audit_events
    from starlette.testclient import TestClient

    tc = TestClient(app)

    # Set full policy so events are stored
    tc.put(
        "/v1/org/policy",
        json={"logging_level": "full"},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )

    # Create test events
    tc.post(
        "/v1/events",
        json={"agent_id": "mcp-test", "action": "shell_command", "data": {"command": "ls"}},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )

    # Patch the MCP client to use our test transport
    import agentaudit_mcp.server as server_mod

    audit = server_mod.AgentAudit.__new__(server_mod.AgentAudit)
    audit._api_key = api_key_raw
    audit._base_url = str(tc.base_url).rstrip("/")
    audit._client = httpx.Client(
        transport=tc._transport,
        base_url=audit._base_url,
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    server_mod._client = audit

    try:
        result = get_my_audit_events(limit=10)
        assert "events" in result
        assert "total" in result
        assert result["total"] >= 1
        assert result["events"][0]["action"] == "shell_command"
    finally:
        server_mod._client = None


def test_mcp_get_session_risk_summary(app, api_key_raw):
    """MCP tool get_session_risk_summary returns stats."""
    import httpx
    from agentaudit_mcp.server import get_session_risk_summary
    from starlette.testclient import TestClient

    tc = TestClient(app)

    # Set full policy
    tc.put(
        "/v1/org/policy",
        json={"logging_level": "full"},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )

    # Create a test event
    tc.post(
        "/v1/events",
        json={"agent_id": "mcp-test", "action": "shell_command", "data": {"command": "ls"}},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )

    import agentaudit_mcp.server as server_mod

    audit = server_mod.AgentAudit.__new__(server_mod.AgentAudit)
    audit._api_key = api_key_raw
    audit._base_url = str(tc.base_url).rstrip("/")
    audit._client = httpx.Client(
        transport=tc._transport,
        base_url=audit._base_url,
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    server_mod._client = audit

    try:
        result = get_session_risk_summary()
        assert "total_events" in result
        assert "by_risk_level" in result
        assert result["total_events"] >= 1
    finally:
        server_mod._client = None


def test_mcp_check_action_risk():
    """MCP tool check_action_risk runs risk checker."""
    from agentaudit_mcp.server import check_action_risk

    result = check_action_risk(
        action="shell_command",
        data={"command": "psql -h prod -c 'SELECT 1'"},
    )
    assert result["risk_level"] == "high"
    assert "dry-run" in result["note"]
