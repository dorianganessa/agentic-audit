"""Event API endpoints: ingest, query, and statistics."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from agentaudit_api.auth.api_key import get_current_api_key
from agentaudit_api.config import get_settings
from agentaudit_api.database import get_session
from agentaudit_api.models.api_key import ApiKey
from agentaudit_api.models.event import AuditEventCreate, AuditEventRead
from agentaudit_api.services.alerter import evaluate_and_send
from agentaudit_api.services.event_service import create_event, get_event, get_stats, list_events

router = APIRouter()


def _get_alert_rules(session: Session, api_key: ApiKey) -> list[dict[str, Any]]:
    """Get alert_rules from the org policy."""
    if not api_key.org_id:
        return []
    from agentaudit_api.models.organization import Organization

    org = session.query(Organization).filter(Organization.id == api_key.org_id).first()  # type: ignore[arg-type]
    if org is None:
        return []
    return org.policy.get("alert_rules", [])  # type: ignore[no-any-return]


@router.post(
    "/events",
    response_model=AuditEventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Log an audit event",
    description=(
        "Record an agent action. The event will be classified for risk, "
        "checked for PII, and mapped to compliance frameworks."
    ),
    responses={
        401: {"description": "Invalid or missing API key"},
        422: {"description": "Validation error in request body"},
    },
)
def ingest_event(
    event_data: AuditEventCreate,
    background_tasks: BackgroundTasks,
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> AuditEventRead:
    """Ingest a new audit event."""
    settings = get_settings()
    data_size = len(json.dumps(event_data.data, default=str).encode())
    ctx_size = len(json.dumps(event_data.context, default=str).encode())
    if data_size > settings.max_event_data_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"data field too large ({data_size} bytes, max {settings.max_event_data_bytes})",
        )
    if ctx_size > settings.max_event_context_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"context field too large"
                f" ({ctx_size} bytes, max {settings.max_event_context_bytes})"
            ),
        )

    result = create_event(session, event_data, api_key_id=api_key.id, org_id=api_key.org_id)

    alert_rules = _get_alert_rules(session, api_key)
    if alert_rules:
        event_dict = result.model_dump(mode="json")
        background_tasks.add_task(evaluate_and_send, alert_rules, event_dict)

    return result


@router.get(
    "/events/stats",
    summary="Get event statistics",
    description="Aggregate statistics for events including risk levels, actions, and PII counts.",
    responses={401: {"description": "Invalid or missing API key"}},
)
def events_stats(
    after: datetime | None = Query(None, description="Filter events after this datetime"),
    before: datetime | None = Query(None, description="Filter events before this datetime"),
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get aggregate statistics for events."""
    return get_stats(session, api_key.id, after=after, before=before)


@router.get(
    "/events/{event_id}",
    response_model=AuditEventRead,
    summary="Get event by ID",
    responses={
        401: {"description": "Invalid or missing API key"},
        404: {"description": "Event not found"},
    },
)
def get_event_by_id(
    event_id: str,
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> AuditEventRead:
    """Get a single event by ID."""
    event = get_event(session, event_id, api_key.id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return AuditEventRead.model_validate(event)


@router.get(
    "/events",
    summary="List events",
    description="List events with filtering and pagination.",
    responses={401: {"description": "Invalid or missing API key"}},
)
def list_events_endpoint(
    agent_id: str | None = Query(None, description="Filter by agent ID"),
    action: str | None = Query(None, description="Filter by action type"),
    risk_level: str | None = Query(None, description="Filter by risk level"),
    pii_detected: bool | None = Query(None, description="Filter by PII detection"),
    session_id: str | None = Query(None, description="Filter by session ID"),
    after: datetime | None = Query(None, description="Filter events after this datetime"),
    before: datetime | None = Query(None, description="Filter events before this datetime"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List events with filtering and pagination."""
    events, total = list_events(
        session,
        api_key.id,
        agent_id=agent_id,
        action=action,
        risk_level=risk_level,
        pii_detected=pii_detected,
        session_id=session_id,
        after=after,
        before=before,
        limit=limit,
        offset=offset,
    )
    return {
        "events": [AuditEventRead.model_validate(e) for e in events],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
