"""Auto-suggest AI Act risk classification from observed event patterns."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from agentaudit_api.models.ai_system import AISystem
from agentaudit_api.models.event import AuditEvent
from agentaudit_api.services.system_service import _build_agent_id_filter

logger = logging.getLogger(__name__)

# Keywords in event data that hint at Annex III categories
_CATEGORY_SIGNALS: dict[str, list[str]] = {
    "employment": [
        "hr", "recruit", "hiring", "candidate", "resume", "cv",
        "employee", "salary", "payroll", "performance review",
        "termination", "promotion",
    ],
    "education": [
        "student", "grade", "transcript", "enrollment", "school",
        "university", "exam", "course",
    ],
    "essential_services": [
        "credit", "loan", "insurance", "mortgage", "benefit",
        "social security", "welfare",
    ],
    "law_enforcement": [
        "arrest", "criminal", "suspect", "warrant", "forensic",
        "surveillance", "detention",
    ],
    "biometric": [
        "face", "fingerprint", "iris", "voice recognition",
        "biometric", "facial",
    ],
    "critical_infrastructure": [
        "scada", "power grid", "water treatment", "nuclear",
        "traffic control",
    ],
    "migration": [
        "visa", "asylum", "border", "immigration", "passport",
    ],
}


def suggest_classification(
    session: Session,
    system: AISystem,
    api_key_id: str,
    *,
    event_limit: int = 500,
) -> dict[str, Any]:
    """Analyze recent events and suggest a risk classification.

    Returns a dict with suggested_classification, suggested_category,
    rationale, and evidence.
    """
    if not system.agent_id_patterns:
        return {
            "suggested_classification": "minimal",
            "suggested_category": None,
            "rationale": "No agent_id_patterns configured — no events to analyze.",
            "evidence": {},
        }

    agent_clauses = _build_agent_id_filter(system.agent_id_patterns)
    base_filter = [
        AuditEvent.api_key_id == api_key_id,  # type: ignore[arg-type]
        or_(*agent_clauses),
    ]

    total = session.query(AuditEvent).filter(*base_filter).count()
    if total == 0:
        return {
            "suggested_classification": "unclassified",
            "suggested_category": None,
            "rationale": "No events found for this system yet.",
            "evidence": {"total_events": 0},
        }

    # Risk distribution
    risk_rows = (
        session.query(AuditEvent.risk_level, func.count())  # type: ignore[call-overload]
        .filter(*base_filter)
        .group_by(AuditEvent.risk_level)
        .all()
    )
    by_risk = {level: count for level, count in risk_rows}

    # PII stats
    pii_count = (
        session.query(AuditEvent)
        .filter(*base_filter, AuditEvent.pii_detected.is_(True))  # type: ignore[attr-defined]
        .count()
    )

    # Action distribution
    action_rows = (
        session.query(AuditEvent.action, func.count())  # type: ignore[call-overload]
        .filter(*base_filter)
        .group_by(AuditEvent.action)
        .all()
    )
    by_action = {act: count for act, count in action_rows}

    # Sample data for keyword analysis
    recent = (
        session.query(AuditEvent)
        .filter(*base_filter)
        .order_by(AuditEvent.created_at.desc())  # type: ignore[attr-defined]
        .limit(event_limit)
        .all()
    )
    corpus = _build_corpus(recent)

    # Determine category
    category_scores = _score_categories(corpus)
    suggested_category = (
        max(category_scores, key=category_scores.get)  # type: ignore[arg-type]
        if category_scores
        else None
    )

    # Determine classification
    high_critical = by_risk.get("high", 0) + by_risk.get("critical", 0)
    pii_ratio = pii_count / total if total > 0 else 0

    reasons: list[str] = []
    suggested = "minimal"

    if high_critical > 0 and high_critical / total >= 0.1:
        suggested = "high"
        reasons.append(
            f"{high_critical}/{total} events are high/critical risk"
            f" ({high_critical / total:.0%})"
        )

    if pii_ratio >= 0.2:
        if suggested != "high":
            suggested = "limited"
        reasons.append(
            f"{pii_count}/{total} events contain PII ({pii_ratio:.0%})"
        )

    if suggested_category in ("employment", "biometric", "law_enforcement"):
        suggested = "high"
        reasons.append(
            f"Data patterns suggest Annex III category: {suggested_category}"
        )

    if "connector_access" in by_action:
        if suggested == "minimal":
            suggested = "limited"
        reasons.append(
            f"System accesses external connectors"
            f" ({by_action['connector_access']} events)"
        )

    if not reasons:
        reasons.append("No high-risk patterns detected in event data")

    return {
        "suggested_classification": suggested,
        "suggested_category": suggested_category,
        "rationale": "; ".join(reasons),
        "evidence": {
            "total_events": total,
            "by_risk_level": by_risk,
            "by_action": by_action,
            "pii_events": pii_count,
            "pii_ratio": round(pii_ratio, 3),
            "category_scores": category_scores,
        },
    }


def _build_corpus(events: list[AuditEvent]) -> str:
    """Flatten event data into a searchable text corpus."""
    parts: list[str] = []
    for ev in events:
        if ev.data:
            parts.append(_flatten(ev.data))
        if ev.context:
            parts.append(_flatten(ev.context))
    return " ".join(parts).lower()


def _flatten(obj: object) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return " ".join(_flatten(v) for v in obj.values())
    if isinstance(obj, list):
        return " ".join(_flatten(v) for v in obj)
    return str(obj) if obj is not None else ""


def _score_categories(corpus: str) -> dict[str, int]:
    """Count keyword matches per Annex III category."""
    scores: dict[str, int] = {}
    for category, keywords in _CATEGORY_SIGNALS.items():
        hits = sum(1 for kw in keywords if kw in corpus)
        if hits > 0:
            scores[category] = hits
    return scores
