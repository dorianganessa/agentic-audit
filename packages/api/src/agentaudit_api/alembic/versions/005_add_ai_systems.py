"""Add ai_systems table for AI Act compliance registry.

Revision ID: 005
Revises: 004
Create Date: 2026-04-24

The AISystem model was added in the v0.2.0 release but never captured in an
alembic migration — the test suite uses SQLModel.metadata.create_all and so
silently hides the gap. Fresh deploys via `alembic upgrade head` (as the
docker-compose image does) fail at the first POST /v1/systems with
`relation "ai_systems" does not exist`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_systems",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("vendor", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("description", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("use_case", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column(
            "agent_id_patterns",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "risk_classification",
            sa.String(length=20),
            nullable=False,
            server_default="unclassified",
        ),
        sa.Column(
            "classification_rationale",
            sa.String(length=2000),
            nullable=False,
            server_default="",
        ),
        sa.Column("annex_iii_category", sa.String(length=50), nullable=True),
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default="deployer",
        ),
        sa.Column(
            "contract_has_ai_annex",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "provider_obligations_documented",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("contract_last_reviewed", sa.DateTime(), nullable=True),
        sa.Column(
            "contract_notes",
            sa.String(length=2000),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "fria_status",
            sa.String(length=20),
            nullable=False,
            server_default="not_started",
        ),
        sa.Column("fria_completed_at", sa.DateTime(), nullable=True),
        sa.Column("fria_next_review", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("next_review_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ai_systems_org_id", "ai_systems", ["org_id"])
    op.create_index(
        "ix_ai_systems_risk_classification",
        "ai_systems",
        ["risk_classification"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_systems_risk_classification", table_name="ai_systems")
    op.drop_index("ix_ai_systems_org_id", table_name="ai_systems")
    op.drop_table("ai_systems")
