"""Tests for production-readiness features."""

import json

from agentaudit_hook.buffer import buffer_event, flush_buffer

# ── Health check with DB status ──────────────────────────────────────


def test_health_returns_db_status(client):
    """Health endpoint reports database connectivity."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert "version" in body


# ── Request body size limits ─────────────────────────────────────────


def test_ingest_oversized_data_rejected(client, api_key_raw, monkeypatch):
    """Event with data field exceeding max_event_data_bytes is rejected with 413."""
    from agentaudit_api.api import events as events_mod
    from agentaudit_api.config import get_settings

    original = get_settings

    def patched_settings():
        s = original()
        s.max_event_data_bytes = 100  # very small limit
        return s

    monkeypatch.setattr(events_mod, "get_settings", patched_settings)

    resp = client.post(
        "/v1/events",
        json={
            "agent_id": "test",
            "action": "shell_command",
            "data": {"command": "x" * 200},
        },
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 413
    assert "data field too large" in resp.json()["detail"]


def test_ingest_oversized_context_rejected(client, api_key_raw, monkeypatch):
    """Event with context field exceeding max_event_context_bytes is rejected."""
    from agentaudit_api.api import events as events_mod
    from agentaudit_api.config import get_settings

    original = get_settings

    def patched_settings():
        s = original()
        s.max_event_context_bytes = 50
        return s

    monkeypatch.setattr(events_mod, "get_settings", patched_settings)

    resp = client.post(
        "/v1/events",
        json={
            "agent_id": "test",
            "action": "shell_command",
            "data": {"command": "ls"},
            "context": {"big_field": "y" * 200},
        },
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 413
    assert "context field too large" in resp.json()["detail"]


def test_ingest_normal_size_accepted(client, api_key_raw):
    """Normal-sized event is accepted (sanity check for size limits)."""
    resp = client.post(
        "/v1/events",
        json={
            "agent_id": "test",
            "action": "shell_command",
            "data": {"command": "echo hello"},
        },
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 201


# ── API key rotation ─────────────────────────────────────────────────


def test_rotate_api_key(client, api_key_raw):
    """Rotating an API key returns a new key and deactivates the old one."""
    headers = {"Authorization": f"Bearer {api_key_raw}"}

    resp = client.post("/v1/org/api-keys/rotate", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "api_key" in body
    assert body["api_key"].startswith("aa_live_")
    assert body["api_key"] != api_key_raw
    assert "previous_key_id" in body

    # Old key should no longer work
    resp_old = client.get("/v1/events", headers=headers)
    assert resp_old.status_code == 401

    # New key should work
    new_headers = {"Authorization": f"Bearer {body['api_key']}"}
    resp_new = client.get("/v1/events", headers=new_headers)
    assert resp_new.status_code == 200


# ── Buffer flush ─────────────────────────────────────────────────────


def test_flush_buffer_sends_events(tmp_path, app, api_key_raw):
    """flush_buffer sends buffered events to the API and clears the file."""
    import httpx
    from agentaudit import AgentAudit
    from starlette.testclient import TestClient

    tc = TestClient(app)
    tc.put(
        "/v1/org/policy",
        json={"logging_level": "full"},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )

    buf = tmp_path / "buffer.jsonl"

    # Buffer two events
    buffer_event(
        {"agent_id": "test", "action": "shell_command", "data": {"command": "ls"}},
        buffer_path=buf,
    )
    buffer_event(
        {"agent_id": "test", "action": "file_read", "data": {"file_path": "/tmp/x"}},
        buffer_path=buf,
    )
    assert len(buf.read_text().strip().splitlines()) == 2

    # Create SDK client wired to test app
    audit = AgentAudit(api_key=api_key_raw, base_url=str(tc.base_url))
    audit._client = httpx.Client(
        transport=tc._transport,
        base_url=str(tc.base_url),
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )

    flushed = flush_buffer(audit, buffer_path=buf)
    assert flushed == 2
    assert not buf.exists()


def test_flush_buffer_keeps_failed(tmp_path):
    """Events that fail to send remain in the buffer."""
    buf = tmp_path / "buffer.jsonl"
    buffer_event(
        {"agent_id": "test", "action": "shell_command", "data": {"command": "ls"}},
        buffer_path=buf,
    )

    class FakeClient:
        def log(self, **kwargs):
            raise ConnectionError("API down")

    flushed = flush_buffer(FakeClient(), buffer_path=buf)
    assert flushed == 0
    assert len(buf.read_text().strip().splitlines()) == 1


def test_flush_empty_buffer(tmp_path):
    """flush_buffer with no file returns 0."""
    buf = tmp_path / "nonexistent.jsonl"
    assert flush_buffer(None, buffer_path=buf) == 0


# ── Retention purge ──────────────────────────────────────────────────


def test_purge_expired_events(client, api_key_raw, db_url):
    """purge_expired_events deletes old events and keeps recent ones."""
    from datetime import UTC, datetime, timedelta

    from agentaudit_api.models.event import AuditEvent
    from agentaudit_api.services.retention import purge_expired_events
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as SASession

    headers = {"Authorization": f"Bearer {api_key_raw}"}

    client.put(
        "/v1/org/policy",
        json={"logging_level": "full"},
        headers=headers,
    )

    # Create a recent event via API
    client.post(
        "/v1/events",
        json={"agent_id": "test", "action": "shell_command", "data": {"command": "ls"}},
        headers=headers,
    )

    # Manually insert an old event directly in the DB
    engine = create_engine(db_url)
    with SASession(engine) as session:
        # Get the API key ID
        from agentaudit_api.models.api_key import ApiKey, hash_api_key

        key_hash = hash_api_key(api_key_raw)
        ak = session.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()

        old_event = AuditEvent(
            agent_id="test",
            action="file_read",
            data={"file_path": "/old"},
            context={},
            api_key_id=ak.id,
            risk_level="low",
            created_at=datetime.now(UTC) - timedelta(days=200),
        )
        session.add(old_event)
        session.commit()

    # Verify we have 2 events
    resp = client.get("/v1/events", headers=headers)
    assert resp.json()["total"] == 2

    # Purge with 90-day retention
    import agentaudit_api.database as db_mod

    original_engine = db_mod._engine
    db_mod._engine = engine
    try:
        deleted = purge_expired_events(retention_days=90)
    finally:
        db_mod._engine = original_engine

    assert deleted == 1

    # Only the recent event should remain
    resp = client.get("/v1/events", headers=headers)
    assert resp.json()["total"] == 1


def test_purge_zero_retention_skips(client, api_key_raw, db_url):
    """retention_days=0 means keep everything."""
    import agentaudit_api.database as db_mod
    from agentaudit_api.services.retention import purge_expired_events
    from sqlalchemy import create_engine

    engine = create_engine(db_url)
    original_engine = db_mod._engine
    db_mod._engine = engine
    try:
        deleted = purge_expired_events(retention_days=0)
    finally:
        db_mod._engine = original_engine

    assert deleted == 0


# ── Structured logging ───────────────────────────────────────────────


def test_json_log_formatter():
    """JsonLogFormatter produces valid JSON with expected fields."""
    import logging

    from agentaudit_api.config import JsonLogFormatter

    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["level"] == "INFO"
    assert parsed["msg"] == "hello world"
    assert parsed["logger"] == "test"
    assert "ts" in parsed
