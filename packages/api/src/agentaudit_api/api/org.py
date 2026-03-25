"""Organization policy API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from agentaudit_api.api.deps import get_org
from agentaudit_api.auth.api_key import get_current_api_key
from agentaudit_api.database import get_session
from agentaudit_api.models.api_key import (
    ApiKey,
    generate_api_key,
    hash_api_key,
    key_prefix_from_key,
)
from agentaudit_api.models.organization import Organization, PolicyUpdate

router = APIRouter()


@router.get(
    "/org/policy",
    summary="Get organization policy",
    description="Returns the current compliance policy for the organization.",
    responses={
        401: {"description": "Invalid or missing API key"},
        404: {"description": "Organization not found"},
    },
)
def get_policy(
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get the current policy for the organization."""
    org = get_org(session, api_key)
    return dict(org.policy)


@router.put(
    "/org/policy",
    summary="Update organization policy",
    description="Partially update the organization's compliance policy.",
    responses={
        401: {"description": "Invalid or missing API key"},
        404: {"description": "Organization not found"},
    },
)
def update_policy(
    policy_update: PolicyUpdate,
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Update the organization policy."""
    org = get_org(session, api_key)
    old_version = org.version

    current_policy = dict(org.policy)

    if policy_update.logging_level is not None:
        current_policy["logging_level"] = policy_update.logging_level
    if policy_update.frameworks is not None:
        current_policy["frameworks"] = policy_update.frameworks
    if policy_update.alert_rules is not None:
        current_policy["alert_rules"] = policy_update.alert_rules
    if policy_update.blocking_rules is not None:
        current_policy["blocking_rules"] = policy_update.blocking_rules
    if policy_update.compliance_preset is not None:
        current_policy["compliance_preset"] = policy_update.compliance_preset
    if policy_update.retention_days is not None:
        current_policy["retention_days"] = policy_update.retention_days

    # AI Act preset enforces minimum 180-day retention (Art 12)
    if current_policy.get("compliance_preset") == "ai_act":
        ret = current_policy.get("retention_days", 0)
        if ret < 180:
            current_policy["retention_days"] = 180

    stmt = (
        update(Organization)
        .where(Organization.id == org.id, Organization.version == old_version)  # type: ignore[arg-type]
        .values(
            policy=current_policy,
            version=old_version + 1,
            updated_at=datetime.now(UTC),
        )
    )
    result = session.execute(stmt)
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise HTTPException(status_code=409, detail="Policy was modified concurrently. Retry.")
    session.commit()

    session.refresh(org)
    return dict(org.policy)


@router.post(
    "/org/api-keys/rotate",
    summary="Rotate API key",
    description=(
        "Generate a new API key and deactivate the current one. "
        "The new raw key is returned once and cannot be retrieved again."
    ),
    responses={
        401: {"description": "Invalid or missing API key"},
    },
)
def rotate_api_key(
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Rotate the current API key: create a new one and deactivate the old."""
    new_raw = generate_api_key()
    new_key = ApiKey(
        key_hash=hash_api_key(new_raw),
        key_prefix=key_prefix_from_key(new_raw),
        name=api_key.name,
        org_id=api_key.org_id,
        is_active=True,
    )
    session.add(new_key)

    # Deactivate old key
    api_key.is_active = False
    session.add(api_key)

    session.commit()
    session.refresh(new_key)

    return {
        "api_key": new_raw,
        "key_prefix": new_key.key_prefix,
        "id": new_key.id,
        "previous_key_id": api_key.id,
    }
