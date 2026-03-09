"""Audit event model and schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, Index
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel
from ulid import ULID


def _generate_ulid() -> str:
    return str(ULID())


class AuditEventBase(SQLModel):
    """Base schema shared by create and read models."""

    agent_id: str = Field(max_length=255)
    action: str = Field(max_length=255)
    data: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False, default={})
    )
    context: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False, default={})
    )
    reasoning: str | None = Field(default=None, max_length=2000)


class AuditEvent(AuditEventBase, table=True):
    """Persisted audit event in the database."""

    __tablename__ = "audit_events"

    id: str = Field(default_factory=_generate_ulid, primary_key=True)
    api_key_id: str = Field(foreign_key="api_keys.id")

    risk_level: str | None = None
    pii_detected: bool = False
    pii_fields: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False, default=[])
    )
    frameworks: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False, default={})
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_audit_events_agent_id", "agent_id"),
        Index("ix_audit_events_action", "action"),
        Index("ix_audit_events_created_at", "created_at"),
        Index("ix_audit_events_risk_level", "risk_level"),
        Index("ix_audit_events_api_key_id", "api_key_id"),
    )


class AuditEventCreate(AuditEventBase):
    """Schema for creating an audit event (client request body)."""


class AuditEventRead(AuditEventBase):
    """Schema for reading an audit event (API response body)."""

    id: str
    risk_level: str | None = None
    pii_detected: bool = False
    pii_fields: list[str] = Field(default_factory=list)
    frameworks: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    stored: bool = True
    decision: str = "allow"
    reason: str | None = None
