"""Rules-based risk scoring for audit events."""

from __future__ import annotations

import re

RISK_LEVELS = ("low", "medium", "high", "critical")
_RISK_ORDER = {level: i for i, level in enumerate(RISK_LEVELS)}


def score_risk(
    action: str,
    data: dict,
    context: dict,
    pii_detected: bool,
) -> str:
    """Compute the risk level for an audit event. Returns the highest matching level."""
    levels: list[str] = []

    command = str(data.get("command", ""))
    file_path = str(data.get("file_path", ""))
    environment = str(context.get("environment", ""))

    # --- Critical rules ---
    if _has_credential_indicators(action, data):
        levels.append("critical")

    if action == "shell_command" and _matches_any(
        command, ["rm -rf", "rm  -rf", "DROP ", "DELETE FROM"]
    ):
        levels.append("critical")

    # --- High rules ---
    if action == "shell_command" and _matches_any(command, ["prod", "production"]):
        levels.append("high")

    if pii_detected and environment == "production":
        levels.append("high")

    if action == "file_write" and _path_matches_sensitive_write(file_path):
        levels.append("high")

    if action == "file_read" and _path_matches_sensitive_read(file_path):
        levels.append("high")

    # --- Medium rules ---
    if pii_detected:
        levels.append("medium")

    if action == "shell_command" and _matches_any(command, ["sudo ", "chmod "]):
        levels.append("medium")

    # --- Low rules ---
    if action == "shell_command" and _matches_any(
        command, ["npm install", "pip install", "uv add"]
    ):
        levels.append("low")

    if not levels:
        return "low"

    return max(levels, key=lambda level: _RISK_ORDER[level])


def _has_credential_indicators(action: str, data: dict) -> bool:
    """Check if the action or data suggests credential access."""
    if "credential" in action.lower() or "password" in action.lower():
        return True

    data_str = _flatten_to_str(data)
    credential_patterns = [
        r"sk_live_[a-zA-Z0-9]+",
        r"sk_test_[a-zA-Z0-9]+",
        r"ghp_[a-zA-Z0-9]+",
        r"AKIA[A-Z0-9]+",
        r"password\s*[:=]\s*\S+",
    ]
    return any(re.search(pat, data_str) for pat in credential_patterns)


def _matches_any(text: str, keywords: list[str]) -> bool:
    """Case-insensitive check if text contains any of the keywords."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def _path_matches_sensitive_write(file_path: str) -> bool:
    path_lower = file_path.lower()
    return any(
        pat in path_lower for pat in [".env", "auth", "secret", "credential", "token"]
    )


def _path_matches_sensitive_read(file_path: str) -> bool:
    path_lower = file_path.lower()
    return any(pat in path_lower for pat in [".env", ".pem", ".key", "id_rsa", "credential"])


def _flatten_to_str(data: object) -> str:
    """Recursively flatten a dict/list to a single string for pattern matching."""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        return " ".join(_flatten_to_str(v) for v in data.values())
    if isinstance(data, list):
        return " ".join(_flatten_to_str(v) for v in data)
    return str(data) if data is not None else ""
