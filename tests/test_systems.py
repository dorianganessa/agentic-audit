"""Tests for AI Systems registry (CRUD + event linking)."""


def test_create_system(client, api_key_raw):
    """Create a new AI system."""
    resp = client.post(
        "/v1/systems",
        json={
            "name": "OpenClaw",
            "vendor": "OpenClaw Inc",
            "description": "AI agent platform",
            "use_case": "Customer support automation",
            "agent_id_patterns": ["openclaw", "openclaw-*"],
            "risk_classification": "limited",
            "role": "deployer",
        },
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "OpenClaw"
    assert body["vendor"] == "OpenClaw Inc"
    assert body["agent_id_patterns"] == ["openclaw", "openclaw-*"]
    assert body["risk_classification"] == "limited"
    assert body["fria_status"] == "not_started"
    assert body["is_active"] is True
    assert "id" in body


def test_list_systems(client, api_key_raw):
    """List systems returns all active systems."""
    headers = {"Authorization": f"Bearer {api_key_raw}"}
    client.post(
        "/v1/systems",
        json={"name": "System A", "agent_id_patterns": ["a"]},
        headers=headers,
    )
    client.post(
        "/v1/systems",
        json={"name": "System B", "agent_id_patterns": ["b"]},
        headers=headers,
    )
    resp = client.get("/v1/systems", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    names = [s["name"] for s in body["systems"]]
    assert "System A" in names
    assert "System B" in names


def test_get_system(client, api_key_raw):
    """Get a single system by ID."""
    headers = {"Authorization": f"Bearer {api_key_raw}"}
    create_resp = client.post(
        "/v1/systems",
        json={"name": "Test System", "agent_id_patterns": ["test-*"]},
        headers=headers,
    )
    system_id = create_resp.json()["id"]

    resp = client.get(f"/v1/systems/{system_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test System"


def test_get_system_not_found(client, api_key_raw):
    """Non-existent system returns 404."""
    resp = client.get(
        "/v1/systems/nonexistent",
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert resp.status_code == 404


def test_update_system(client, api_key_raw):
    """Partial update of a system."""
    headers = {"Authorization": f"Bearer {api_key_raw}"}
    create_resp = client.post(
        "/v1/systems",
        json={"name": "Before", "risk_classification": "unclassified"},
        headers=headers,
    )
    system_id = create_resp.json()["id"]

    resp = client.put(
        f"/v1/systems/{system_id}",
        json={
            "name": "After",
            "risk_classification": "high",
            "annex_iii_category": "employment",
            "fria_status": "in_progress",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "After"
    assert body["risk_classification"] == "high"
    assert body["annex_iii_category"] == "employment"
    assert body["fria_status"] == "in_progress"


def test_update_invalid_classification(client, api_key_raw):
    """Invalid risk_classification returns 422."""
    headers = {"Authorization": f"Bearer {api_key_raw}"}
    create_resp = client.post(
        "/v1/systems",
        json={"name": "Test"},
        headers=headers,
    )
    system_id = create_resp.json()["id"]

    resp = client.put(
        f"/v1/systems/{system_id}",
        json={"risk_classification": "invalid_value"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_delete_system(client, api_key_raw):
    """Soft-delete deactivates the system."""
    headers = {"Authorization": f"Bearer {api_key_raw}"}
    create_resp = client.post(
        "/v1/systems",
        json={"name": "To Delete"},
        headers=headers,
    )
    system_id = create_resp.json()["id"]

    resp = client.delete(f"/v1/systems/{system_id}", headers=headers)
    assert resp.status_code == 204

    # Should not appear in default list
    list_resp = client.get("/v1/systems", headers=headers)
    ids = [s["id"] for s in list_resp.json()["systems"]]
    assert system_id not in ids

    # Should appear with include_inactive
    list_resp2 = client.get("/v1/systems?include_inactive=true", headers=headers)
    ids2 = [s["id"] for s in list_resp2.json()["systems"]]
    assert system_id in ids2


def test_system_events_matching(client, api_key_raw):
    """Events are linked to systems via agent_id_patterns."""
    headers = {"Authorization": f"Bearer {api_key_raw}"}

    # Set full logging
    client.put(
        "/v1/org/policy",
        json={"logging_level": "full"},
        headers=headers,
    )

    # Create events with different agent_ids
    client.post(
        "/v1/events",
        json={"agent_id": "openclaw", "action": "shell_command", "data": {"command": "ls"}},
        headers=headers,
    )
    client.post(
        "/v1/events",
        json={
            "agent_id": "openclaw-support",
            "action": "file_read",
            "data": {"file_path": "/tmp/x"},
        },
        headers=headers,
    )
    client.post(
        "/v1/events",
        json={"agent_id": "claude-code", "action": "shell_command", "data": {"command": "pwd"}},
        headers=headers,
    )

    # Create system matching openclaw*
    create_resp = client.post(
        "/v1/systems",
        json={"name": "OpenClaw", "agent_id_patterns": ["openclaw", "openclaw-*"]},
        headers=headers,
    )
    system_id = create_resp.json()["id"]

    # Query events for this system
    resp = client.get(f"/v1/systems/{system_id}/events", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    agent_ids = [e["agent_id"] for e in body["events"]]
    assert "openclaw" in agent_ids
    assert "openclaw-support" in agent_ids
    assert "claude-code" not in agent_ids


def test_system_stats(client, api_key_raw):
    """Stats are aggregated for system's matched events."""
    headers = {"Authorization": f"Bearer {api_key_raw}"}
    client.put(
        "/v1/org/policy",
        json={"logging_level": "full"},
        headers=headers,
    )

    client.post(
        "/v1/events",
        json={"agent_id": "mybot", "action": "shell_command", "data": {"command": "ls"}},
        headers=headers,
    )
    client.post(
        "/v1/events",
        json={"agent_id": "mybot", "action": "file_read", "data": {"file_path": "/tmp/x"}},
        headers=headers,
    )

    create_resp = client.post(
        "/v1/systems",
        json={"name": "MyBot", "agent_id_patterns": ["mybot"]},
        headers=headers,
    )
    system_id = create_resp.json()["id"]

    resp = client.get(f"/v1/systems/{system_id}/stats", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_events"] == 2
    assert "by_risk_level" in body
    assert "by_action" in body


def test_system_no_events_when_no_patterns(client, api_key_raw):
    """System with empty patterns returns no events."""
    headers = {"Authorization": f"Bearer {api_key_raw}"}
    create_resp = client.post(
        "/v1/systems",
        json={"name": "Empty", "agent_id_patterns": []},
        headers=headers,
    )
    system_id = create_resp.json()["id"]

    resp = client.get(f"/v1/systems/{system_id}/events", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_create_system_with_contract_fields(client, api_key_raw):
    """Contract tracking fields are persisted."""
    headers = {"Authorization": f"Bearer {api_key_raw}"}
    resp = client.post(
        "/v1/systems",
        json={
            "name": "Vendor AI",
            "vendor": "Acme Corp",
            "contract_has_ai_annex": True,
            "provider_obligations_documented": True,
            "contract_notes": "Reviewed with legal 2026-03",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["contract_has_ai_annex"] is True
    assert body["provider_obligations_documented"] is True
    assert "Reviewed with legal" in body["contract_notes"]


def test_create_system_with_fria_fields(client, api_key_raw):
    """FRIA tracking fields are persisted."""
    headers = {"Authorization": f"Bearer {api_key_raw}"}
    resp = client.post(
        "/v1/systems",
        json={
            "name": "HR Tool",
            "risk_classification": "high",
            "annex_iii_category": "employment",
            "fria_status": "completed",
            "fria_completed_at": "2026-03-01T00:00:00",
            "fria_next_review": "2026-09-01T00:00:00",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["fria_status"] == "completed"
    assert body["annex_iii_category"] == "employment"
    assert body["fria_completed_at"] is not None
