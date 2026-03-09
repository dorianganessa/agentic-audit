"""Tests for the Codex transcript parser."""

import json

import httpx
from agentaudit.integrations.codex_parser import CodexTranscriptParser
from starlette.testclient import TestClient


def test_parse_shell_command():
    """Codex shell tool_call maps to shell_command action."""
    parser = CodexTranscriptParser(api_key="test")
    entry = {
        "type": "tool_call",
        "name": "shell",
        "arguments": {"command": "ls -la"},
        "session_id": "sess_codex_1",
    }
    result = parser.parse_entry(entry)
    assert result is not None
    assert result["action"] == "shell_command"
    assert result["data"]["command"] == "ls -la"
    assert result["context"]["tool"] == "codex"
    assert result["context"]["session_id"] == "sess_codex_1"


def test_parse_apply_patch():
    """Codex apply_patch maps to file_edit."""
    parser = CodexTranscriptParser(api_key="test")
    entry = {
        "type": "tool_call",
        "name": "apply_patch",
        "arguments": {"file_path": "/tmp/test.py"},
    }
    result = parser.parse_entry(entry)
    assert result is not None
    assert result["action"] == "file_edit"
    assert result["data"]["file_path"] == "/tmp/test.py"


def test_parse_read_file():
    """Codex read_file maps to file_read."""
    parser = CodexTranscriptParser(api_key="test")
    entry = {
        "type": "tool_call",
        "name": "read_file",
        "arguments": {"path": "/tmp/data.txt"},
    }
    result = parser.parse_entry(entry)
    assert result is not None
    assert result["action"] == "file_read"


def test_parse_unknown_tool():
    """Unknown tool name is lowercased."""
    parser = CodexTranscriptParser(api_key="test")
    entry = {
        "type": "tool_call",
        "name": "custom_tool",
        "arguments": {"foo": "bar"},
    }
    result = parser.parse_entry(entry)
    assert result is not None
    assert result["action"] == "custom_tool"


def test_parse_non_tool_entry():
    """Non-tool entries return None."""
    parser = CodexTranscriptParser(api_key="test")
    entry = {"type": "message", "content": "hello"}
    result = parser.parse_entry(entry)
    assert result is None


def test_parse_function_call_type():
    """function_call type also works."""
    parser = CodexTranscriptParser(api_key="test")
    entry = {
        "type": "function_call",
        "name": "shell",
        "arguments": '{"command": "echo hi"}',
    }
    result = parser.parse_entry(entry)
    assert result is not None
    assert result["action"] == "shell_command"
    assert result["data"]["command"] == "echo hi"


def test_scan_jsonl_file(tmp_path, app, api_key_raw):
    """Scanner reads JSONL file and creates events via SDK."""
    tc = TestClient(app)

    # Set full policy
    tc.put(
        "/v1/org/policy",
        json={"logging_level": "full"},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )

    # Create a fake Codex sessions directory with a JSONL file
    sessions_dir = tmp_path / ".codex" / "sessions"
    sessions_dir.mkdir(parents=True)
    jsonl_file = sessions_dir / "session_001.jsonl"
    entries = [
        {"type": "tool_call", "name": "shell", "arguments": {"command": "echo test"}},
        {"type": "message", "content": "thinking..."},
        {"type": "tool_call", "name": "apply_patch", "arguments": {"file_path": "/tmp/x.py"}},
    ]
    jsonl_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    # Create parser with patched SDK client
    parser = CodexTranscriptParser(
        api_key=api_key_raw,
        codex_home=str(tmp_path / ".codex"),
    )
    parser.audit._client = httpx.Client(
        transport=tc._transport,
        base_url=str(tc.base_url).rstrip("/"),
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )

    # Scan the directory
    parser._scan_directory()

    # Verify events were created
    resp = tc.get("/v1/events", headers={"Authorization": f"Bearer {api_key_raw}"})
    events = resp.json()["events"]

    actions = [e["action"] for e in events]
    assert "shell_command" in actions
    assert "file_edit" in actions

    # Second scan should not duplicate events (offset tracking)
    parser._scan_directory()
    resp2 = tc.get("/v1/events", headers={"Authorization": f"Bearer {api_key_raw}"})
    assert resp2.json()["total"] == resp.json()["total"]
