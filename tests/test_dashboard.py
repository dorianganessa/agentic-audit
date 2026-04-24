"""Tests for the dashboard, Slack alerts, and PDF report export."""

from unittest.mock import MagicMock, patch

from agentaudit_api.models.api_key import (
    ApiKey,
    generate_api_key,
    hash_api_key,
    key_prefix_from_key,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def _auth(api_key_raw):
    return {"Authorization": f"Bearer {api_key_raw}"}


def _set_dashboard_cookie(client, api_key_raw):
    """Set the dashboard auth cookie on the test client."""
    client.cookies.set("agentaudit_session", hash_api_key(api_key_raw))


def _set_full(client, api_key_raw):
    client.put("/v1/org/policy", json={"logging_level": "full"}, headers=_auth(api_key_raw))


def _post(client, api_key_raw, **kwargs):
    payload = {"agent_id": "test-agent", "action": "test_action"}
    payload.update(kwargs)
    resp = client.post("/v1/events", json=payload, headers=_auth(api_key_raw))
    assert resp.status_code == 201
    return resp.json()


# --- Dashboard timeline ---


def test_dashboard_timeline_200(client, api_key_raw):
    """GET /dashboard returns 200 with HTML."""
    _set_dashboard_cookie(client, api_key_raw)
    _set_full(client, api_key_raw)
    _post(client, api_key_raw)

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Event Timeline" in resp.text
    assert "test-agent" in resp.text


def test_dashboard_timeline_filter_risk(client, api_key_raw):
    """GET /dashboard?risk_level=high filters events via HTMX."""
    _set_dashboard_cookie(client, api_key_raw)
    _set_full(client, api_key_raw)
    _post(client, api_key_raw, action="shell_command", data={"command": "echo hi"})
    _post(
        client,
        api_key_raw,
        action="shell_command",
        data={"command": "psql -h prod -c 'SELECT 1'"},
    )

    # Request with HX-Request header (HTMX partial)
    resp = client.get("/dashboard?risk_level=high", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    # Should only contain high-risk events
    assert "high" in resp.text
    # The partial should not have <nav> (only full pages do)
    assert "<nav" not in resp.text


def test_dashboard_timeline_empty(client, api_key_raw):
    """Dashboard with no events shows empty state."""
    _set_dashboard_cookie(client, api_key_raw)
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "No events found" in resp.text


# --- Event detail ---


def test_dashboard_event_detail(client, api_key_raw):
    """GET /dashboard/events/{id} shows event details."""
    _set_dashboard_cookie(client, api_key_raw)
    _set_full(client, api_key_raw)
    created = _post(
        client,
        api_key_raw,
        action="access_record",
        data={"email": "user@example.com"},
    )

    resp = client.get(f"/dashboard/events/{created['id']}")
    assert resp.status_code == 200
    assert created["id"] in resp.text
    assert "access_record" in resp.text
    assert "PII" in resp.text
    assert "GDPR" in resp.text


def test_dashboard_event_not_found(client, api_key_raw):
    """GET /dashboard/events/{bad_id} returns 404."""
    _set_dashboard_cookie(client, api_key_raw)
    resp = client.get("/dashboard/events/nonexistent_12345")
    assert resp.status_code == 404


# --- Policy page ---


def test_dashboard_policy_page(client, api_key_raw):
    """GET /dashboard/policy shows current policy."""
    _set_dashboard_cookie(client, api_key_raw)
    resp = client.get("/dashboard/policy")
    assert resp.status_code == 200
    assert "Policy" in resp.text
    assert "standard" in resp.text


def test_dashboard_policy_update(client, api_key_raw):
    """PUT /dashboard/policy updates the policy via HTMX."""
    _set_dashboard_cookie(client, api_key_raw)
    resp = client.put(
        "/dashboard/policy?logging_level=full&fw_gdpr=true&fw_ai_act=true&fw_soc2=true&blocking_enabled=false&block_on=critical"
    )
    assert resp.status_code == 200
    assert "Policy updated" in resp.text

    # Verify via API
    resp2 = client.get("/v1/org/policy", headers=_auth(api_key_raw))
    data = resp2.json()
    assert data["logging_level"] == "full"
    assert data["frameworks"]["soc2"] is True


# --- Stats page ---


def test_dashboard_stats(client, api_key_raw):
    """GET /dashboard/stats returns stats page with counters."""
    _set_dashboard_cookie(client, api_key_raw)
    _set_full(client, api_key_raw)
    _post(client, api_key_raw, action="shell_command", data={"command": "echo hi"})
    _post(client, api_key_raw, action="access_record", data={"email": "u@e.com"})

    resp = client.get("/dashboard/stats?range=all")
    assert resp.status_code == 200
    assert "Stats Overview" in resp.text
    assert "Total Events" in resp.text


# --- PDF report ---


def test_dashboard_report_pdf(client, api_key_raw):
    """GET /dashboard/report/pdf returns a valid PDF."""
    _set_dashboard_cookie(client, api_key_raw)
    _set_full(client, api_key_raw)
    _post(client, api_key_raw, action="shell_command", data={"command": "echo hi"})
    _post(
        client,
        api_key_raw,
        action="shell_command",
        data={"command": "psql -h prod -c 'SELECT 1'"},
    )

    resp = client.get("/dashboard/report/pdf?range=all")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    # PDF magic bytes
    assert resp.content[:5] == b"%PDF-"
    assert len(resp.content) > 500


# --- Slack alerts ---


def test_alert_matches_and_fires(client, api_key_raw):
    """POST high-risk event with alert rule configured triggers Slack webhook."""
    # Set policy with alert rule
    client.put(
        "/v1/org/policy",
        json={
            "logging_level": "full",
            "alert_rules": [
                {
                    "name": "High risk alert",
                    "condition": {"risk_level_gte": "high"},
                    "notify": {"slack_webhook_url": "https://hooks.slack.com/test"},
                }
            ],
        },
        headers=_auth(api_key_raw),
    )

    with patch("agentaudit_api.services.alerter.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = MagicMock(status_code=200)
        mock_client.post.return_value.raise_for_status = MagicMock()
        mock_client_cls.return_value = mock_client

        resp = client.post(
            "/v1/events",
            json={
                "agent_id": "test-agent",
                "action": "shell_command",
                "data": {"command": "psql -h prod -c 'SELECT 1'"},
            },
            headers=_auth(api_key_raw),
        )
        assert resp.status_code == 201
        assert resp.json()["risk_level"] == "high"

        # BackgroundTasks run synchronously in TestClient
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://hooks.slack.com/test"
        payload = call_args[1]["json"]
        assert "High risk alert" in payload["text"]


def test_alert_no_match_no_fire(client, api_key_raw):
    """POST low-risk event with high-risk alert rule does NOT fire webhook."""
    client.put(
        "/v1/org/policy",
        json={
            "logging_level": "full",
            "alert_rules": [
                {
                    "name": "High risk only",
                    "condition": {"risk_level_gte": "high"},
                    "notify": {"slack_webhook_url": "https://hooks.slack.com/test"},
                }
            ],
        },
        headers=_auth(api_key_raw),
    )

    with patch("agentaudit_api.services.alerter.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        resp = client.post(
            "/v1/events",
            json={
                "agent_id": "test-agent",
                "action": "shell_command",
                "data": {"command": "echo hi"},
            },
            headers=_auth(api_key_raw),
        )
        assert resp.status_code == 201
        assert resp.json()["risk_level"] == "low"

        mock_client.post.assert_not_called()


def test_alert_multiple_conditions_and(client, api_key_raw):
    """Alert with multiple conditions requires all to match (AND)."""
    client.put(
        "/v1/org/policy",
        json={
            "logging_level": "full",
            "alert_rules": [
                {
                    "name": "PII + high risk",
                    "condition": {"risk_level_gte": "high", "pii_detected": True},
                    "notify": {"slack_webhook_url": "https://hooks.slack.com/test"},
                }
            ],
        },
        headers=_auth(api_key_raw),
    )

    with patch("agentaudit_api.services.alerter.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # High risk but no PII → should NOT fire
        resp = client.post(
            "/v1/events",
            json={
                "agent_id": "test-agent",
                "action": "shell_command",
                "data": {"command": "psql -h prod -c 'SELECT 1'"},
            },
            headers=_auth(api_key_raw),
        )
        assert resp.status_code == 201
        mock_client.post.assert_not_called()


# --- Dashboard org-scoping (events posted under a sibling API key) ---


def _mint_sibling_key(db_url: str, org_id: str, name: str) -> str:
    """Create a second API key in the same org and return the raw key string."""
    engine = create_engine(db_url)
    raw = generate_api_key()
    with Session(engine) as s:
        s.add(
            ApiKey(
                key_hash=hash_api_key(raw),
                key_prefix=key_prefix_from_key(raw),
                name=name,
                org_id=org_id,
            )
        )
        s.commit()
    return raw


def test_dashboard_shows_events_from_sibling_key_in_same_org(client, api_key_raw, db_url):
    """Regression: dashboard used to filter events by api_key_id of the logged-in
    key, so events ingested under a different API key in the same org (e.g. the
    claude-code hook using a distinct key from the dashboard login) appeared
    empty on the dashboard. The dashboard must show all events for the org."""
    _set_full(client, api_key_raw)

    # Find the org that owns the logged-in key.
    engine = create_engine(db_url)
    with Session(engine) as s:
        logged_in_key = s.query(ApiKey).filter(ApiKey.key_hash == hash_api_key(api_key_raw)).first()
        assert logged_in_key is not None and logged_in_key.org_id is not None
        org_id = logged_in_key.org_id

    # Mint a second key in the same org (simulating the claude-code hook key).
    sibling_raw = _mint_sibling_key(db_url, org_id, "claude-code-hook")

    # Post an event using the SIBLING key.
    resp = client.post(
        "/v1/events",
        json={
            "agent_id": "sibling-agent",
            "action": "shell_command",
            "data": {"command": "echo from sibling"},
        },
        headers={"Authorization": f"Bearer {sibling_raw}"},
    )
    assert resp.status_code == 201

    # Log into the dashboard with the ORIGINAL key — should see the sibling's event.
    _set_dashboard_cookie(client, api_key_raw)
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "sibling-agent" in resp.text, (
        "dashboard should show events from all API keys in the org, not just the logged-in key"
    )


def test_dashboard_does_not_leak_events_across_orgs(client, api_key_raw, db_url):
    """Org-scoping must not leak events from a different org."""
    _set_full(client, api_key_raw)

    # Create a separate org + key and post an event under it.
    from agentaudit_api.models.organization import Organization

    engine = create_engine(db_url)
    other_raw = generate_api_key()
    with Session(engine) as s:
        other_org = Organization(name="Other Org")
        s.add(other_org)
        s.flush()
        s.add(
            ApiKey(
                key_hash=hash_api_key(other_raw),
                key_prefix=key_prefix_from_key(other_raw),
                name="Other",
                org_id=other_org.id,
            )
        )
        s.commit()

    client.post(
        "/v1/events",
        json={
            "agent_id": "other-org-agent",
            "action": "shell_command",
            "data": {"command": "secret"},
        },
        headers={"Authorization": f"Bearer {other_raw}"},
    )

    _set_dashboard_cookie(client, api_key_raw)
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "other-org-agent" not in resp.text, (
        "org-scoped dashboard must not leak events from a different org"
    )


def test_dashboard_stats_aggregate_across_org_keys(client, api_key_raw, db_url):
    """Stats page (top agents, top actions) must aggregate across all keys in the org."""
    _set_full(client, api_key_raw)

    engine = create_engine(db_url)
    with Session(engine) as s:
        logged_in = s.query(ApiKey).filter(ApiKey.key_hash == hash_api_key(api_key_raw)).first()
        assert logged_in is not None and logged_in.org_id is not None
        org_id = logged_in.org_id

    sibling_raw = _mint_sibling_key(db_url, org_id, "hook-key")

    # Sibling key posts a high-risk event
    client.post(
        "/v1/events",
        json={
            "agent_id": "hook-agent",
            "action": "shell_command",
            "data": {"command": "rm -rf /tmp/foo"},
        },
        headers={"Authorization": f"Bearer {sibling_raw}"},
    )

    _set_dashboard_cookie(client, api_key_raw)
    resp = client.get("/dashboard/stats")
    assert resp.status_code == 200
    assert "hook-agent" in resp.text


# --- Rate limiter: loopback / private IPs are exempt ---


def test_rate_limiter_is_exempt_ip_covers_loopback_and_private():
    """Unit test for the rate-limit exemption predicate."""
    from agentaudit_api.main import _is_exempt_ip

    # Loopback
    assert _is_exempt_ip("127.0.0.1")
    assert _is_exempt_ip("::1")
    # RFC 1918 private ranges — covers docker-compose bridge NAT
    assert _is_exempt_ip("192.168.1.5")
    assert _is_exempt_ip("192.168.65.1")  # Docker Desktop host-to-container gateway
    assert _is_exempt_ip("10.0.0.5")
    assert _is_exempt_ip("172.16.0.5")
    # Not exempt: public IPs
    assert not _is_exempt_ip("8.8.8.8")
    assert not _is_exempt_ip("1.1.1.1")
    # Non-parseable strings (e.g., "testclient", "unknown") don't pass as IPs
    # and are therefore NOT exempt — they still count against the bucket so
    # the TestClient fixture continues to exercise the rate limiter code path.
    assert not _is_exempt_ip("testclient")
    assert not _is_exempt_ip("unknown")
    assert not _is_exempt_ip("")
