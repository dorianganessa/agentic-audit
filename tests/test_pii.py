from agentaudit_api.services.pii_detector import detect_pii


def test_detect_email():
    result = detect_pii({"message": "Contact user@example.com"}, {})
    assert result.detected is True
    assert "email" in result.fields


def test_detect_ip():
    result = detect_pii({"host": "Connected to 192.168.1.100"}, {})
    assert result.detected is True
    assert "ip_address" in result.fields


def test_detect_phone():
    result = detect_pii({"phone": "+1 555-123-4567"}, {})
    assert result.detected is True
    assert "phone" in result.fields


def test_detect_credit_card():
    result = detect_pii({"card": "4111-1111-1111-1111"}, {})
    assert result.detected is True
    assert "credit_card" in result.fields


def test_detect_api_key_sk_live():
    result = detect_pii({"key": "sk_live_abc123def456ghi789"}, {})
    assert result.detected is True
    assert "api_key" in result.fields


def test_detect_api_key_ghp():
    result = detect_pii({"token": "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345678"}, {})
    assert result.detected is True
    assert "api_key" in result.fields


def test_detect_db_connection_string():
    result = detect_pii({"dsn": "postgresql://user:pass@host:5432/db"}, {})
    assert result.detected is True
    assert "db_connection_string" in result.fields


def test_detect_multiple():
    result = detect_pii(
        {"msg": "Email user@example.com from 10.0.0.1"},
        {"dsn": "postgresql://u:p@h/d"},
    )
    assert result.detected is True
    assert "email" in result.fields
    assert "ip_address" in result.fields
    assert "db_connection_string" in result.fields


def test_detect_nested():
    result = detect_pii(
        {"nested": {"deep": {"email": "test@example.com"}}},
        {},
    )
    assert result.detected is True
    assert "email" in result.fields


def test_detect_in_list():
    result = detect_pii(
        {"items": ["no-pii", "user@example.com", "clean"]},
        {},
    )
    assert result.detected is True
    assert "email" in result.fields


def test_no_pii():
    result = detect_pii({"command": "ls -la", "exit_code": 0}, {"tool": "bash"})
    assert result.detected is False
    assert result.fields == []


def test_detect_in_context():
    result = detect_pii({}, {"developer": "dev@company.com"})
    assert result.detected is True
    assert "email" in result.fields


def test_ingest_event_with_email(client, api_key_raw):
    """POST event with email in data → pii_detected=True."""
    response = client.post(
        "/v1/events",
        json={
            "agent_id": "test",
            "action": "access_record",
            "data": {"customer_email": "john@example.com"},
        },
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["pii_detected"] is True
    assert "email" in data["pii_fields"]


def test_ingest_event_with_db_conn(client, api_key_raw):
    """POST event with DB connection string → pii_detected=True."""
    response = client.post(
        "/v1/events",
        json={
            "agent_id": "test",
            "action": "shell_command",
            "data": {"command": "psql postgresql://admin:secret@prod:5432/mydb"},
        },
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["pii_detected"] is True
    assert "db_connection_string" in data["pii_fields"]
