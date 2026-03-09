"""Seed script: creates a default organization and API key if none exist."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from agentaudit_api.database import get_engine
from agentaudit_api.models.api_key import (
    ApiKey,
    generate_api_key,
    hash_api_key,
    key_prefix_from_key,
)
from agentaudit_api.models.organization import Organization

logger = logging.getLogger(__name__)


def seed() -> None:
    """Create the default organization and API key if none exist."""
    engine = get_engine()
    with Session(engine) as session:
        existing = session.query(ApiKey).first()
        if existing is not None:
            logger.info("API key already exists, skipping seed.")
            return

        org = Organization(name="Default")
        session.add(org)
        session.flush()

        raw_key = generate_api_key()
        api_key = ApiKey(
            key_hash=hash_api_key(raw_key),
            key_prefix=key_prefix_from_key(raw_key),
            name="Default",
            org_id=org.id,
        )
        session.add(api_key)
        session.commit()
        # Print the key only once during initial setup
        print(f"Default API key: {raw_key}")  # noqa: T201


if __name__ == "__main__":
    seed()
