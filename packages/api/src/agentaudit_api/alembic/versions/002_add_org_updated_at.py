"""Add updated_at to organizations

Revision ID: 002
Revises: 001
Create Date: 2026-03-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.execute("UPDATE organizations SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("organizations", "updated_at", nullable=False)


def downgrade() -> None:
    op.drop_column("organizations", "updated_at")
