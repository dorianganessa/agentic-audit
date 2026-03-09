from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from agentaudit_api.database import get_session
from agentaudit_api.models.api_key import ApiKey, hash_api_key

security = HTTPBearer()


def get_current_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
    session: Session = Depends(get_session),
) -> ApiKey:
    """Validate the Bearer token and return the corresponding ApiKey."""
    key_hash = hash_api_key(credentials.credentials)
    api_key = session.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
    if api_key is None or not api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
        )
    return api_key
