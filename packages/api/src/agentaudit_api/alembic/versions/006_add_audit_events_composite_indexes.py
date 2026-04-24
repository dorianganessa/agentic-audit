"""Add composite indexes on audit_events declared on the SQLModel.

Revision ID: 006
Revises: 005
Create Date: 2026-04-24

Two composite indexes are declared in `AuditEvent.__table_args__` but were
never captured in an alembic migration:

  - ix_audit_events_apikey_created: (api_key_id, created_at)
  - ix_audit_events_apikey_risk:    (api_key_id, risk_level)

The test suite uses SQLModel.metadata.create_all and so has these indexes,
hiding the gap. Production databases migrated via alembic only have the
single-column indexes from 001, which means common per-org queries (events
by time window, events by risk level within an org) fall back to scanning
+ filtering by api_key_id rather than using the composite index.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_audit_events_apikey_created",
        "audit_events",
        ["api_key_id", "created_at"],
    )
    op.create_index(
        "ix_audit_events_apikey_risk",
        "audit_events",
        ["api_key_id", "risk_level"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_apikey_risk", table_name="audit_events")
    op.drop_index("ix_audit_events_apikey_created", table_name="audit_events")
