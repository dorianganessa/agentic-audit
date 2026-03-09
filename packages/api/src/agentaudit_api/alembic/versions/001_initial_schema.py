"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("key_hash", sa.String(), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False, server_default="Default"),
        sa.Column("org_id", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("context", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("reasoning", sa.String(), nullable=True),
        sa.Column(
            "api_key_id",
            sa.String(),
            sa.ForeignKey("api_keys.id"),
            nullable=False,
        ),
        sa.Column("risk_level", sa.String(), nullable=True),
        sa.Column("pii_detected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("pii_fields", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("frameworks", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_audit_events_agent_id", "audit_events", ["agent_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_index("ix_audit_events_risk_level", "audit_events", ["risk_level"])
    op.create_index("ix_audit_events_api_key_id", "audit_events", ["api_key_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("api_keys")
    op.drop_table("organizations")
