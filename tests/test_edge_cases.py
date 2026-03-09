"""Edge case tests for improved coverage."""

from agentaudit_api.models.organization import DEFAULT_POLICY
from agentaudit_api.services.event_service import _should_block, _should_store
from agentaudit_api.services.framework_mapper import map_frameworks
from agentaudit_api.services.pii_detector import detect_pii
from agentaudit_api.services.risk_scorer import score_risk
from agentaudit_hook.buffer import buffer_event
from agentaudit_hook.mapper import map_session_event, map_tool_event

# --- Hook mapper edge cases ---


def test_mapper_empty_tool_input():
    """Empty tool_input should not crash."""
    result = map_tool_event(
        {
            "tool_name": "Bash",
            "tool_input": {},
        }
    )
    assert result["action"] == "shell_command"
    assert result["data"]["command"] == ""


def test_mapper_missing_tool_name():
    """Missing tool_name falls back to empty string lowercase."""
    result = map_tool_event({"tool_input": {}})
    assert result["action"] == ""


def test_mapper_tool_output_truncation():
    """Long tool_output is truncated to 4000 chars."""
    long_output = "x" * 5000
    result = map_tool_event(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "echo test"},
            "tool_output": long_output,
        }
    )
    assert len(result["data"]["tool_output"]) < 5000
    assert "[truncated]" in result["data"]["tool_output"]


def test_mapper_session_no_session_id():
    """Session event without session_id should still work."""
    result = map_session_event({"hook_event_name": "SessionStart"})
    assert result["action"] == "session_start"
    assert "session_id" not in result["context"]


def test_mapper_mcp_four_parts():
    """MCP tool with 4+ parts: mcp__org__connector__action."""
    result = map_tool_event(
        {
            "tool_name": "mcp__claude_ai__Slack__send_message",
            "tool_input": {"channel": "#general"},
        }
    )
    assert result["action"] == "connector_access"
    assert result["data"]["connector"] == "claude_ai"
    assert result["data"]["operation"] == "Slack"


# --- PII edge cases ---


def test_pii_empty_data():
    """Empty dicts should return no PII."""
    result = detect_pii({}, {})
    assert result.detected is False
    assert result.fields == []


def test_pii_non_string_values():
    """Non-string values in data should not crash PII detection."""
    result = detect_pii({"count": 42, "active": True, "items": [1, 2, 3]}, {})
    assert result.detected is False


def test_pii_ip_like_version():
    """Version strings like '3.12.7' should not match (only 3 octets)."""
    result = detect_pii({"version": "3.12.7"}, {})
    assert result.detected is False


def test_pii_aws_access_key():
    """AWS access key pattern detection."""
    result = detect_pii({"key": "AKIAIOSFODNN7EXAMPLE"}, {})
    assert result.detected is True
    assert "api_key" in result.fields


def test_pii_slack_token():
    """Slack token pattern detection."""
    # Construct token dynamically to avoid push protection false positive
    fake_token = "xoxb-" + "0" * 12 + "-" + "0" * 13 + "-" + "A" * 24
    result = detect_pii({"token": fake_token}, {})
    assert result.detected is True
    assert "api_key" in result.fields


# --- Risk scorer edge cases ---


def test_risk_empty_data():
    """Empty data dict should return low risk."""
    result = score_risk("unknown_action", {}, {}, pii_detected=False)
    assert result == "low"


def test_risk_credential_in_nested_data():
    """Credential pattern in nested data should be detected."""
    result = score_risk(
        "shell_command",
        {"config": {"auth": {"token": "ghp_ABCDefGHIjklMNOpqrSTUvwx12345"}}},
        {},
        pii_detected=False,
    )
    assert result == "critical"


def test_risk_password_action():
    """Action containing 'password' is critical."""
    result = score_risk("reset_password", {}, {}, pii_detected=False)
    assert result == "critical"


def test_risk_file_write_token():
    """Writing to a file with 'token' in path is high risk."""
    result = score_risk(
        "file_write", {"file_path": "/app/config/token.json"}, {}, pii_detected=False
    )
    assert result == "high"


def test_risk_file_read_key():
    """Reading a .key file is high risk."""
    result = score_risk(
        "file_read", {"file_path": "/etc/ssl/private/server.key"}, {}, pii_detected=False
    )
    assert result == "high"


# --- Storage policy edge cases ---


def test_should_store_full_low_risk():
    """Full policy stores even low-risk events."""
    assert _should_store("full", "low", pii_detected=False) is True


def test_should_store_paranoid():
    """Paranoid policy stores everything."""
    assert _should_store("paranoid", "low", pii_detected=False) is True


def test_should_store_minimal_pii():
    """Minimal stores events with PII."""
    assert _should_store("minimal", "low", pii_detected=True) is True


def test_should_store_minimal_no_pii():
    """Minimal does NOT store events without PII."""
    assert _should_store("minimal", "high", pii_detected=False) is False


def test_should_store_standard_medium():
    """Standard stores medium risk."""
    assert _should_store("standard", "medium", pii_detected=False) is True


def test_should_store_standard_low_no_pii():
    """Standard does NOT store low risk without PII."""
    assert _should_store("standard", "low", pii_detected=False) is False


# --- Blocking policy edge cases ---


def test_should_block_not_paranoid():
    """Non-paranoid policy never blocks."""
    policy = {
        **DEFAULT_POLICY,
        "logging_level": "full",
        "blocking_rules": {"enabled": True, "block_on": "high"},
    }
    blocked, reason = _should_block(policy, "critical")
    assert blocked is False


def test_should_block_not_enabled():
    """Paranoid with blocking disabled never blocks."""
    policy = {
        **DEFAULT_POLICY,
        "logging_level": "paranoid",
        "blocking_rules": {"enabled": False, "block_on": "high"},
    }
    blocked, reason = _should_block(policy, "critical")
    assert blocked is False


def test_should_block_below_threshold():
    """Paranoid with block_on=critical does not block high."""
    policy = {
        **DEFAULT_POLICY,
        "logging_level": "paranoid",
        "blocking_rules": {"enabled": True, "block_on": "critical"},
    }
    blocked, reason = _should_block(policy, "high")
    assert blocked is False


def test_should_block_at_threshold():
    """Paranoid with block_on=high blocks high."""
    policy = {
        **DEFAULT_POLICY,
        "logging_level": "paranoid",
        "blocking_rules": {"enabled": True, "block_on": "high"},
    }
    blocked, reason = _should_block(policy, "high")
    assert blocked is True
    assert reason is not None


def test_should_block_above_threshold():
    """Paranoid with block_on=medium blocks high."""
    policy = {
        **DEFAULT_POLICY,
        "logging_level": "paranoid",
        "blocking_rules": {"enabled": True, "block_on": "medium"},
    }
    blocked, reason = _should_block(policy, "high")
    assert blocked is True


# --- Framework mapper edge cases ---


def test_frameworks_all_disabled():
    """No frameworks enabled returns empty dict."""
    result = map_frameworks(
        action="shell_command",
        risk_level="high",
        pii_detected=True,
        reasoning="test",
        context={},
        agent_id="test",
        enabled_frameworks={"gdpr": False, "ai_act": False, "soc2": False},
    )
    assert result == {}


def test_frameworks_gdpr_delete_pii():
    """Delete action with PII maps to GDPR art_17."""
    result = map_frameworks(
        action="delete_record",
        risk_level="medium",
        pii_detected=True,
        reasoning=None,
        context={},
        agent_id="test",
        enabled_frameworks={"gdpr": True, "ai_act": False, "soc2": False},
    )
    assert "art_17" in result.get("gdpr", [])
    assert "art_30" in result.get("gdpr", [])


def test_frameworks_ai_act_reasoning():
    """AI Act art_13 for events with reasoning."""
    result = map_frameworks(
        action="test",
        risk_level="low",
        pii_detected=False,
        reasoning="Automated decision",
        context={},
        agent_id="agent-1",
        enabled_frameworks={"gdpr": False, "ai_act": True, "soc2": False},
    )
    assert "art_13" in result.get("ai_act", [])
    assert "art_14" in result.get("ai_act", [])


def test_frameworks_soc2_pii():
    """SOC2 CC6.5 for PII events."""
    result = map_frameworks(
        action="test",
        risk_level="low",
        pii_detected=True,
        reasoning=None,
        context={},
        agent_id="test",
        enabled_frameworks={"gdpr": False, "ai_act": False, "soc2": True},
    )
    assert "CC6.5" in result.get("soc2", [])


# --- Buffer edge cases ---


def test_buffer_creates_directory(tmp_path):
    """Buffer creates parent directory if it doesn't exist."""
    buffer_file = tmp_path / "nested" / "dir" / "buffer.jsonl"
    buffer_event({"action": "test"}, buffer_path=buffer_file)
    assert buffer_file.exists()
    lines = buffer_file.read_text().strip().splitlines()
    assert len(lines) == 1


def test_buffer_returns_path(tmp_path):
    """Buffer returns the path it wrote to."""
    buffer_file = tmp_path / "buffer.jsonl"
    result = buffer_event({"action": "test"}, buffer_path=buffer_file)
    assert result == buffer_file
