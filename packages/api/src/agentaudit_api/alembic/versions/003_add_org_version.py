"""Add version column to organizations for optimistic locking

Revision ID: 003
Revises: 002
Create Date: 2026-03-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("version", sa.Integer(), nullable=True),
    )
    op.execute("UPDATE organizations SET version = 1 WHERE version IS NULL")
    op.alter_column("organizations", "version", nullable=False)


def downgrade() -> None:
    op.drop_column("organizations", "version")
