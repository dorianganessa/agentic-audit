"""Rules-based risk scoring for audit events.

Uses the YAML rules engine for evaluation. The ``score_risk`` function
maintains the same public API but delegates to the engine internally.
"""

from __future__ import annotations

import logging
from typing import Any

from agentaudit_api.services.rules.engine import EvaluationResult, RuleEngine
from agentaudit_api.services.rules.loader import create_engine

logger = logging.getLogger(__name__)

RISK_LEVELS: tuple[str, ...] = ("low", "medium", "high", "critical")

# Module-level engine singleton, loaded lazily
_engine: RuleEngine | None = None


def get_engine() -> RuleEngine:
    """Get (or create) the shared rules engine singleton."""
    global _engine  # noqa: PLW0603
    if _engine is None:
        _engine = create_engine()
    return _engine


def reset_engine() -> None:
    """Reset the engine singleton (useful for testing)."""
    global _engine  # noqa: PLW0603
    _engine = None


def score_risk(
    action: str,
    data: dict[str, Any],
    context: dict[str, Any],
    pii_detected: bool,
) -> str:
    """Compute the risk level for an audit event.

    Evaluates the action and data against YAML rules and returns
    the highest matching risk level.

    Args:
        action: The action type (e.g., shell_command, file_read).
        data: Action-specific payload.
        context: Environment metadata.
        pii_detected: Whether PII was found in the event.

    Returns:
        One of: low, medium, high, critical.
    """
    result = evaluate_event(action, data, context, pii_detected)
    return result.risk_level


def evaluate_event(
    action: str,
    data: dict[str, Any],
    context: dict[str, Any],
    pii_detected: bool,
    engine: RuleEngine | None = None,
) -> EvaluationResult:
    """Full evaluation returning matched rules, tags, and effects.

    Args:
        action: The action type.
        data: Action-specific payload.
        context: Environment metadata.
        pii_detected: Whether PII was found.
        engine: Optional engine override (uses singleton if None).

    Returns:
        EvaluationResult with risk_level, matched_rules, tags, etc.
    """
    eng = engine or get_engine()

    event = {
        "action": action,
        "data": data,
        "context": context,
        "pii_detected": pii_detected,
    }

    return eng.evaluate(event)
