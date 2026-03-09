import hashlib
import secrets
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel
from ulid import ULID

API_KEY_PREFIX = "aa_live_"


def generate_ulid() -> str:
    return str(ULID())


def generate_api_key() -> str:
    """Generate an API key in the format aa_live_ + 32 hex chars."""
    return API_KEY_PREFIX + secrets.token_hex(16)


def hash_api_key(key: str) -> str:
    """Hash an API key with SHA-256."""
    return hashlib.sha256(key.encode()).hexdigest()


def key_prefix_from_key(key: str) -> str:
    """Extract the prefix for identification: aa_live_ + first 8 chars of the random part."""
    return key[: len(API_KEY_PREFIX) + 8]


class ApiKey(SQLModel, table=True):
    __tablename__ = "api_keys"

    id: str = Field(default_factory=generate_ulid, primary_key=True)
    key_hash: str = Field(unique=True)
    key_prefix: str
    name: str = "Default"
    org_id: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
