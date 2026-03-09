"""CLI entrypoint for agentaudit-hook."""

from __future__ import annotations

import json
import logging
import sys

from agentaudit import AgentAudit, AgentAuditError

from agentaudit_hook.buffer import buffer_event
from agentaudit_hook.mapper import map_session_event, map_tool_event

logger = logging.getLogger(__name__)

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
    """Parse arguments, read hook JSON from stdin, and forward to AgentAudit."""
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        sys.stderr.write(USAGE)
        sys.exit(0)

    command = sys.argv[1]
    if command not in ("pre", "post", "session-start", "session-end"):
        sys.stderr.write(f"Unknown command: {command}\n")
        sys.stderr.write(USAGE)
        sys.exit(1)

    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)

    try:
        hook_data: dict[str, object] = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid JSON on stdin: %s", exc)
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
            sys.stderr.write(f"BLOCKED: {reason}\n")
            sys.exit(2)

    except AgentAuditError as exc:
        logger.warning("AgentAudit API error: %s", exc.message)
        buffer_event(payload)
    except Exception:
        logger.warning("AgentAudit hook error", exc_info=True)
        buffer_event(payload)

    sys.exit(0)
