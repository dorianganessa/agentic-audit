"""Organization model and policy schema."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel
from ulid import ULID

DEFAULT_POLICY: dict[str, Any] = {
    "logging_level": "standard",
    "frameworks": {"gdpr": True, "ai_act": True, "soc2": False},
    "alert_rules": [],
    "blocking_rules": {"enabled": False, "block_on": "critical"},
}


def _generate_ulid() -> str:
    return str(ULID())


class Organization(SQLModel, table=True):
    """Organization with associated compliance policy."""

    __tablename__ = "organizations"

    id: str = Field(default_factory=_generate_ulid, primary_key=True)
    name: str = Field(max_length=255)
    policy: dict[str, Any] = Field(
        default_factory=lambda: {**DEFAULT_POLICY},
        sa_column=Column(JSON, nullable=False),
    )
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PolicyUpdate(SQLModel):
    """Schema for partial policy updates."""

    logging_level: str | None = None
    frameworks: dict[str, Any] | None = None
    alert_rules: list[dict[str, Any]] | None = None
    blocking_rules: dict[str, Any] | None = None
    compliance_preset: str | None = None
    retention_days: int | None = None
