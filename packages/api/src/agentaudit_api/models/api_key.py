"""API key model and utilities for authentication."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel
from ulid import ULID

API_KEY_PREFIX = "aa_live_"


def generate_ulid() -> str:
    """Generate a new ULID string."""
    return str(ULID())


def generate_api_key() -> str:
    """Generate an API key in the format ``aa_live_`` + 32 hex chars."""
    return API_KEY_PREFIX + secrets.token_hex(16)


def hash_api_key(key: str) -> str:
    """Hash an API key with SHA-256.

    Returns the hex digest of the SHA-256 hash.
    """
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """Verify an API key against a stored hash using constant-time comparison.

    Args:
        provided_key: The raw API key provided by the client.
        stored_hash: The stored SHA-256 hash to compare against.

    Returns:
        True if the key matches, False otherwise.
    """
    computed_hash = hash_api_key(provided_key)
    return hmac.compare_digest(computed_hash, stored_hash)


def key_prefix_from_key(key: str) -> str:
    """Extract the prefix for identification: ``aa_live_`` + first 8 chars of the random part."""
    return key[: len(API_KEY_PREFIX) + 8]


class ApiKey(SQLModel, table=True):
    """API key for authenticating requests."""

    __tablename__ = "api_keys"

    id: str = Field(default_factory=generate_ulid, primary_key=True)
    key_hash: str = Field(unique=True, max_length=64)
    key_prefix: str = Field(max_length=20)
    name: str = Field(default="Default", max_length=255)
    org_id: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
