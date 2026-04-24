"""Core event processing: creation, querying, and policy enforcement."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from agentaudit_api.models.blocking_log import BlockingLog
from agentaudit_api.models.event import (
    AuditEvent,
    AuditEventCreate,
    AuditEventRead,
)
from agentaudit_api.models.organization import DEFAULT_POLICY, Organization
from agentaudit_api.services.framework_mapper import map_frameworks
from agentaudit_api.services.pii_detector import detect_pii
from agentaudit_api.services.risk_scorer import RISK_LEVELS, score_risk

logger = logging.getLogger(__name__)


def _get_policy(session: Session, org_id: str | None) -> dict[str, Any]:
    """Get the policy for an org, falling back to the default."""
    if org_id:
        org = (
            session.query(Organization)
            .filter(Organization.id == org_id)  # type: ignore[arg-type]
            .first()
        )
        if org:
            return dict(org.policy)
    return {**DEFAULT_POLICY}


def _should_store(logging_level: str, risk_level: str, pii_detected: bool) -> bool:
    """Decide whether to persist the event based on logging level.

    Args:
        logging_level: One of minimal, standard, full, paranoid.
        risk_level: Computed risk level of the event.
        pii_detected: Whether PII was found in the event.
    """
    if logging_level == "minimal":
        return pii_detected
    if logging_level == "standard":
        return risk_level != "low" or pii_detected
    # full and paranoid: store everything
    return True


def _should_block(policy: dict[str, Any], risk_level: str) -> tuple[bool, str | None]:
    """Decide whether to block the action (paranoid mode only).

    Returns:
        A tuple of (blocked, reason). If not blocked, reason is None.
    """
    logging_level = policy.get("logging_level", "standard")
    blocking_rules = policy.get("blocking_rules", {})

    if logging_level != "paranoid" or not blocking_rules.get("enabled", False):
        return False, None

    block_on: str = blocking_rules.get("block_on", "critical")
    risk_order = {level: i for i, level in enumerate(RISK_LEVELS)}
    event_risk = risk_order.get(risk_level, 0)
    threshold_risk = risk_order.get(block_on, 3)

    if event_risk >= threshold_risk:
        return True, f"Action blocked: risk level '{risk_level}' >= threshold '{block_on}'"
    return False, None


def create_event(
    session: Session,
    event_data: AuditEventCreate,
    api_key_id: str,
    org_id: str | None = None,
) -> AuditEventRead:
    """Create a new audit event with PII detection, risk scoring, and policy enforcement.

    Args:
        session: Database session.
        event_data: The event payload from the client.
        api_key_id: ID of the API key used for authentication.
        org_id: Optional organization ID for policy lookup.

    Returns:
        The processed event with risk level, PII, frameworks, and decision populated.
    """
    policy = _get_policy(session, org_id)
    logging_level: str = policy.get("logging_level", "standard")
    enabled_frameworks: dict[str, bool] = policy.get(
        "frameworks", {"gdpr": True, "ai_act": True, "soc2": False}
    )

    # PII detection
    pii_result = detect_pii(event_data.data, event_data.context)

    # Risk scoring
    risk_level = score_risk(
        action=event_data.action,
        data=event_data.data,
        context=event_data.context,
        pii_detected=pii_result.detected,
    )

    # Framework mapping
    frameworks = map_frameworks(
        action=event_data.action,
        risk_level=risk_level,
        pii_detected=pii_result.detected,
        reasoning=event_data.reasoning,
        context=event_data.context,
        agent_id=event_data.agent_id,
        enabled_frameworks=enabled_frameworks,
    )

    # Blocking decision
    blocked, reason = _should_block(policy, risk_level)
    decision = "block" if blocked else "allow"

    # Record blocking evidence for compliance (Art. 14 Human Oversight)
    if blocked:
        try:
            log_entry = BlockingLog(
                org_id=org_id or "",
                agent_id=event_data.agent_id,
                action=event_data.action,
                risk_level=risk_level,
                block_reason=reason or "Unknown",
            )
            session.add(log_entry)
            session.commit()
        except Exception:
            session.rollback()
            logger.error(
                "Failed to write blocking log for action=%s agent=%s",
                event_data.action,
                event_data.agent_id,
                exc_info=True,
            )

    # Storage decision — blocked events are NOT stored
    stored = False if blocked else _should_store(logging_level, risk_level, pii_result.detected)

    if stored:
        event = AuditEvent(
            agent_id=event_data.agent_id,
            action=event_data.action,
            data=event_data.data,
            context=event_data.context,
            reasoning=event_data.reasoning,
            api_key_id=api_key_id,
            pii_detected=pii_result.detected,
            pii_fields=pii_result.fields,
            risk_level=risk_level,
            frameworks=frameworks,
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        result = AuditEventRead.model_validate(event)
    else:
        from agentaudit_api.models.event import _generate_ulid

        result = AuditEventRead(
            id=_generate_ulid(),
            agent_id=event_data.agent_id,
            action=event_data.action,
            data=event_data.data,
            context=event_data.context,
            reasoning=event_data.reasoning,
            pii_detected=pii_result.detected,
            pii_fields=pii_result.fields,
            risk_level=risk_level,
            frameworks=frameworks,
            created_at=datetime.now(UTC),
        )

    result.stored = stored
    result.decision = decision
    result.reason = reason

    logger.info(
        "Event %s: action=%s risk=%s pii=%s decision=%s stored=%s",
        result.id,
        result.action,
        risk_level,
        pii_result.detected,
        decision,
        stored,
    )

    return result


def _scope_filter(
    session: Session, api_key_id: str | None, org_id: str | None
) -> Any:
    """Tenancy filter for event queries.

    Exactly one of api_key_id or org_id must be provided:
      - api_key_id: SDK / programmatic access — only events posted by this key.
      - org_id: operator / dashboard access — every event across all API keys
        that belong to the org.
    """
    if (api_key_id is None) == (org_id is None):
        raise ValueError("Exactly one of api_key_id or org_id must be provided")
    if api_key_id is not None:
        return AuditEvent.api_key_id == api_key_id

    from agentaudit_api.models.api_key import ApiKey

    keys_for_org = (
        session.query(ApiKey.id)  # type: ignore[call-overload]
        .filter(ApiKey.org_id == org_id)
        .subquery()
    )
    return AuditEvent.api_key_id.in_(keys_for_org.select())  # type: ignore[attr-defined]


def get_event(
    session: Session,
    event_id: str,
    api_key_id: str | None = None,
    *,
    org_id: str | None = None,
) -> AuditEvent | None:
    """Get a single event by ID, scoped to an API key or org.

    Args:
        session: Database session.
        event_id: The event ULID.
        api_key_id: The API key ID for programmatic (SDK) access control.
        org_id: Alternative org-wide scoping for dashboard/operator access.
            Exactly one of api_key_id or org_id must be provided.
    """
    return (
        session.query(AuditEvent)
        .filter(
            AuditEvent.id == event_id,  # type: ignore[arg-type]
            _scope_filter(session, api_key_id, org_id),
        )
        .first()
    )


def list_events(
    session: Session,
    api_key_id: str | None = None,
    *,
    org_id: str | None = None,
    agent_id: str | None = None,
    action: str | None = None,
    risk_level: str | None = None,
    pii_detected: bool | None = None,
    session_id: str | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditEvent], int]:
    """List events with filtering and pagination.

    Pass api_key_id for SDK-style per-key access, or org_id for operator /
    dashboard-style access that spans every key in the org.

    Returns:
        A tuple of (events, total_count).
    """
    query = session.query(AuditEvent).filter(_scope_filter(session, api_key_id, org_id))

    if agent_id is not None:
        query = query.filter(AuditEvent.agent_id == agent_id)  # type: ignore[arg-type]
    if action is not None:
        query = query.filter(AuditEvent.action == action)  # type: ignore[arg-type]
    if risk_level is not None:
        query = query.filter(AuditEvent.risk_level == risk_level)  # type: ignore[arg-type]
    if pii_detected is not None:
        query = query.filter(AuditEvent.pii_detected == pii_detected)  # type: ignore[arg-type]
    if session_id is not None:
        query = query.filter(text("context->>'session_id' = :sid").bindparams(sid=session_id))
    if after is not None:
        query = query.filter(AuditEvent.created_at > after)  # type: ignore[arg-type]
    if before is not None:
        query = query.filter(AuditEvent.created_at < before)  # type: ignore[arg-type]

    total: int = query.count()
    events: list[AuditEvent] = (
        query.order_by(AuditEvent.created_at.desc())  # type: ignore[attr-defined]
        .offset(offset)
        .limit(limit)
        .all()
    )
    return events, total


def get_stats(
    session: Session,
    api_key_id: str | None = None,
    *,
    org_id: str | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
) -> dict[str, Any]:
    """Compute aggregate statistics for events.

    Pass api_key_id for SDK-style per-key access, or org_id for operator /
    dashboard-style access that spans every key in the org.

    Returns:
        Dictionary with total_events, by_risk_level, by_action, pii_events,
        unique_agents, and unique_sessions counts.
    """
    scope = _scope_filter(session, api_key_id, org_id)

    def _with_time(q: Any) -> Any:
        if after is not None:
            q = q.filter(AuditEvent.created_at > after)
        if before is not None:
            q = q.filter(AuditEvent.created_at < before)
        return q

    base = _with_time(session.query(AuditEvent).filter(scope))
    total_events: int = base.count()

    risk_rows = _with_time(
        session.query(AuditEvent.risk_level, func.count()).filter(scope)  # type: ignore[call-overload]
    ).group_by(AuditEvent.risk_level).all()
    by_risk_level: dict[str, int] = {level: 0 for level in ("low", "medium", "high", "critical")}
    for level, count in risk_rows:
        if level in by_risk_level:
            by_risk_level[level] = count

    action_rows = _with_time(
        session.query(AuditEvent.action, func.count()).filter(scope)  # type: ignore[call-overload]
    ).group_by(AuditEvent.action).all()
    by_action: dict[str, int] = {act: count for act, count in action_rows}

    pii_events: int = base.filter(AuditEvent.pii_detected.is_(True)).count()  # type: ignore[attr-defined]

    unique_agents: int = _with_time(
        session.query(func.count(func.distinct(AuditEvent.agent_id))).filter(scope)
    ).scalar() or 0

    unique_sessions: int = _with_time(
        session.query(
            func.count(func.distinct(text("context->>'session_id'")))
        ).filter(scope)
    ).scalar() or 0

    return {
        "total_events": total_events,
        "by_risk_level": by_risk_level,
        "by_action": by_action,
        "pii_events": pii_events,
        "unique_agents": unique_agents,
        "unique_sessions": unique_sessions,
    }
