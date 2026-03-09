"""CLI entrypoint for agentaudit-hook."""

from __future__ import annotations

import json
import sys

from agentaudit import AgentAudit, AgentAuditError

from agentaudit_hook.buffer import buffer_event
from agentaudit_hook.mapper import map_session_event, map_tool_event

USAGE = """\
Usage: agentaudit-hook <command>

Commands:
  pre             PreToolUse hook — log tool call before execution
  post            PostToolUse hook — log tool call after execution
  session-start   SessionStart hook
  session-end     SessionEnd hook

Reads JSON from stdin. Requires AGENTAUDIT_API_KEY env var.
"""


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(USAGE, file=sys.stderr)
        sys.exit(0)

    command = sys.argv[1]
    if command not in ("pre", "post", "session-start", "session-end"):
        print(f"Unknown command: {command}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)

    try:
        hook_data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON on stdin: {e}", file=sys.stderr)
        sys.exit(0)

    if command in ("session-start", "session-end"):
        payload = map_session_event(hook_data)
    else:
        payload = map_tool_event(hook_data)

    try:
        client = AgentAudit()
        event = client.log(**payload)

        # For pre hooks: check if the action was blocked
        if command == "pre" and event.decision == "block":
            reason = event.reason or "Action blocked by policy"
            print(f"BLOCKED: {reason}", file=sys.stderr)
            sys.exit(2)

    except AgentAuditError as e:
        print(f"AgentAudit API error: {e.message}", file=sys.stderr)
        buffer_event(payload)
    except Exception as e:  # noqa: BLE001
        print(f"AgentAudit hook error: {e}", file=sys.stderr)
        buffer_event(payload)

    sys.exit(0)
