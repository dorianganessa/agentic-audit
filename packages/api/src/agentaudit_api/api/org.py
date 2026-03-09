from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agentaudit_api.auth.api_key import get_current_api_key
from agentaudit_api.database import get_session
from agentaudit_api.models.api_key import ApiKey
from agentaudit_api.models.organization import Organization, PolicyUpdate

router = APIRouter()


def _get_org(session: Session, api_key: ApiKey) -> Organization:
    """Get the organization for the current API key, or raise 404."""
    if not api_key.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No organization associated with this API key",
        )
    org = session.query(Organization).filter(Organization.id == api_key.org_id).first()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return org


@router.get("/org/policy")
def get_policy(
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> dict:
    """Get the current policy for the organization."""
    org = _get_org(session, api_key)
    return org.policy


@router.put("/org/policy")
def update_policy(
    policy_update: PolicyUpdate,
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> dict:
    """Update the organization policy."""
    org = _get_org(session, api_key)

    current_policy = dict(org.policy)

    if policy_update.logging_level is not None:
        current_policy["logging_level"] = policy_update.logging_level
    if policy_update.frameworks is not None:
        current_policy["frameworks"] = policy_update.frameworks
    if policy_update.alert_rules is not None:
        current_policy["alert_rules"] = policy_update.alert_rules
    if policy_update.blocking_rules is not None:
        current_policy["blocking_rules"] = policy_update.blocking_rules

    org.policy = current_policy
    org.updated_at = datetime.now(UTC)
    session.add(org)
    session.commit()
    session.refresh(org)

    return org.policy
