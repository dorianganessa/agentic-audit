"""AI System registry model — tracks AI systems for AI Act compliance."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, Index
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel
from ulid import ULID


def _generate_ulid() -> str:
    return str(ULID())


# Annex III categories for high-risk classification
ANNEX_III_CATEGORIES = (
    "biometric",
    "critical_infrastructure",
    "education",
    "employment",
    "essential_services",
    "law_enforcement",
    "migration",
    "democratic_processes",
)

RISK_CLASSIFICATIONS = ("prohibited", "high", "limited", "minimal", "unclassified")

FRIA_STATUSES = ("not_started", "in_progress", "completed", "due_for_review")

ROLES = ("deployer", "provider", "both")


class AISystem(SQLModel, table=True):
    """An AI system registered for AI Act compliance tracking."""

    __tablename__ = "ai_systems"

    id: str = Field(default_factory=_generate_ulid, primary_key=True)
    org_id: str

    # Identity
    name: str = Field(max_length=255)
    vendor: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=2000)
    use_case: str = Field(default="", max_length=1000)

    # Event linking — list of agent_id patterns that map to this system
    agent_id_patterns: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=[]),
    )

    # AI Act classification
    risk_classification: str = Field(default="unclassified", max_length=20)
    classification_rationale: str = Field(default="", max_length=2000)
    annex_iii_category: str | None = Field(default=None, max_length=50)
    role: str = Field(default="deployer", max_length=20)

    # Contract / vendor tracking
    contract_has_ai_annex: bool = False
    provider_obligations_documented: bool = False
    contract_last_reviewed: datetime | None = None
    contract_notes: str = Field(default="", max_length=2000)

    # FRIA tracking
    fria_status: str = Field(default="not_started", max_length=20)
    fria_completed_at: datetime | None = None
    fria_next_review: datetime | None = None

    # General
    is_active: bool = True
    next_review_date: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_ai_systems_org_id", "org_id"),
        Index("ix_ai_systems_risk_classification", "risk_classification"),
    )


class AISystemCreate(SQLModel):
    """Schema for creating an AI system."""

    name: str = Field(max_length=255)
    vendor: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=2000)
    use_case: str = Field(default="", max_length=1000)
    agent_id_patterns: list[str] = Field(default_factory=list)
    risk_classification: str = Field(default="unclassified", max_length=20)
    classification_rationale: str = Field(default="", max_length=2000)
    annex_iii_category: str | None = None
    role: str = Field(default="deployer", max_length=20)
    contract_has_ai_annex: bool = False
    provider_obligations_documented: bool = False
    contract_last_reviewed: datetime | None = None
    contract_notes: str = Field(default="", max_length=2000)
    fria_status: str = Field(default="not_started", max_length=20)
    fria_completed_at: datetime | None = None
    fria_next_review: datetime | None = None
    next_review_date: datetime | None = None


class AISystemUpdate(SQLModel):
    """Schema for partial update of an AI system."""

    name: str | None = None
    vendor: str | None = None
    description: str | None = None
    use_case: str | None = None
    agent_id_patterns: list[str] | None = None
    risk_classification: str | None = None
    classification_rationale: str | None = None
    annex_iii_category: str | None = None
    role: str | None = None
    contract_has_ai_annex: bool | None = None
    provider_obligations_documented: bool | None = None
    contract_last_reviewed: datetime | None = None
    contract_notes: str | None = None
    fria_status: str | None = None
    fria_completed_at: datetime | None = None
    fria_next_review: datetime | None = None
    next_review_date: datetime | None = None
    is_active: bool | None = None


class AISystemRead(SQLModel):
    """Schema for reading an AI system (API response)."""

    id: str
    org_id: str
    name: str
    vendor: str
    description: str
    use_case: str
    agent_id_patterns: list[str]
    risk_classification: str
    classification_rationale: str
    annex_iii_category: str | None
    role: str
    contract_has_ai_annex: bool
    provider_obligations_documented: bool
    contract_last_reviewed: datetime | None
    contract_notes: str
    fria_status: str
    fria_completed_at: datetime | None
    fria_next_review: datetime | None
    is_active: bool
    next_review_date: datetime | None
    created_at: datetime
    updated_at: datetime
