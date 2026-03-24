"""Local buffer for events when the AgenticAudit API is unreachable."""

from __future__ import annotations

import fcntl
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_BUFFER_PATH = Path.home() / ".agentaudit" / "buffer.jsonl"

# Max buffer size: 50 MB. Oldest events are dropped when exceeded.
MAX_BUFFER_BYTES = 50 * 1024 * 1024

logger = logging.getLogger(__name__)


def _ensure_dir(path: Path) -> None:
    """Create buffer directory with restricted permissions (owner-only)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)


def buffer_event(event_payload: dict[str, Any], buffer_path: Path | None = None) -> Path:
    """Append an event payload as a JSON line to the local buffer file.

    Args:
        event_payload: The event dict to buffer locally.
        buffer_path: Override path for the buffer file.

    Returns:
        The path where the event was written.
    """
    path = buffer_path or DEFAULT_BUFFER_PATH
    _ensure_dir(path)

    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        line = json.dumps(event_payload) + "\n"

        # Enforce max buffer size: drop if buffer is already too large
        try:
            size = os.fstat(fd).st_size
        except OSError:
            size = 0
        if size + len(line) > MAX_BUFFER_BYTES:
            logger.warning("Buffer at %d bytes (limit %d), dropping event", size, MAX_BUFFER_BYTES)
            return path

        os.write(fd, line.encode())
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    return path


def flush_buffer(
    client: Any,
    buffer_path: Path | None = None,
) -> int:
    """Send buffered events to the API and remove them from the buffer.

    Uses file locking to prevent race conditions with concurrent hook processes.

    Args:
        client: An ``AgentAudit`` SDK instance.
        buffer_path: Override path for the buffer file.

    Returns:
        Number of events successfully flushed.
    """
    path = buffer_path or DEFAULT_BUFFER_PATH
    if not path.exists() or path.stat().st_size == 0:
        return 0

    # Lock the buffer file during the entire read-flush-write cycle
    fd = os.open(str(path), os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)

        with open(fd, closefd=False) as f:
            lines = f.read().strip().splitlines()

        if not lines:
            return 0

        flushed = 0
        failed: list[str] = []

        for line in lines:
            try:
                payload = json.loads(line)
                client.log(**payload)
                flushed += 1
            except json.JSONDecodeError:
                logger.debug("Skipping malformed buffer line")
            except Exception:
                logger.debug("Failed to flush buffered event, keeping for retry", exc_info=True)
                failed.append(line)

        # Atomically replace buffer contents using a temp file in the same dir
        if failed:
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=str(path.parent), suffix=".tmp",
            )
            try:
                os.write(tmp_fd, ("\n".join(failed) + "\n").encode())
                os.close(tmp_fd)
                os.chmod(tmp_path, 0o600)
                os.rename(tmp_path, str(path))
            except OSError:
                os.close(tmp_fd)
                os.unlink(tmp_path)
                raise
        else:
            path.unlink(missing_ok=True)

        if flushed:
            logger.info("Flushed %d buffered events (%d remaining)", flushed, len(failed))

        return flushed
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
