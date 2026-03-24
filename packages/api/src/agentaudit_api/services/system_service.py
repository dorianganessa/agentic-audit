"""AI Systems registry service: CRUD and event linking."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from agentaudit_api.models.ai_system import (
    AISystem,
    AISystemCreate,
    AISystemRead,
    AISystemUpdate,
)
from agentaudit_api.models.event import AuditEvent

logger = logging.getLogger(__name__)


def create_system(
    session: Session,
    data: AISystemCreate,
    org_id: str,
) -> AISystemRead:
    """Create a new AI system in the registry."""
    system = AISystem(
        org_id=org_id,
        **data.model_dump(),
    )
    session.add(system)
    session.commit()
    session.refresh(system)
    return AISystemRead.model_validate(system)


def get_system(
    session: Session,
    system_id: str,
    org_id: str,
) -> AISystem | None:
    """Get a single system by ID, scoped to org."""
    return (
        session.query(AISystem)
        .filter(
            AISystem.id == system_id,  # type: ignore[arg-type]
            AISystem.org_id == org_id,  # type: ignore[arg-type]
        )
        .first()
    )


def list_systems(
    session: Session,
    org_id: str,
    *,
    include_inactive: bool = False,
) -> list[AISystem]:
    """List all systems for an org."""
    query = session.query(AISystem).filter(AISystem.org_id == org_id)  # type: ignore[arg-type]
    if not include_inactive:
        query = query.filter(AISystem.is_active.is_(True))  # type: ignore[attr-defined]
    return query.order_by(AISystem.name).all()  # type: ignore[return-value]


def update_system(
    session: Session,
    system: AISystem,
    data: AISystemUpdate,
) -> AISystemRead:
    """Partially update an AI system."""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(system, key, value)
    system.updated_at = datetime.now(UTC)
    session.add(system)
    session.commit()
    session.refresh(system)
    return AISystemRead.model_validate(system)


def delete_system(session: Session, system: AISystem) -> None:
    """Soft-delete an AI system."""
    system.is_active = False
    system.updated_at = datetime.now(UTC)
    session.add(system)
    session.commit()


def _build_agent_id_filter(patterns: list[str]) -> list[Any]:
    """Convert agent_id_patterns (with * wildcards) to SQLAlchemy LIKE clauses."""
    clauses = []
    for pattern in patterns:
        # Escape SQL LIKE metacharacters before converting our wildcards
        escaped = pattern.replace("%", r"\%").replace("_", r"\_")
        sql_pattern = escaped.replace("*", "%")
        clauses.append(AuditEvent.agent_id.like(sql_pattern))  # type: ignore[union-attr]
    return clauses


def get_events_for_system(
    session: Session,
    system: AISystem,
    api_key_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditEvent], int]:
    """Get events matching a system's agent_id_patterns."""
    if not system.agent_id_patterns:
        return [], 0

    agent_clauses = _build_agent_id_filter(system.agent_id_patterns)
    base_query = session.query(AuditEvent).filter(
        AuditEvent.api_key_id == api_key_id,  # type: ignore[arg-type]
        or_(*agent_clauses),
    )

    total: int = base_query.count()
    events: list[AuditEvent] = (
        base_query.order_by(AuditEvent.created_at.desc())  # type: ignore[attr-defined]
        .offset(offset)
        .limit(limit)
        .all()
    )
    return events, total


def get_system_event_stats(
    session: Session,
    system: AISystem,
    api_key_id: str,
) -> dict[str, Any]:
    """Get aggregate event statistics for a system."""
    from sqlalchemy import func

    if not system.agent_id_patterns:
        return {
            "total_events": 0,
            "by_risk_level": {},
            "by_action": {},
            "pii_events": 0,
        }

    agent_clauses = _build_agent_id_filter(system.agent_id_patterns)
    base_filter = [
        AuditEvent.api_key_id == api_key_id,  # type: ignore[arg-type]
        or_(*agent_clauses),
    ]

    total = session.query(AuditEvent).filter(*base_filter).count()

    risk_rows = (
        session.query(AuditEvent.risk_level, func.count())  # type: ignore[call-overload]
        .filter(*base_filter)
        .group_by(AuditEvent.risk_level)
        .all()
    )
    by_risk: dict[str, int] = {level: 0 for level in ("low", "medium", "high", "critical")}
    for level, count in risk_rows:
        if level in by_risk:
            by_risk[level] = count

    action_rows = (
        session.query(AuditEvent.action, func.count())  # type: ignore[call-overload]
        .filter(*base_filter)
        .group_by(AuditEvent.action)
        .all()
    )
    by_action: dict[str, int] = {act: count for act, count in action_rows}

    pii_events = (
        session.query(AuditEvent)
        .filter(*base_filter, AuditEvent.pii_detected.is_(True))  # type: ignore[attr-defined]
        .count()
    )

    return {
        "total_events": total,
        "by_risk_level": by_risk,
        "by_action": by_action,
        "pii_events": pii_events,
    }
