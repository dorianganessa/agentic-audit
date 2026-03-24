"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from agentaudit_api.config import Settings

_engine: Engine | None = None


def get_engine(database_url: str | None = None) -> Engine:
    """Return the SQLAlchemy engine, creating it if necessary.

    Args:
        database_url: Explicit database URL. If provided, creates a new
            engine without caching (useful for tests).
    """
    global _engine  # noqa: PLW0603
    if database_url is not None:
        return create_engine(database_url, echo=False)
    if _engine is None:
        settings = Settings()
        if not settings.database_url:
            raise RuntimeError(
                "AGENTAUDIT_DATABASE_URL environment variable is required. "
                "Example: postgresql+psycopg2://user:pass@localhost:5432/agentaudit"
            )
        _engine = create_engine(
            settings.database_url,
            echo=False,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_pool_max_overflow,
            pool_recycle=settings.db_pool_recycle,
            pool_pre_ping=settings.db_pool_pre_ping,
        )
    return _engine


def check_db_health() -> bool:
    """Return True if the database is reachable."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    engine = get_engine()
    with Session(engine) as session:
        yield session
