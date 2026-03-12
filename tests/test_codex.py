"""Tests for the Codex transcript parser integration."""

import json

import httpx
from agentaudit.integrations.codex_parser import CodexTranscriptParser
from starlette.testclient import TestClient


def _make_parser(app, api_key: str) -> CodexTranscriptParser:
    """Create a parser wired to the test app."""
    tc = TestClient(app)
    parser = CodexTranscriptParser(api_key=api_key, agent_id="codex")
    parser.audit._client = httpx.Client(
        transport=tc._transport,
        base_url=str(tc.base_url).rstrip("/"),
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return parser


# ── parse_entry mapping ─────────────────────────────────────────────


def test_parse_shell_command():
    """Shell tool_call maps to shell_command."""
    parser = CodexTranscriptParser(api_key="test")
    result = parser.parse_entry(
        {
            "type": "tool_call",
            "name": "shell",
            "arguments": {"command": "ls -la"},
        }
    )
    assert result is not None
    assert result["action"] == "shell_command"
    assert result["data"]["command"] == "ls -la"
    assert result["agent_id"] == "codex"
    assert result["context"]["tool"] == "codex"


def test_parse_apply_patch():
    """apply_patch maps to file_edit."""
    parser = CodexTranscriptParser(api_key="test")
    result = parser.parse_entry(
        {
            "type": "tool_call",
            "name": "apply_patch",
            "arguments": {"file_path": "/tmp/test.py"},
        }
    )
    assert result is not None
    assert result["action"] == "file_edit"
    assert result["data"]["file_path"] == "/tmp/test.py"


def test_parse_read_file():
    """read_file maps to file_read."""
    parser = CodexTranscriptParser(api_key="test")
    result = parser.parse_entry(
        {
            "type": "tool_call",
            "name": "read_file",
            "arguments": {"file_path": "/etc/passwd"},
        }
    )
    assert result is not None
    assert result["action"] == "file_read"
    assert result["data"]["file_path"] == "/etc/passwd"


def test_parse_write_file():
    """write_file maps to file_write."""
    parser = CodexTranscriptParser(api_key="test")
    result = parser.parse_entry(
        {
            "type": "tool_call",
            "name": "write_file",
            "arguments": {"file_path": "/tmp/out.txt"},
        }
    )
    assert result is not None
    assert result["action"] == "file_write"


def test_parse_function_call_type():
    """function_call type is also handled."""
    parser = CodexTranscriptParser(api_key="test")
    result = parser.parse_entry(
        {
            "type": "function_call",
            "name": "shell",
            "arguments": {"command": "echo hi"},
        }
    )
    assert result is not None
    assert result["action"] == "shell_command"


def test_parse_unknown_tool():
    """Unknown tool name falls back to lowercase."""
    parser = CodexTranscriptParser(api_key="test")
    result = parser.parse_entry(
        {
            "type": "tool_call",
            "name": "custom_tool",
            "arguments": {"foo": "bar"},
        }
    )
    assert result is not None
    assert result["action"] == "custom_tool"


def test_parse_with_session_id():
    """Session ID is included in context when present."""
    parser = CodexTranscriptParser(api_key="test")
    result = parser.parse_entry(
        {
            "type": "tool_call",
            "name": "shell",
            "arguments": {"command": "pwd"},
            "session_id": "sess_codex_123",
        }
    )
    assert result is not None
    assert result["context"]["session_id"] == "sess_codex_123"


def test_parse_string_arguments():
    """String arguments are parsed as JSON or wrapped in raw."""
    parser = CodexTranscriptParser(api_key="test")
    # Valid JSON string
    result = parser.parse_entry(
        {
            "type": "tool_call",
            "name": "shell",
            "arguments": '{"command": "ls"}',
        }
    )
    assert result is not None
    assert result["data"]["command"] == "ls"

    # Non-JSON string gets wrapped in {"raw": ...}
    result = parser.parse_entry(
        {
            "type": "tool_call",
            "name": "shell",
            "arguments": "just a string",
        }
    )
    assert result is not None
    # The raw string becomes str({"raw": "just a string"}) via the command extraction
    assert "just a string" in str(result["data"]["command"])


def test_parse_skips_non_tool_entries():
    """Non tool_call/function_call entries return None."""
    parser = CodexTranscriptParser(api_key="test")
    assert parser.parse_entry({"type": "message", "content": "hello"}) is None
    assert parser.parse_entry({"type": "system"}) is None
    assert parser.parse_entry({}) is None


def test_parse_alternate_arg_keys():
    """Handles 'args' and 'input' keys as alternatives to 'arguments'."""
    parser = CodexTranscriptParser(api_key="test")

    result = parser.parse_entry(
        {
            "type": "tool_call",
            "name": "shell",
            "args": {"command": "whoami"},
        }
    )
    assert result is not None
    assert result["data"]["command"] == "whoami"

    result = parser.parse_entry(
        {
            "type": "tool_call",
            "name": "shell",
            "input": {"command": "date"},
        }
    )
    assert result is not None
    assert result["data"]["command"] == "date"


# ── File scanning ────────────────────────────────────────────────────


def test_scan_file(tmp_path, app, api_key_raw):
    """_scan_file reads new lines from a JSONL transcript."""
    parser = _make_parser(app, api_key_raw)

    # Set full logging
    tc = TestClient(app)
    tc.put(
        "/v1/org/policy",
        json={"logging_level": "full"},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )

    # Write a transcript file
    transcript = tmp_path / "session.jsonl"
    entries = [
        {"type": "tool_call", "name": "shell", "arguments": {"command": "echo hello"}},
        {"type": "message", "content": "thinking..."},
        {"type": "tool_call", "name": "read_file", "arguments": {"file_path": "/tmp/x"}},
    ]
    transcript.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    parser._scan_file(transcript)

    # Should have forwarded 2 tool_call entries (message is skipped)
    resp = tc.get("/v1/events", headers={"Authorization": f"Bearer {api_key_raw}"})
    events = resp.json()["events"]
    actions = [e["action"] for e in events]
    assert "shell_command" in actions
    assert "file_read" in actions


def test_scan_file_incremental(tmp_path, app, api_key_raw):
    """_scan_file only reads new lines on subsequent calls."""
    parser = _make_parser(app, api_key_raw)

    tc = TestClient(app)
    tc.put(
        "/v1/org/policy",
        json={"logging_level": "full"},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )

    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        json.dumps({"type": "tool_call", "name": "shell", "arguments": {"command": "first"}}) + "\n"
    )

    parser._scan_file(transcript)

    # Get count after first scan
    resp1 = tc.get("/v1/events", headers={"Authorization": f"Bearer {api_key_raw}"})
    count1 = resp1.json()["total"]

    # Append a new entry
    with open(transcript, "a") as f:
        entry = {"type": "tool_call", "name": "shell", "arguments": {"command": "second"}}
        f.write(json.dumps(entry) + "\n")

    parser._scan_file(transcript)

    resp2 = tc.get("/v1/events", headers={"Authorization": f"Bearer {api_key_raw}"})
    count2 = resp2.json()["total"]

    assert count2 == count1 + 1


def test_scan_directory(tmp_path, app, api_key_raw):
    """_scan_directory finds and scans JSONL files in sessions subdir."""
    parser = _make_parser(app, api_key_raw)
    parser.codex_home = tmp_path

    tc = TestClient(app)
    tc.put(
        "/v1/org/policy",
        json={"logging_level": "full"},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    # Two session files
    (sessions_dir / "sess1.jsonl").write_text(
        json.dumps({"type": "tool_call", "name": "shell", "arguments": {"command": "ls"}}) + "\n"
    )
    entry2 = {"type": "tool_call", "name": "read_file", "arguments": {"file_path": "/tmp/x"}}
    (sessions_dir / "sess2.jsonl").write_text(json.dumps(entry2) + "\n")

    parser._scan_directory()

    resp = tc.get("/v1/events", headers={"Authorization": f"Bearer {api_key_raw}"})
    events = resp.json()["events"]
    actions = [e["action"] for e in events]
    assert "shell_command" in actions
    assert "file_read" in actions
