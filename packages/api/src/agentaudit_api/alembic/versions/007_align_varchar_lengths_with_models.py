"""Align VARCHAR column lengths with SQLModel max_length declarations.

Revision ID: 007
Revises: 006
Create Date: 2026-04-24

Several columns in the initial migration (001) were created as unbounded
VARCHAR but the SQLModel declares an explicit max_length. The test suite
uses SQLModel.metadata.create_all and so has the bounded types, hiding
the drift. Production databases migrated via alembic accept values that
would be rejected in tests.

Columns aligned here (all old definition: VARCHAR → new: VARCHAR(N)):

  api_keys.key_hash     → VARCHAR(64)   (sha256 hex digest)
  api_keys.key_prefix   → VARCHAR(20)
  api_keys.name         → VARCHAR(255)
  audit_events.agent_id → VARCHAR(255)
  audit_events.action   → VARCHAR(255)
  audit_events.reasoning → VARCHAR(2000)
  organizations.name    → VARCHAR(255)

Each ALTER is a plain TYPE change, not a truncate — Postgres will reject
the migration if any existing row exceeds the new length, which is the
right behavior (loud failure, operator investigates, no silent data loss).
Writes through the API already respect these limits via pydantic
validation on the SQLModel, so in-spec data from the API path will fit.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CHANGES: list[tuple[str, str, int]] = [
    ("api_keys", "key_hash", 64),
    ("api_keys", "key_prefix", 20),
    ("api_keys", "name", 255),
    ("audit_events", "agent_id", 255),
    ("audit_events", "action", 255),
    ("audit_events", "reasoning", 2000),
    ("organizations", "name", 255),
]


def upgrade() -> None:
    for table, column, length in _CHANGES:
        op.alter_column(
            table,
            column,
            existing_type=sa.String(),
            type_=sa.String(length=length),
        )


def downgrade() -> None:
    # Downgrade relaxes back to unbounded VARCHAR — safe since any value that
    # fit in VARCHAR(N) also fits in unbounded VARCHAR.
    for table, column, length in _CHANGES:
        op.alter_column(
            table,
            column,
            existing_type=sa.String(length=length),
            type_=sa.String(),
        )
