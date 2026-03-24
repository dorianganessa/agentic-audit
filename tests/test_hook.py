import json

from agentaudit_hook.buffer import buffer_event
from agentaudit_hook.mapper import map_session_event, map_tool_event


def test_mapper_bash():
    """Bash tool maps to shell_command action."""
    hook_data = {
        "session_id": "sess_x",
        "tool_name": "Bash",
        "tool_input": {"command": "psql -h prod-db.internal -c 'SELECT email FROM users'"},
        "hook_event_name": "PostToolUse",
    }
    result = map_tool_event(hook_data)
    assert result["action"] == "shell_command"
    assert result["agent_id"] == "claude-code"
    assert "psql" in result["data"]["command"]
    assert result["context"]["session_id"] == "sess_x"
    assert result["context"]["hook_event"] == "PostToolUse"


def test_mapper_write():
    hook_data = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/tmp/test.py"},
    }
    result = map_tool_event(hook_data)
    assert result["action"] == "file_write"
    assert result["data"]["file_path"] == "/tmp/test.py"


def test_mapper_edit():
    hook_data = {
        "tool_name": "Edit",
        "tool_input": {"file_path": "/tmp/test.py"},
    }
    result = map_tool_event(hook_data)
    assert result["action"] == "file_edit"


def test_mapper_multi_edit():
    hook_data = {
        "tool_name": "MultiEdit",
        "tool_input": {"file_path": "/tmp/test.py"},
    }
    result = map_tool_event(hook_data)
    assert result["action"] == "file_edit"


def test_mapper_read():
    hook_data = {
        "tool_name": "Read",
        "tool_input": {"file_path": "/tmp/test.py"},
    }
    result = map_tool_event(hook_data)
    assert result["action"] == "file_read"


def test_mapper_web_fetch():
    hook_data = {
        "tool_name": "WebFetch",
        "tool_input": {"url": "https://example.com"},
    }
    result = map_tool_event(hook_data)
    assert result["action"] == "web_fetch"
    assert result["data"]["url"] == "https://example.com"


def test_mapper_mcp_tool():
    """MCP connector tool maps to connector_access with connector/operation."""
    hook_data = {
        "tool_name": "mcp__slack__send_message",
        "tool_input": {"channel": "#general", "text": "hello"},
    }
    result = map_tool_event(hook_data)
    assert result["action"] == "connector_access"
    assert result["data"]["connector"] == "slack"
    assert result["data"]["operation"] == "send_message"
    assert result["data"]["channel"] == "#general"


def test_mapper_mcp_google_drive():
    """MCP Google Drive tool maps to connector_access."""
    hook_data = {
        "tool_name": "mcp__google_drive__read_file",
        "tool_input": {"file_id": "abc123"},
    }
    result = map_tool_event(hook_data)
    assert result["action"] == "connector_access"
    assert result["data"]["connector"] == "google_drive"
    assert result["data"]["operation"] == "read_file"
    assert result["data"]["file_id"] == "abc123"


def test_mapper_mcp_salesforce():
    """MCP Salesforce tool maps to connector_access."""
    hook_data = {
        "tool_name": "mcp__salesforce__query",
        "tool_input": {"soql": "SELECT Name, Email FROM Contact"},
    }
    result = map_tool_event(hook_data)
    assert result["action"] == "connector_access"
    assert result["data"]["connector"] == "salesforce"
    assert result["data"]["operation"] == "query"


def test_mapper_mcp_malformed():
    """MCP tool with fewer than 3 parts falls back to mcp_tool_call."""
    hook_data = {
        "tool_name": "mcp__onlytwo",
        "tool_input": {},
    }
    result = map_tool_event(hook_data)
    assert result["action"] == "mcp_tool_call"


def test_mapper_web_search():
    """WebSearch tool maps to web_search action."""
    hook_data = {
        "tool_name": "WebSearch",
        "tool_input": {"query": "market data 2026"},
    }
    result = map_tool_event(hook_data)
    assert result["action"] == "web_search"
    assert result["data"]["query"] == "market data 2026"


def test_mapper_task():
    """Task tool maps to sub_agent_spawn action."""
    hook_data = {
        "tool_name": "Task",
        "tool_input": {"task_description": "Research competitor pricing"},
    }
    result = map_tool_event(hook_data)
    assert result["action"] == "sub_agent_spawn"
    assert result["data"]["task"] == "Research competitor pricing"


def test_mapper_unknown_tool():
    """Unknown tool_name falls back to lowercase."""
    hook_data = {
        "tool_name": "CustomTool",
        "tool_input": {"foo": "bar"},
    }
    result = map_tool_event(hook_data)
    assert result["action"] == "customtool"


def test_mapper_post_with_tool_output():
    """Post hook includes tool_output in data."""
    hook_data = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo hello"},
        "tool_output": "hello\n",
    }
    result = map_tool_event(hook_data)
    assert result["data"]["tool_output"] == "hello\n"


def test_mapper_session_start():
    hook_data = {
        "hook_event_name": "SessionStart",
        "session_id": "sess_123",
    }
    result = map_session_event(hook_data)
    assert result["action"] == "session_start"
    assert result["context"]["session_id"] == "sess_123"


def test_mapper_session_end():
    hook_data = {
        "hook_event_name": "SessionEnd",
        "session_id": "sess_123",
    }
    result = map_session_event(hook_data)
    assert result["action"] == "session_end"


def test_buffer_event(tmp_path):
    """Events are buffered to local JSONL file."""
    buffer_file = tmp_path / "buffer.jsonl"
    payload = {"agent_id": "test", "action": "test_action"}

    buffer_event(payload, buffer_path=buffer_file)

    lines = buffer_file.read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == payload

    # Second event appends
    buffer_event({"agent_id": "test2", "action": "act2"}, buffer_path=buffer_file)
    lines = buffer_file.read_text().strip().splitlines()
    assert len(lines) == 2


def test_cli_post_creates_event(app, api_key_raw, monkeypatch, tmp_path):
    """Hook post subcommand creates an event via the API."""
    import io

    # Isolate buffer so flush_buffer doesn't pick up stale events
    import agentaudit_hook.buffer as buf_mod
    import httpx
    from starlette.testclient import TestClient

    monkeypatch.setattr(buf_mod, "DEFAULT_BUFFER_PATH", tmp_path / "buffer.jsonl")

    tc = TestClient(app)

    # Set full logging so events are persisted and queryable
    tc.put(
        "/v1/org/policy",
        json={"logging_level": "full"},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )

    # Count events before
    before = tc.get("/v1/events", headers={"Authorization": f"Bearer {api_key_raw}"}).json()[
        "total"
    ]

    # Patch AgentAudit to use our test client transport
    import agentaudit.client as client_mod

    original_init = client_mod.AgentAudit.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._client = httpx.Client(
            transport=tc._transport,
            base_url=str(tc.base_url),
            headers={"Authorization": f"Bearer {self._api_key}"},
        )

    monkeypatch.setattr(client_mod.AgentAudit, "__init__", patched_init)
    monkeypatch.setenv("AGENTAUDIT_API_KEY", api_key_raw)
    monkeypatch.setenv("AGENTAUDIT_BASE_URL", str(tc.base_url))

    hook_json = json.dumps(
        {
            "session_id": "sess_test",
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "hook_event_name": "PostToolUse",
        }
    )

    monkeypatch.setattr("sys.stdin", io.StringIO(hook_json))
    monkeypatch.setattr("sys.argv", ["agentaudit-hook", "post"])

    # Prevent sys.exit from killing the test
    import pytest
    from agentaudit_hook.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0

    # Verify the event was actually persisted
    after_resp = tc.get("/v1/events", headers={"Authorization": f"Bearer {api_key_raw}"}).json()
    assert after_resp["total"] == before + 1
    latest = after_resp["events"][0]
    assert latest["action"] == "shell_command"
    assert latest["data"]["command"] == "ls -la"


def test_cli_pre_api_down_buffers(monkeypatch, tmp_path):
    """Hook pre with unreachable API buffers event and exits 0."""
    import io

    import pytest

    hook_json = json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "echo test"},
            "hook_event_name": "PreToolUse",
        }
    )

    monkeypatch.setattr("sys.stdin", io.StringIO(hook_json))
    monkeypatch.setattr("sys.argv", ["agentaudit-hook", "pre"])
    monkeypatch.setenv("AGENTAUDIT_API_KEY", "aa_live_test00000000000000000000")
    monkeypatch.setenv("AGENTAUDIT_BASE_URL", "http://localhost:19999")

    buffer_file = tmp_path / "buffer.jsonl"
    monkeypatch.setattr(
        "agentaudit_hook.cli.buffer_event",
        lambda payload: buffer_event(payload, buffer_path=buffer_file),
    )

    from agentaudit_hook.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0

    lines = buffer_file.read_text().strip().splitlines()
    assert len(lines) == 1
    buffered = json.loads(lines[0])
    assert buffered["action"] == "shell_command"


def test_cli_pre_blocking(app, api_key_raw, monkeypatch):
    """Hook pre with paranoid+blocking policy returns exit code 2 for high risk."""
    import io

    import httpx
    import pytest
    from starlette.testclient import TestClient

    tc = TestClient(app)

    # Set paranoid policy with blocking on high
    tc.put(
        "/v1/org/policy",
        json={
            "logging_level": "paranoid",
            "blocking_rules": {"enabled": True, "block_on": "high"},
        },
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )

    import agentaudit.client as client_mod

    original_init = client_mod.AgentAudit.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._client = httpx.Client(
            transport=tc._transport,
            base_url=str(tc.base_url),
            headers={"Authorization": f"Bearer {self._api_key}"},
        )

    monkeypatch.setattr(client_mod.AgentAudit, "__init__", patched_init)
    monkeypatch.setenv("AGENTAUDIT_API_KEY", api_key_raw)
    monkeypatch.setenv("AGENTAUDIT_BASE_URL", str(tc.base_url))

    # High-risk command: psql -h prod
    hook_json = json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "psql -h prod-db -c 'SELECT * FROM users'"},
            "hook_event_name": "PreToolUse",
        }
    )

    monkeypatch.setattr("sys.stdin", io.StringIO(hook_json))
    monkeypatch.setattr("sys.argv", ["agentaudit-hook", "pre"])

    from agentaudit_hook.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2
