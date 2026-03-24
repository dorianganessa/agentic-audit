"""Shared dependencies for API and dashboard routes."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from agentaudit_api.models.api_key import ApiKey
from agentaudit_api.models.organization import Organization


def get_org(session: Session, api_key: ApiKey) -> Organization:
    """Get the organization for the current API key, or raise 404."""
    if not api_key.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No organization associated with this API key",
        )
    org = (
        session.query(Organization)
        .filter(Organization.id == api_key.org_id)  # type: ignore[arg-type]
        .first()
    )
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return org
