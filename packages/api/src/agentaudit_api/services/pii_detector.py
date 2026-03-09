"""Regex-based PII detection for audit event payloads."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- Patterns ---

_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_PHONE = re.compile(
    r"(?:\+\d{1,3}[\s.-]?)?"  # optional country code
    r"(?:\(?\d{2,4}\)?[\s.-]?)?"  # optional area code
    r"\d{3,4}[\s.-]?\d{3,4}\b"  # main number
)
_CREDIT_CARD = re.compile(
    r"\b(?:\d{4}[\s-]?){3}\d{4}\b"  # 16 digits grouped by 4
)
_API_KEY = re.compile(
    r"(?:"
    r"sk_live_[a-zA-Z0-9]{10,}"
    r"|sk_test_[a-zA-Z0-9]{10,}"
    r"|Bearer\s+[a-zA-Z0-9._\-]{20,}"
    r"|ghp_[a-zA-Z0-9]{30,}"
    r"|gho_[a-zA-Z0-9]{30,}"
    r"|aws_access_key[_\s]*[:=]\s*[A-Z0-9]{16,}"
    r"|AKIA[A-Z0-9]{12,}"
    r"|xox[bpras]-[a-zA-Z0-9\-]{10,}"
    r")"
)
_DB_CONN_STRING = re.compile(
    r"(?:postgresql|mysql|mongodb|redis|amqp)://[^\s\"'`]+"
)

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("email", _EMAIL),
    ("ip_address", _IPV4),
    ("phone", _PHONE),
    ("credit_card", _CREDIT_CARD),
    ("api_key", _API_KEY),
    ("db_connection_string", _DB_CONN_STRING),
]


@dataclass
class PiiResult:
    detected: bool = False
    fields: list[str] = field(default_factory=list)


def detect_pii(data: dict, context: dict) -> PiiResult:
    """Scan data and context dicts for PII patterns.

    Returns which PII types were found.
    """
    found: set[str] = set()
    _scan_value(data, found)
    _scan_value(context, found)

    return PiiResult(detected=bool(found), fields=sorted(found))


def _scan_value(value: object, found: set[str]) -> None:
    """Recursively scan a value for PII patterns."""
    if isinstance(value, str):
        for pii_type, pattern in _PATTERNS:
            if pii_type not in found and pattern.search(value):
                found.add(pii_type)
    elif isinstance(value, dict):
        for v in value.values():
            _scan_value(v, found)
    elif isinstance(value, list):
        for item in value:
            _scan_value(item, found)
