"""Map Claude Code / Cowork hook JSON to AuditEvent fields."""

from __future__ import annotations

import contextlib
import getpass
import os
import socket
from typing import Any


def _get_user_context() -> dict[str, str]:
    """Collect user/machine identity for event attribution.

    Priority for user identity:
      1. AGENTAUDIT_USER_EMAIL env var (explicit, enterprise-friendly)
      2. AGENTAUDIT_USER_ID env var (explicit)
      3. OS username (automatic fallback)

    Machine identity is always included via hostname.
    """
    ctx: dict[str, str] = {"tool": "claude_code"}

    # Machine identity
    ctx["hostname"] = socket.gethostname()

    # User identity — explicit env vars take priority
    user_email = os.environ.get("AGENTAUDIT_USER_EMAIL", "")
    user_id = os.environ.get("AGENTAUDIT_USER_ID", "")
    if user_email:
        ctx["user_email"] = user_email
    if user_id:
        ctx["user_id"] = user_id

    # Always include OS username as fallback identity
    with contextlib.suppress(Exception):
        ctx["os_user"] = getpass.getuser()

    return ctx


def map_tool_event(hook_data: dict[str, object]) -> dict[str, Any]:
    """Transform a tool use hook JSON into an AuditEvent create payload.

    Args:
        hook_data: Raw JSON from Claude Code / Cowork hook stdin.

    Returns:
        A dict with keys: agent_id, action, data, context, reasoning.
    """
    tool_name = str(hook_data.get("tool_name", ""))
    tool_input: dict[str, Any] = hook_data.get("tool_input", {}) or {}  # type: ignore[assignment]
    tool_output = hook_data.get("tool_output")
    session_id = hook_data.get("session_id")
    hook_event_name = str(hook_data.get("hook_event_name", ""))

    action, data = _map_action_data(tool_name, tool_input)

    if tool_output is not None:
        data["tool_output"] = _truncate(tool_output, max_len=4000)

    context = _get_user_context()
    if session_id:
        context["session_id"] = str(session_id)
    if hook_event_name:
        context["hook_event"] = hook_event_name

    return {
        "agent_id": "claude-code",
        "action": action,
        "data": data,
        "context": context,
    }


def map_session_event(hook_data: dict[str, object]) -> dict[str, Any]:
    """Transform a session start/end hook JSON into an AuditEvent create payload.

    Args:
        hook_data: Raw JSON from Claude Code / Cowork session hook stdin.
    """
    hook_event_name = str(hook_data.get("hook_event_name", ""))
    session_id = hook_data.get("session_id")

    action = "session_start" if "Start" in hook_event_name else "session_end"

    context = _get_user_context()
    if session_id:
        context["session_id"] = str(session_id)

    return {
        "agent_id": "claude-code",
        "action": action,
        "data": {},
        "context": context,
    }


def _map_action_data(tool_name: str, tool_input: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Map tool_name to action string and extract relevant data."""
    if tool_name == "Bash":
        return "shell_command", {
            "command": tool_input.get("command", ""),
            "working_dir": tool_input.get("working_dir"),
            "exit_code": tool_input.get("exit_code"),
        }

    if tool_name == "Write":
        return "file_write", {
            "file_path": tool_input.get("file_path", ""),
        }

    if tool_name in ("Edit", "MultiEdit"):
        return "file_edit", {
            "file_path": tool_input.get("file_path", ""),
        }

    if tool_name == "Read":
        return "file_read", {
            "file_path": tool_input.get("file_path", ""),
        }

    if tool_name == "WebFetch":
        return "web_fetch", {
            "url": tool_input.get("url", ""),
        }

    if tool_name == "WebSearch":
        return "web_search", {
            "query": tool_input.get("query", ""),
        }

    if tool_name == "Task":
        return "sub_agent_spawn", {
            "task": tool_input.get("task_description", ""),
        }

    # MCP connector pattern: mcp__<connector>__<action>
    if tool_name.startswith("mcp__"):
        return _map_mcp_tool(tool_name, tool_input)

    # Fallback: lowercase tool name
    return tool_name.lower(), {"tool_input": tool_input}


def _map_mcp_tool(tool_name: str, tool_input: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Map MCP connector tool calls to AgenticAudit actions.

    Parses ``mcp__<connector>__<operation>`` into a ``connector_access``
    action with connector and operation metadata.
    """
    parts = tool_name.split("__")
    if len(parts) >= 3:
        connector = parts[1]
        operation = parts[2]
        return (
            "connector_access",
            {
                "connector": connector,
                "operation": operation,
                **tool_input,
            },
        )
    return "mcp_tool_call", {"tool_name": tool_name, "tool_input": tool_input}


def _truncate(value: object, max_len: int) -> object:
    """Truncate string values to max_len."""
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + "... [truncated]"
    return value
