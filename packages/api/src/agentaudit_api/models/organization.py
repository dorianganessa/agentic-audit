from datetime import UTC, datetime

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel
from ulid import ULID

DEFAULT_POLICY = {
    "logging_level": "standard",
    "frameworks": {"gdpr": True, "ai_act": True, "soc2": False},
    "alert_rules": [],
    "blocking_rules": {"enabled": False, "block_on": "critical"},
}


def generate_ulid() -> str:
    return str(ULID())


class Organization(SQLModel, table=True):
    __tablename__ = "organizations"

    id: str = Field(default_factory=generate_ulid, primary_key=True)
    name: str
    policy: dict = Field(
        default_factory=lambda: {**DEFAULT_POLICY},
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PolicyUpdate(SQLModel):
    """Schema for updating organization policy."""

    logging_level: str | None = None
    frameworks: dict | None = None
    alert_rules: list | None = None
    blocking_rules: dict | None = None
