"""Tests for Organization policy, storage filtering, blocking, and framework mapping."""


def _auth(api_key_raw):
    return {"Authorization": f"Bearer {api_key_raw}"}


def _set_policy(client, api_key_raw, **kwargs):
    """Helper to update org policy."""
    response = client.put("/v1/org/policy", json=kwargs, headers=_auth(api_key_raw))
    assert response.status_code == 200
    return response.json()


def _post(client, api_key_raw, **kwargs):
    payload = {"agent_id": "test-agent", "action": "test_action"}
    payload.update(kwargs)
    response = client.post("/v1/events", json=payload, headers=_auth(api_key_raw))
    assert response.status_code == 201
    return response.json()


# --- Policy API ---


def test_get_policy(client, api_key_raw):
    response = client.get("/v1/org/policy", headers=_auth(api_key_raw))
    assert response.status_code == 200
    data = response.json()
    assert data["logging_level"] == "standard"
    assert data["frameworks"]["gdpr"] is True
    assert data["frameworks"]["ai_act"] is True


def test_update_policy(client, api_key_raw):
    data = _set_policy(client, api_key_raw, logging_level="full")
    assert data["logging_level"] == "full"
    # Other fields preserved
    assert data["frameworks"]["gdpr"] is True


def test_update_policy_partial(client, api_key_raw):
    """Partial update only changes specified fields."""
    _set_policy(client, api_key_raw, logging_level="paranoid")
    frameworks = {"gdpr": True, "ai_act": False, "soc2": True}
    data = _set_policy(client, api_key_raw, frameworks=frameworks)
    assert data["logging_level"] == "paranoid"
    assert data["frameworks"]["soc2"] is True
    assert data["frameworks"]["ai_act"] is False


# --- Minimal policy ---


def test_minimal_no_pii_not_stored(client, api_key_raw):
    """Minimal: event without PII → stored=false."""
    _set_policy(client, api_key_raw, logging_level="minimal")
    data = _post(
        client, api_key_raw, action="shell_command", data={"command": "ls -la"}
    )
    assert data["stored"] is False


def test_minimal_with_pii_stored(client, api_key_raw):
    """Minimal: event with PII → stored=true, frameworks include GDPR art_30."""
    _set_policy(client, api_key_raw, logging_level="minimal")
    data = _post(
        client,
        api_key_raw,
        action="access_record",
        data={"email": "user@example.com"},
    )
    assert data["stored"] is True
    assert data["pii_detected"] is True
    assert "email" in data["pii_fields"]
    assert "art_30" in data["frameworks"].get("gdpr", [])


# --- Standard policy ---


def test_standard_low_risk_not_stored(client, api_key_raw):
    """Standard: low risk, no PII → not stored."""
    _set_policy(client, api_key_raw, logging_level="standard")
    data = _post(client, api_key_raw, action="shell_command", data={"command": "echo hi"})
    assert data["stored"] is False
    assert data["risk_level"] == "low"


def test_standard_medium_risk_stored(client, api_key_raw):
    """Standard: medium risk (PII) → stored."""
    _set_policy(client, api_key_raw, logging_level="standard")
    data = _post(
        client, api_key_raw, action="access_record", data={"email": "user@example.com"}
    )
    assert data["stored"] is True
    assert data["risk_level"] == "medium"


def test_standard_high_risk_stored(client, api_key_raw):
    """Standard: high risk → stored."""
    _set_policy(client, api_key_raw, logging_level="standard")
    data = _post(
        client,
        api_key_raw,
        action="shell_command",
        data={"command": "psql -h prod -c 'SELECT 1'"},
    )
    assert data["stored"] is True
    assert data["risk_level"] == "high"


# --- Full policy ---


def test_full_stores_everything(client, api_key_raw):
    """Full: even low-risk events are stored."""
    _set_policy(client, api_key_raw, logging_level="full")
    data = _post(client, api_key_raw, action="shell_command", data={"command": "ls"})
    assert data["stored"] is True
    assert data["risk_level"] == "low"


# --- Paranoid policy + blocking ---


def test_paranoid_allow_low_risk(client, api_key_raw):
    """Paranoid with block_on=high: low risk → allow."""
    _set_policy(
        client,
        api_key_raw,
        logging_level="paranoid",
        blocking_rules={"enabled": True, "block_on": "high"},
    )
    data = _post(client, api_key_raw, action="shell_command", data={"command": "ls"})
    assert data["decision"] == "allow"
    assert data["stored"] is True


def test_paranoid_block_high_risk(client, api_key_raw):
    """Paranoid with block_on=high: high risk → block."""
    _set_policy(
        client,
        api_key_raw,
        logging_level="paranoid",
        blocking_rules={"enabled": True, "block_on": "high"},
    )
    data = _post(
        client,
        api_key_raw,
        action="shell_command",
        data={"command": "psql -h prod -c 'SELECT 1'"},
    )
    assert data["decision"] == "block"
    assert data["reason"] is not None
    assert "high" in data["reason"]
    assert data["stored"] is True


def test_paranoid_block_critical(client, api_key_raw):
    """Paranoid with block_on=critical: critical → block."""
    _set_policy(
        client,
        api_key_raw,
        logging_level="paranoid",
        blocking_rules={"enabled": True, "block_on": "critical"},
    )
    data = _post(
        client,
        api_key_raw,
        action="shell_command",
        data={"command": "rm -rf /var/data"},
    )
    assert data["decision"] == "block"
    assert data["stored"] is True


def test_paranoid_not_enabled_no_block(client, api_key_raw):
    """Paranoid without blocking enabled → allow even high risk."""
    _set_policy(
        client,
        api_key_raw,
        logging_level="paranoid",
        blocking_rules={"enabled": False, "block_on": "high"},
    )
    data = _post(
        client,
        api_key_raw,
        action="shell_command",
        data={"command": "psql -h prod -c 'SELECT 1'"},
    )
    assert data["decision"] == "allow"


# --- Framework mapping ---


def test_frameworks_gdpr_pii(client, api_key_raw):
    """PII event maps to GDPR art_30."""
    _set_policy(client, api_key_raw, logging_level="full")
    data = _post(
        client, api_key_raw, action="access_record", data={"email": "user@example.com"}
    )
    assert "gdpr" in data["frameworks"]
    assert "art_30" in data["frameworks"]["gdpr"]


def test_frameworks_gdpr_access_pii(client, api_key_raw):
    """Access action with PII maps to GDPR art_15."""
    _set_policy(client, api_key_raw, logging_level="full")
    data = _post(
        client, api_key_raw, action="access_record", data={"email": "user@example.com"}
    )
    assert "art_15" in data["frameworks"]["gdpr"]


def test_frameworks_gdpr_reasoning(client, api_key_raw):
    """Event with reasoning maps to GDPR art_22."""
    _set_policy(client, api_key_raw, logging_level="full")
    data = _post(
        client,
        api_key_raw,
        action="shell_command",
        data={"command": "echo hi"},
        reasoning="Testing automated decision",
    )
    assert "art_22" in data["frameworks"].get("gdpr", [])


def test_frameworks_ai_act(client, api_key_raw):
    """All events with agent_id map to AI Act art_14."""
    _set_policy(client, api_key_raw, logging_level="full")
    data = _post(client, api_key_raw, action="shell_command", data={"command": "echo hi"})
    assert "ai_act" in data["frameworks"]
    assert "art_14" in data["frameworks"]["ai_act"]


def test_frameworks_ai_act_high_risk(client, api_key_raw):
    """High risk event maps to AI Act art_9."""
    _set_policy(client, api_key_raw, logging_level="full")
    data = _post(
        client,
        api_key_raw,
        action="shell_command",
        data={"command": "psql -h prod -c 'SELECT 1'"},
    )
    assert "art_9" in data["frameworks"]["ai_act"]


def test_frameworks_soc2_disabled_by_default(client, api_key_raw):
    """SOC2 not in frameworks when disabled in policy."""
    _set_policy(
        client,
        api_key_raw,
        logging_level="full",
        frameworks={"gdpr": True, "ai_act": True, "soc2": False},
    )
    data = _post(
        client, api_key_raw, action="shell_command", data={"command": "echo hi"}
    )
    assert "soc2" not in data["frameworks"]


def test_frameworks_soc2_enabled(client, api_key_raw):
    """SOC2 CC6.1 for shell_command when enabled."""
    _set_policy(
        client,
        api_key_raw,
        logging_level="full",
        frameworks={"gdpr": True, "ai_act": True, "soc2": True},
    )
    data = _post(
        client, api_key_raw, action="shell_command", data={"command": "echo hi"}
    )
    assert "soc2" in data["frameworks"]
    assert "CC6.1" in data["frameworks"]["soc2"]


def test_frameworks_soc2_critical(client, api_key_raw):
    """SOC2 CC7.2 for critical events."""
    _set_policy(
        client,
        api_key_raw,
        logging_level="full",
        frameworks={"gdpr": True, "ai_act": True, "soc2": True},
    )
    data = _post(
        client,
        api_key_raw,
        action="shell_command",
        data={"command": "rm -rf /var/data"},
    )
    assert "CC7.2" in data["frameworks"]["soc2"]


def test_frameworks_full_pii_event(client, api_key_raw):
    """Full PII event should have GDPR + AI Act mappings."""
    _set_policy(
        client,
        api_key_raw,
        logging_level="full",
        frameworks={"gdpr": True, "ai_act": True, "soc2": True},
    )
    data = _post(
        client,
        api_key_raw,
        action="access_record",
        data={"email": "user@example.com"},
        reasoning="Customer requested data",
        context={"developer": "dev@company.com"},
    )
    # GDPR
    assert "art_30" in data["frameworks"]["gdpr"]
    assert "art_15" in data["frameworks"]["gdpr"]
    assert "art_22" in data["frameworks"]["gdpr"]
    assert "art_13" in data["frameworks"]["gdpr"]
    # AI Act
    assert "art_14" in data["frameworks"]["ai_act"]
    assert "art_13" in data["frameworks"]["ai_act"]
    # SOC2
    assert "CC6.5" in data["frameworks"]["soc2"]
