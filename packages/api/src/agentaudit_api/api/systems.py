"""AI Systems registry API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from agentaudit_api.auth.api_key import get_current_api_key
from agentaudit_api.database import get_session
from agentaudit_api.models.ai_system import (
    ANNEX_III_CATEGORIES,
    FRIA_STATUSES,
    RISK_CLASSIFICATIONS,
    ROLES,
    AISystemCreate,
    AISystemRead,
    AISystemUpdate,
)
from agentaudit_api.models.api_key import ApiKey
from agentaudit_api.models.event import AuditEventRead
from agentaudit_api.services.classification_service import suggest_classification
from agentaudit_api.services.system_service import (
    create_system,
    delete_system,
    get_events_for_system,
    get_system,
    get_system_event_stats,
    list_systems,
    update_system,
)

router = APIRouter(tags=["systems"])


def _get_org_id(api_key: ApiKey) -> str:
    if not api_key.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No organization associated with this API key",
        )
    return api_key.org_id


def _check_enum(field: str, value: object, allowed: tuple[str, ...]) -> None:
    """Raise 422 if value is not in allowed set."""
    if value is not None and value not in allowed:
        raise HTTPException(422, f"Invalid {field}. Must be one of: {allowed}")


def _validate_create(data: AISystemCreate) -> None:
    _check_enum("risk_classification", data.risk_classification, RISK_CLASSIFICATIONS)
    _check_enum("annex_iii_category", data.annex_iii_category, ANNEX_III_CATEGORIES)
    _check_enum("role", data.role, ROLES)
    _check_enum("fria_status", data.fria_status, FRIA_STATUSES)


@router.post(
    "/systems",
    response_model=AISystemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register an AI system",
)
def create(
    data: AISystemCreate,
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> AISystemRead:
    """Register a new AI system for compliance tracking."""
    org_id = _get_org_id(api_key)
    _validate_create(data)
    return create_system(session, data, org_id)


@router.get(
    "/systems",
    summary="List AI systems",
)
def list_all(
    include_inactive: bool = Query(False),
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List all registered AI systems for the organization."""
    org_id = _get_org_id(api_key)
    systems = list_systems(session, org_id, include_inactive=include_inactive)
    return {
        "systems": [AISystemRead.model_validate(s) for s in systems],
        "total": len(systems),
    }


@router.get(
    "/systems/{system_id}",
    response_model=AISystemRead,
    summary="Get AI system",
)
def get_one(
    system_id: str,
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> AISystemRead:
    """Get a single AI system by ID."""
    org_id = _get_org_id(api_key)
    system = get_system(session, system_id, org_id)
    if system is None:
        raise HTTPException(status_code=404, detail="System not found")
    return AISystemRead.model_validate(system)


@router.put(
    "/systems/{system_id}",
    response_model=AISystemRead,
    summary="Update AI system",
)
def update(
    system_id: str,
    data: AISystemUpdate,
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> AISystemRead:
    """Partially update an AI system."""
    org_id = _get_org_id(api_key)
    system = get_system(session, system_id, org_id)
    if system is None:
        raise HTTPException(status_code=404, detail="System not found")

    # Validate enum fields if provided
    update_data = data.model_dump(exclude_unset=True)
    _check_enum("risk_classification", update_data.get("risk_classification"), RISK_CLASSIFICATIONS)
    _check_enum("annex_iii_category", update_data.get("annex_iii_category"), ANNEX_III_CATEGORIES)
    _check_enum("role", update_data.get("role"), ROLES)
    _check_enum("fria_status", update_data.get("fria_status"), FRIA_STATUSES)

    return update_system(session, system, data)


@router.delete(
    "/systems/{system_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate AI system",
)
def deactivate(
    system_id: str,
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> None:
    """Soft-delete (deactivate) an AI system."""
    org_id = _get_org_id(api_key)
    system = get_system(session, system_id, org_id)
    if system is None:
        raise HTTPException(status_code=404, detail="System not found")
    delete_system(session, system)


@router.get(
    "/systems/{system_id}/events",
    summary="List events for an AI system",
)
def system_events(
    system_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List audit events matching this system's agent_id_patterns."""
    org_id = _get_org_id(api_key)
    system = get_system(session, system_id, org_id)
    if system is None:
        raise HTTPException(status_code=404, detail="System not found")

    events, total = get_events_for_system(session, system, api_key.id, limit=limit, offset=offset)
    return {
        "events": [AuditEventRead.model_validate(e) for e in events],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/systems/{system_id}/stats",
    summary="Get event statistics for an AI system",
)
def system_stats(
    system_id: str,
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get aggregate event statistics for a system based on its agent_id_patterns."""
    org_id = _get_org_id(api_key)
    system = get_system(session, system_id, org_id)
    if system is None:
        raise HTTPException(status_code=404, detail="System not found")
    return get_system_event_stats(session, system, api_key.id)


@router.get(
    "/systems/{system_id}/classification-suggestion",
    summary="Suggest AI Act risk classification",
)
def classification_suggestion(
    system_id: str,
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Analyze events and suggest risk classification + Annex III category."""
    org_id = _get_org_id(api_key)
    system = get_system(session, system_id, org_id)
    if system is None:
        raise HTTPException(status_code=404, detail="System not found")
    return suggest_classification(session, system, api_key.id)
