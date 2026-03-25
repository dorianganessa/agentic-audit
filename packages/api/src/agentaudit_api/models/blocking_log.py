"""Blocking log model — records evidence of blocked agent actions for compliance."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Index
from sqlmodel import Field, SQLModel
from ulid import ULID


def _generate_ulid() -> str:
    return str(ULID())


class BlockingLog(SQLModel, table=True):
    """A record of a blocked agent action. Stored separately from audit_events
    because blocked events are intentionally not persisted to the main event store."""

    __tablename__ = "blocking_log"

    id: str = Field(default_factory=_generate_ulid, primary_key=True)
    org_id: str = Field(foreign_key="organizations.id")
    agent_id: str = Field(max_length=255)
    action: str = Field(max_length=255)
    risk_level: str = Field(max_length=20)
    block_reason: str = Field(max_length=500)
    blocked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_blocking_log_org_id", "org_id"),
        Index("ix_blocking_log_blocked_at", "blocked_at"),
        Index("ix_blocking_log_agent_id", "agent_id"),
    )
