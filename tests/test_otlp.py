"""OTLP endpoint smoke tests — simulates Cowork sending events."""

import json


def _otlp_payload(*log_records, service_name="cowork"):
    """Build an ExportLogsServiceRequest with given log records."""
    return {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": service_name}},
                        {"key": "service.version", "value": {"stringValue": "1.0.0"}},
                    ]
                },
                "scopeLogs": [
                    {
                        "logRecords": list(log_records),
                    }
                ],
            }
        ]
    }


def _set_full_logging(client, api_key_raw):
    """Set logging_level to full so all events are persisted and GETable."""
    client.put(
        "/v1/org/policy",
        json={"logging_level": "full"},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )


def _log_record(event_name, **extra_attrs):
    """Build an OTLP log record with given event name and attributes."""
    attrs = [{"key": "event.name", "value": {"stringValue": event_name}}]
    for key, value in extra_attrs.items():
        if isinstance(value, bool):
            attrs.append({"key": key, "value": {"boolValue": value}})
        elif isinstance(value, int):
            attrs.append({"key": key, "value": {"intValue": str(value)}})
        elif isinstance(value, dict):
            attrs.append({"key": key, "value": {"stringValue": json.dumps(value)}})
        else:
            attrs.append({"key": key, "value": {"stringValue": str(value)}})
    return {"attributes": attrs}


# ── Basic ingestion ──────────────────────────────────────────────────


def test_otlp_tool_result_file_read(client, api_key_raw):
    """Cowork file read → file_read action."""
    payload = _otlp_payload(
        _log_record(
            "cowork.tool_result",
            **{
                "tool_name": "Read",
                "session.id": "sess_cowork_1",
                "success": True,
                "duration_ms": 42,
            },
        )
    )

    resp = client.post(
        "/v1/otlp/v1/logs",
        json=payload,
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] == 1
    assert body["events"][0]["action"] == "file_read"


def test_otlp_connector_access_google_drive(client, api_key_raw):
    """Cowork MCP Google Drive → connector_access with connector extracted."""
    _set_full_logging(client, api_key_raw)
    payload = _otlp_payload(
        _log_record(
            "cowork.tool_result",
            **{
                "tool_name": "mcp__google_drive__read_file",
                "tool_parameters": json.dumps({"file_id": "1abc"}),
                "mcp_server_scope": "google_drive",
                "session.id": "sess_cowork_2",
                "success": True,
            },
        )
    )
    resp = client.post(
        "/v1/otlp/v1/logs",
        json=payload,
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] == 1
    assert body["events"][0]["action"] == "connector_access"

    # Verify the event details via the events API
    event_id = body["events"][0]["id"]
    detail = client.get(
        f"/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {api_key_raw}"},
    ).json()
    assert detail["data"]["connector"] == "google_drive"
    assert detail["data"]["operation"] == "read_file"
    assert detail["context"]["source"] == "otlp"


def test_otlp_shell_command(client, api_key_raw):
    """Cowork Bash tool → shell_command action."""
    payload = _otlp_payload(
        _log_record(
            "cowork.tool_result",
            **{
                "tool_name": "Bash",
                "tool_parameters": json.dumps({"command": "ls -la"}),
                "success": True,
            },
        )
    )
    resp = client.post(
        "/v1/otlp/v1/logs",
        json=payload,
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 200
    assert resp.json()["events"][0]["action"] == "shell_command"


def test_otlp_user_prompt(client, api_key_raw):
    """Cowork user prompt event → user_prompt action."""
    payload = _otlp_payload(
        _log_record(
            "cowork.user_prompt",
            **{"session.id": "sess_cowork_3"},
        )
    )
    resp = client.post(
        "/v1/otlp/v1/logs",
        json=payload,
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 200
    assert resp.json()["events"][0]["action"] == "user_prompt"


def test_otlp_api_request(client, api_key_raw):
    """Cowork API request event → api_request action."""
    payload = _otlp_payload(
        _log_record("cowork.api_request", duration_ms=150)
    )
    resp = client.post(
        "/v1/otlp/v1/logs",
        json=payload,
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 200
    assert resp.json()["events"][0]["action"] == "api_request"


def test_otlp_api_error(client, api_key_raw):
    """Cowork API error event → api_error action."""
    payload = _otlp_payload(
        _log_record("cowork.api_error", success=False)
    )
    resp = client.post(
        "/v1/otlp/v1/logs",
        json=payload,
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 200
    assert resp.json()["events"][0]["action"] == "api_error"


def test_otlp_tool_decision(client, api_key_raw):
    """Cowork tool decision event → tool_decision action."""
    payload = _otlp_payload(
        _log_record("cowork.tool_decision", tool_name="WebFetch")
    )
    resp = client.post(
        "/v1/otlp/v1/logs",
        json=payload,
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 200
    assert resp.json()["events"][0]["action"] == "tool_decision"


# ── Risk scoring through OTLP ───────────────────────────────────────


def test_otlp_pii_triggers_risk(client, api_key_raw):
    """Cowork connector accessing PII data → PII detected + risk scored."""
    _set_full_logging(client, api_key_raw)
    payload = _otlp_payload(
        _log_record(
            "cowork.tool_result",
            **{
                "tool_name": "mcp__salesforce__query",
                "tool_parameters": json.dumps({
                    "soql": "SELECT Name, Email FROM Contact WHERE Email = 'john@example.com'"
                }),
                "mcp_server_scope": "salesforce",
                "success": True,
            },
        )
    )
    resp = client.post(
        "/v1/otlp/v1/logs",
        json=payload,
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 200
    event_id = resp.json()["events"][0]["id"]

    detail = client.get(
        f"/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {api_key_raw}"},
    ).json()
    assert detail["pii_detected"] is True


def test_otlp_dangerous_command_high_risk(client, api_key_raw):
    """Cowork shell command with prod access → high risk.

    The OTLP mapper hoists command from tool_parameters to top-level
    data so the risk scorer can detect dangerous patterns.
    """
    payload = _otlp_payload(
        _log_record(
            "cowork.tool_result",
            **{
                "tool_name": "Bash",
                "tool_parameters": json.dumps({
                    "command": "psql -h prod-db.internal -c 'SELECT * FROM users'"
                }),
                "success": True,
            },
        )
    )
    resp = client.post(
        "/v1/otlp/v1/logs",
        json=payload,
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 200
    event = resp.json()["events"][0]
    assert event["risk_level"] in ("high", "critical")


# ── Batch and edge cases ────────────────────────────────────────────


def test_otlp_batch_multiple_records(client, api_key_raw):
    """Multiple log records in a single OTLP request."""
    payload = _otlp_payload(
        _log_record("cowork.tool_result", tool_name="Read"),
        _log_record("cowork.tool_result", tool_name="Write"),
        _log_record("cowork.user_prompt"),
    )
    resp = client.post(
        "/v1/otlp/v1/logs",
        json=payload,
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 200
    assert resp.json()["accepted"] == 3


def test_otlp_skips_empty_event_name(client, api_key_raw):
    """Records without event.name are skipped."""
    payload = _otlp_payload(
        {"attributes": [{"key": "tool_name", "value": {"stringValue": "Read"}}]}
    )
    resp = client.post(
        "/v1/otlp/v1/logs",
        json=payload,
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 200
    assert resp.json()["accepted"] == 0


def test_otlp_invalid_json(client, api_key_raw):
    """Invalid JSON body returns 422."""
    resp = client.post(
        "/v1/otlp/v1/logs",
        content="not json",
        headers={
            "Authorization": f"Bearer {api_key_raw}",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 422


def test_otlp_no_auth(client):
    """Missing API key returns 401."""
    payload = _otlp_payload(_log_record("cowork.tool_result", tool_name="Read"))
    resp = client.post("/v1/otlp/v1/logs", json=payload)
    assert resp.status_code in (401, 403)


def test_otlp_context_extraction(client, api_key_raw):
    """OTLP attributes are correctly extracted into event context."""
    _set_full_logging(client, api_key_raw)
    payload = _otlp_payload(
        _log_record(
            "cowork.tool_result",
            **{
                "tool_name": "Read",
                "session.id": "sess_ctx",
                "organization.id": "org_abc",
                "user.email": "alice@company.com",
                "user.id": "user_123",
                "prompt.id": "prompt_456",
                "event.sequence": 7,
            },
        )
    )
    resp = client.post(
        "/v1/otlp/v1/logs",
        json=payload,
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 200
    event_id = resp.json()["events"][0]["id"]

    detail = client.get(
        f"/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {api_key_raw}"},
    ).json()
    ctx = detail["context"]
    assert ctx["session_id"] == "sess_ctx"
    assert ctx["organization_id"] == "org_abc"
    assert ctx["user_email"] == "alice@company.com"
    assert ctx["source"] == "otlp"
    assert ctx["otlp_event_name"] == "cowork.tool_result"


def test_otlp_slack_connector(client, api_key_raw):
    """Cowork Slack MCP tool → connector_access with slack connector."""
    _set_full_logging(client, api_key_raw)
    payload = _otlp_payload(
        _log_record(
            "cowork.tool_result",
            **{
                "tool_name": "mcp__slack__send_message",
                "tool_parameters": json.dumps({"channel": "#general", "text": "hello"}),
                "mcp_server_scope": "slack",
                "success": True,
            },
        )
    )
    resp = client.post(
        "/v1/otlp/v1/logs",
        json=payload,
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 200
    event_id = resp.json()["events"][0]["id"]

    detail = client.get(
        f"/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {api_key_raw}"},
    ).json()
    assert detail["data"]["connector"] == "slack"
    assert detail["data"]["operation"] == "send_message"
