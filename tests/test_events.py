def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_ingest_event_success(client, api_key_raw):
    response = client.post(
        "/v1/events",
        json={
            "agent_id": "claude-code",
            "action": "shell_command",
            "data": {"command": "ls -la", "working_dir": "/tmp", "exit_code": 0},
            "context": {"tool": "claude_code", "session_id": "test-session"},
            "reasoning": "User requested directory listing",
        },
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["agent_id"] == "claude-code"
    assert data["action"] == "shell_command"
    assert data["data"]["command"] == "ls -la"
    assert data["context"]["tool"] == "claude_code"
    assert data["reasoning"] == "User requested directory listing"
    assert len(data["id"]) == 26
    assert data["risk_level"] == "low"
    assert data["decision"] == "allow"
    assert "created_at" in data


def test_ingest_event_no_auth(client):
    response = client.post(
        "/v1/events",
        json={"agent_id": "test", "action": "test_action"},
    )
    assert response.status_code in (401, 403)


def test_ingest_event_invalid_api_key(client):
    response = client.post(
        "/v1/events",
        json={"agent_id": "test", "action": "test_action"},
        headers={"Authorization": "Bearer aa_live_invalidkey00000000000000000"},
    )
    assert response.status_code == 401


def test_ingest_event_missing_agent_id(client, api_key_raw):
    response = client.post(
        "/v1/events",
        json={"action": "test_action"},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert response.status_code == 422


def test_ingest_event_missing_action(client, api_key_raw):
    response = client.post(
        "/v1/events",
        json={"agent_id": "test"},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert response.status_code == 422


def test_ingest_event_minimal_payload(client, api_key_raw):
    """Test with only required fields. Default policy is 'standard', so low-risk
    events without PII are NOT stored."""
    response = client.post(
        "/v1/events",
        json={"agent_id": "test-agent", "action": "test_action"},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["agent_id"] == "test-agent"
    assert data["action"] == "test_action"
    assert data["risk_level"] == "low"
    # Standard policy: low risk, no PII → not stored
    assert data["stored"] is False
