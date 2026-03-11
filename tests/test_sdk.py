import httpx
import pytest
from agentaudit import AgentAudit, AsyncAgentAudit, AuditEvent, AuthenticationError
from starlette.testclient import TestClient


def _make_sdk_client(app, api_key: str) -> AgentAudit:
    """Create an AgentAudit SDK client wired to a test app.

    Calls the real constructor so env var resolution, defaults, and timeout
    logic are exercised, then swaps the transport for the test app.
    """
    tc = TestClient(app)
    audit = AgentAudit(api_key=api_key, base_url=str(tc.base_url))
    # Replace only the transport so the constructor's client setup is tested
    audit._client = httpx.Client(
        transport=tc._transport,
        base_url=audit._base_url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=audit._client.timeout,
    )
    return audit


def _make_async_sdk_client(app, api_key: str) -> AsyncAgentAudit:
    """Create an AsyncAgentAudit SDK client wired to a test app.

    Calls the real constructor so env var resolution, defaults, and timeout
    logic are exercised, then swaps the transport for the test app.
    """
    audit = AsyncAgentAudit(api_key=api_key, base_url="http://testserver")
    # Replace only the transport for ASGI testing
    audit._client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=audit._base_url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=audit._client.timeout,
    )
    return audit


def test_sdk_log_success(app, api_key_raw):
    """SDK log() with valid payload creates an event."""
    audit = _make_sdk_client(app, api_key_raw)

    event = audit.log(
        agent_id="booking-agent-v2",
        action="access_customer_record",
        data={"customer_id": "usr_8291", "fields_accessed": ["email", "phone"]},
        reasoning="Customer requested booking modification via chat",
    )

    assert isinstance(event, AuditEvent)
    assert len(event.id) == 26  # ULID
    assert event.agent_id == "booking-agent-v2"
    assert event.action == "access_customer_record"
    assert event.data["customer_id"] == "usr_8291"
    assert event.reasoning == "Customer requested booking modification via chat"
    assert event.risk_level == "low"
    assert event.pii_detected is False


def test_sdk_log_with_context(app, api_key_raw):
    """SDK log() with context for coding agents."""
    audit = _make_sdk_client(app, api_key_raw)

    event = audit.log(
        agent_id="claude-code",
        action="shell_command",
        data={
            "command": "psql -h prod-db.internal -c 'SELECT email FROM users'",
            "exit_code": 0,
        },
        context={
            "tool": "claude_code",
            "session_id": "sess_29xKm",
            "developer": "adriano@example.com",
        },
    )

    assert event.agent_id == "claude-code"
    assert event.data["command"].startswith("psql")
    assert event.context["developer"] == "adriano@example.com"


def test_sdk_log_no_auth(app):
    """SDK log() without valid auth raises AuthenticationError."""
    audit = _make_sdk_client(app, "aa_live_invalid0000000000000000000")

    with pytest.raises(AuthenticationError) as exc_info:
        audit.log(agent_id="test", action="test_action")
    assert exc_info.value.status_code in (401, 403)


# ── AsyncAgentAudit tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_sdk_log_success(app, api_key_raw):
    """Async SDK log() with valid payload creates an event."""
    audit = _make_async_sdk_client(app, api_key_raw)

    try:
        event = await audit.log(
            agent_id="async-agent",
            action="access_customer_record",
            data={"customer_id": "usr_999", "fields_accessed": ["email"]},
            reasoning="Async test event",
        )

        assert isinstance(event, AuditEvent)
        assert len(event.id) == 26  # ULID
        assert event.agent_id == "async-agent"
        assert event.action == "access_customer_record"
        assert event.data["customer_id"] == "usr_999"
        assert event.reasoning == "Async test event"
        assert event.risk_level == "low"
    finally:
        await audit.close()


@pytest.mark.asyncio
async def test_async_sdk_log_with_context(app, api_key_raw):
    """Async SDK log() with context."""
    audit = _make_async_sdk_client(app, api_key_raw)

    try:
        event = await audit.log(
            agent_id="claude-code",
            action="shell_command",
            data={"command": "psql -h prod-db -c 'SELECT email FROM users'"},
            context={"session_id": "sess_async", "tool": "claude_code"},
        )

        assert event.agent_id == "claude-code"
        assert event.data["command"].startswith("psql")
        assert event.context["session_id"] == "sess_async"
    finally:
        await audit.close()


@pytest.mark.asyncio
async def test_async_sdk_log_no_auth(app):
    """Async SDK log() without valid auth raises AuthenticationError."""
    audit = _make_async_sdk_client(app, "aa_live_invalid0000000000000000000")

    try:
        with pytest.raises(AuthenticationError) as exc_info:
            await audit.log(agent_id="test", action="test_action")
        assert exc_info.value.status_code in (401, 403)
    finally:
        await audit.close()


@pytest.mark.asyncio
async def test_async_sdk_context_manager(app, api_key_raw):
    """Async SDK works as an async context manager."""
    async with _make_async_sdk_client(app, api_key_raw) as audit:
        event = await audit.log(
            agent_id="ctx-manager-test",
            action="file_read",
            data={"file_path": "/tmp/test.txt"},
        )
        assert event.action == "file_read"
