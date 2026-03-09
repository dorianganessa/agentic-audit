"""Local buffer for events when the API is unreachable."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_BUFFER_PATH = Path.home() / ".agentaudit" / "buffer.jsonl"


def buffer_event(event_payload: dict, buffer_path: Path | None = None) -> Path:
    """Append an event payload as a JSON line to the local buffer file."""
    path = buffer_path or DEFAULT_BUFFER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(event_payload) + "\n")
    return path
