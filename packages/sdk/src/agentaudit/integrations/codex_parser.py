"""Codex transcript parser — tails Codex session files and forwards events to AgentAudit."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from agentaudit.client import AgentAudit

logger = logging.getLogger(__name__)

# Map Codex tool names to AgentAudit action types
_TOOL_MAP: dict[str, str] = {
    "shell": "shell_command",
    "apply_patch": "file_edit",
    "read_file": "file_read",
    "write_file": "file_write",
    "web_fetch": "web_fetch",
}


class CodexTranscriptParser:
    """Background process that tails Codex session transcripts
    and forwards events to AgentAudit."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        codex_home: str = "~/.codex",
        agent_id: str = "codex",
        poll_interval: float = 1.0,
    ):
        self.audit = AgentAudit(api_key=api_key, base_url=base_url)
        self.codex_home = Path(codex_home).expanduser()
        self.agent_id = agent_id
        self.poll_interval = poll_interval
        self._running = False
        self._file_offsets: dict[Path, int] = {}

    def parse_entry(self, entry: dict) -> dict | None:
        """Map a Codex transcript entry to an AuditEvent create payload.

        Returns None if the entry is not a loggable tool call.
        """
        entry_type = entry.get("type", "")

        # Handle tool call entries
        if entry_type in ("tool_call", "function_call"):
            tool_name = entry.get("name", entry.get("tool", ""))
            args = entry.get("arguments", entry.get("args", entry.get("input", {})))
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, TypeError):
                    args = {"raw": args}

            action = _TOOL_MAP.get(tool_name, tool_name.lower() if tool_name else "unknown")
            data = _extract_data(action, tool_name, args)
            session_id = entry.get("session_id")

            context: dict = {"tool": "codex"}
            if session_id:
                context["session_id"] = session_id

            return {
                "agent_id": self.agent_id,
                "action": action,
                "data": data,
                "context": context,
            }

        return None

    def _scan_file(self, path: Path) -> None:
        """Read new lines from a JSONL file and forward them."""
        offset = self._file_offsets.get(path, 0)
        try:
            size = path.stat().st_size
        except OSError:
            return
        if size <= offset:
            return

        try:
            with open(path) as f:
                f.seek(offset)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = self.parse_entry(entry)
                    if payload is not None:
                        try:
                            self.audit.log(**payload)
                        except Exception:
                            logger.exception("Failed to forward Codex event")
                self._file_offsets[path] = f.tell()
        except OSError:
            logger.exception("Error reading %s", path)

    def _scan_directory(self) -> None:
        """Scan for JSONL files in the Codex sessions directory."""
        sessions_dir = self.codex_home / "sessions"
        if not sessions_dir.is_dir():
            return
        for jsonl_file in sessions_dir.glob("*.jsonl"):
            self._scan_file(jsonl_file)

    def start(self) -> None:
        """Start watching for new transcript entries. Runs until stopped."""
        self._running = True
        logger.info("Watching Codex transcripts at %s", self.codex_home)
        while self._running:
            self._scan_directory()
            time.sleep(self.poll_interval)

    def stop(self) -> None:
        """Stop the watcher loop."""
        self._running = False


def _extract_data(action: str, tool_name: str, args: dict) -> dict:
    """Extract relevant data fields based on the action type."""
    if action == "shell_command":
        return {
            "command": args.get("command", args.get("cmd", str(args))),
        }
    if action in ("file_read", "file_write", "file_edit"):
        return {
            "file_path": args.get("file_path", args.get("path", args.get("file", ""))),
        }
    return {"tool_name": tool_name, "args": args}


def watch_codex(
    api_key: str | None = None,
    base_url: str | None = None,
    codex_home: str = "~/.codex",
) -> None:
    """CLI entrypoint: run the Codex transcript watcher."""
    parser = CodexTranscriptParser(
        api_key=api_key or os.environ.get("AGENTAUDIT_API_KEY", ""),
        base_url=base_url or os.environ.get("AGENTAUDIT_BASE_URL"),
        codex_home=codex_home,
    )
    try:
        parser.start()
    except KeyboardInterrupt:
        parser.stop()
