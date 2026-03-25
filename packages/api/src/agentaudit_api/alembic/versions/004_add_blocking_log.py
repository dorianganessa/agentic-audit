"""Add blocking_log table for compliance evidence.

Revision ID: 004
Revises: 003
"""

from alembic import op
import sqlalchemy as sa


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blocking_log",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("org_id", sa.String(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("agent_id", sa.String(255), nullable=False),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("block_reason", sa.String(500), nullable=False),
        sa.Column("blocked_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_blocking_log_org_id", "blocking_log", ["org_id"])
    op.create_index("ix_blocking_log_blocked_at", "blocking_log", ["blocked_at"])
    op.create_index("ix_blocking_log_agent_id", "blocking_log", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_blocking_log_agent_id", table_name="blocking_log")
    op.drop_index("ix_blocking_log_blocked_at", table_name="blocking_log")
    op.drop_index("ix_blocking_log_org_id", table_name="blocking_log")
    op.drop_table("blocking_log")
