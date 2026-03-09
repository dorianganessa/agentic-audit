"""Tests for query API endpoints: GET /v1/events, GET /v1/events/{id}, GET /v1/events/stats."""


def _auth(api_key_raw):
    return {"Authorization": f"Bearer {api_key_raw}"}


def _set_full_policy(client, api_key_raw):
    """Set logging to 'full' so all events are stored."""
    client.put("/v1/org/policy", json={"logging_level": "full"}, headers=_auth(api_key_raw))


def _post_event(client, api_key_raw, **kwargs):
    """Helper to create an event via the API."""
    payload = {"agent_id": "test-agent", "action": "test_action"}
    payload.update(kwargs)
    response = client.post("/v1/events", json=payload, headers=_auth(api_key_raw))
    assert response.status_code == 201
    return response.json()


def test_get_event_by_id(client, api_key_raw):
    """GET /v1/events/{id} returns the event."""
    _set_full_policy(client, api_key_raw)
    created = _post_event(client, api_key_raw)

    response = client.get(f"/v1/events/{created['id']}", headers=_auth(api_key_raw))
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created["id"]
    assert data["agent_id"] == "test-agent"


def test_get_event_not_found(client, api_key_raw):
    response = client.get("/v1/events/nonexistent_id_12345", headers=_auth(api_key_raw))
    assert response.status_code == 404


def test_list_events(client, api_key_raw):
    """GET /v1/events returns paginated list."""
    _set_full_policy(client, api_key_raw)
    _post_event(client, api_key_raw, agent_id="agent-a", action="file_read")
    _post_event(client, api_key_raw, agent_id="agent-b", action="shell_command")

    response = client.get("/v1/events", headers=_auth(api_key_raw))
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert "total" in data
    assert data["total"] >= 2
    assert data["limit"] == 50
    assert data["offset"] == 0


def test_list_events_filter_agent_id(client, api_key_raw):
    _set_full_policy(client, api_key_raw)
    _post_event(client, api_key_raw, agent_id="filter-agent", action="test")

    response = client.get("/v1/events?agent_id=filter-agent", headers=_auth(api_key_raw))
    data = response.json()
    assert data["total"] >= 1
    assert all(e["agent_id"] == "filter-agent" for e in data["events"])


def test_list_events_filter_action(client, api_key_raw):
    _set_full_policy(client, api_key_raw)
    _post_event(client, api_key_raw, action="unique_action_xyz")

    response = client.get("/v1/events?action=unique_action_xyz", headers=_auth(api_key_raw))
    data = response.json()
    assert data["total"] >= 1
    assert all(e["action"] == "unique_action_xyz" for e in data["events"])


def test_list_events_filter_risk_level(client, api_key_raw):
    _set_full_policy(client, api_key_raw)
    _post_event(
        client,
        api_key_raw,
        action="shell_command",
        data={"command": "psql -h prod-db -c 'SELECT *'"},
    )

    response = client.get("/v1/events?risk_level=high", headers=_auth(api_key_raw))
    data = response.json()
    assert data["total"] >= 1
    assert all(e["risk_level"] == "high" for e in data["events"])


def test_list_events_filter_pii(client, api_key_raw):
    _set_full_policy(client, api_key_raw)
    _post_event(
        client,
        api_key_raw,
        action="access_record",
        data={"email": "user@example.com"},
    )

    response = client.get("/v1/events?pii_detected=true", headers=_auth(api_key_raw))
    data = response.json()
    assert data["total"] >= 1
    assert all(e["pii_detected"] is True for e in data["events"])


def test_list_events_filter_session_id(client, api_key_raw):
    _set_full_policy(client, api_key_raw)
    _post_event(
        client,
        api_key_raw,
        context={"session_id": "sess_unique_filter_test"},
    )

    response = client.get(
        "/v1/events?session_id=sess_unique_filter_test", headers=_auth(api_key_raw)
    )
    data = response.json()
    assert data["total"] >= 1


def test_list_events_pagination(client, api_key_raw):
    _set_full_policy(client, api_key_raw)
    for i in range(3):
        _post_event(client, api_key_raw, agent_id=f"page-agent-{i}")

    response = client.get("/v1/events?limit=2&offset=0", headers=_auth(api_key_raw))
    data = response.json()
    assert len(data["events"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0


def test_stats(client, api_key_raw):
    """GET /v1/events/stats returns correct counters."""
    _set_full_policy(client, api_key_raw)
    _post_event(
        client,
        api_key_raw,
        agent_id="stats-agent",
        action="shell_command",
        data={"command": "pytest -v"},
        context={"session_id": "stats-sess-1"},
    )
    _post_event(
        client,
        api_key_raw,
        agent_id="stats-agent",
        action="access_record",
        data={"email": "pii@example.com"},
        context={"session_id": "stats-sess-2"},
    )
    _post_event(
        client,
        api_key_raw,
        agent_id="stats-agent-2",
        action="shell_command",
        data={"command": "psql -h prod -c 'SELECT 1'"},
        context={"session_id": "stats-sess-1"},
    )

    response = client.get("/v1/events/stats", headers=_auth(api_key_raw))
    assert response.status_code == 200
    data = response.json()
    assert data["total_events"] >= 3
    assert "by_risk_level" in data
    assert "by_action" in data
    assert data["pii_events"] >= 1
    assert data["unique_agents"] >= 2
    assert data["unique_sessions"] >= 1


def test_stats_no_auth(client):
    response = client.get("/v1/events/stats")
    assert response.status_code in (401, 403)
