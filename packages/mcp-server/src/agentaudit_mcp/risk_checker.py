"""Offline risk check — lightweight local scorer without importing the API package."""

from __future__ import annotations

import re
from typing import Any

RISK_LEVELS: tuple[str, ...] = ("low", "medium", "high", "critical")
_RISK_ORDER: dict[str, int] = {level: i for i, level in enumerate(RISK_LEVELS)}

_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_CRED_PATTERNS = [
    re.compile(r"sk_live_[a-zA-Z0-9]+"),
    re.compile(r"ghp_[a-zA-Z0-9]+"),
    re.compile(r"AKIA[A-Z0-9]+"),
    re.compile(r"password\s*[:=]\s*\S+"),
]


def _flatten(data: object) -> str:
    """Recursively flatten a data structure to a single string."""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        return " ".join(_flatten(v) for v in data.values())
    if isinstance(data, list):
        return " ".join(_flatten(v) for v in data)
    return str(data) if data is not None else ""


def _has_pii(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check for PII patterns in data."""
    text = _flatten(data)
    fields: list[str] = []
    if _EMAIL.search(text):
        fields.append("email")
    return bool(fields), fields


def _has_creds(data: dict[str, Any]) -> bool:
    """Check for credential patterns in data."""
    text = _flatten(data)
    return any(p.search(text) for p in _CRED_PATTERNS)


def check_risk(action: str, data: dict[str, Any]) -> dict[str, Any]:
    """Score the risk of an action locally, without logging it.

    Args:
        action: The action type to check.
        data: The action data payload.

    Returns:
        Dictionary with risk_level, pii_detected, pii_fields, and a note.
    """
    pii_detected, pii_fields = _has_pii(data)
    command = str(data.get("command", "")).lower()

    levels: list[str] = []

    # Critical
    if _has_creds(data):
        levels.append("critical")
    if action == "shell_command" and any(k in command for k in ["rm -rf", "drop ", "delete from"]):
        levels.append("critical")

    # High
    if action == "shell_command" and any(k in command for k in ["prod", "production"]):
        levels.append("high")

    # Medium
    if pii_detected:
        levels.append("medium")
    if action == "shell_command" and any(k in command for k in ["sudo ", "chmod "]):
        levels.append("medium")

    risk_level = max(levels, key=lambda level: _RISK_ORDER[level]) if levels else "low"

    return {
        "risk_level": risk_level,
        "pii_detected": pii_detected,
        "pii_fields": pii_fields,
        "note": "This is a dry-run check. No event was logged.",
    }
