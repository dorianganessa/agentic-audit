"""Data retention: delete audit events older than the configured TTL."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from agentaudit_api.config import Settings
from agentaudit_api.database import get_engine
from agentaudit_api.models.event import AuditEvent

logger = logging.getLogger(__name__)

BATCH_SIZE = 1_000


def purge_expired_events(retention_days: int | None = None) -> int:
    """Delete events older than *retention_days*.

    Args:
        retention_days: Override from settings. 0 means keep everything.

    Returns:
        Number of rows deleted.
    """
    if retention_days is None:
        retention_days = Settings().retention_days

    if retention_days <= 0:
        logger.info("Retention disabled (retention_days=%d), skipping purge", retention_days)
        return 0

    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    total_deleted = 0

    engine = get_engine()
    with Session(engine) as session:
        while True:
            ids = (
                session.query(AuditEvent.id)
                .filter(AuditEvent.created_at < cutoff)  # type: ignore[arg-type]
                .limit(BATCH_SIZE)
                .all()
            )
            if not ids:
                break
            id_list = [row[0] for row in ids]
            deleted = (
                session.query(AuditEvent)
                .filter(AuditEvent.id.in_(id_list))  # type: ignore[union-attr]
                .delete(synchronize_session=False)
            )
            session.commit()
            total_deleted += deleted

    logger.info(
        "Retention purge complete: deleted %d events older than %d days",
        total_deleted,
        retention_days,
    )
    return total_deleted


def _cli() -> None:
    """CLI entrypoint: ``agentaudit-purge [--days N]``."""
    import argparse
    import sys

    from agentaudit_api.config import configure_logging

    configure_logging()

    parser = argparse.ArgumentParser(description="Purge expired audit events")
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Override retention_days from settings (0 = dry-run, keeps all)",
    )
    args = parser.parse_args()
    deleted = purge_expired_events(retention_days=args.days)
    sys.stdout.write(f"Deleted {deleted} events\n")
