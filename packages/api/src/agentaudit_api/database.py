from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentaudit_api.config import Settings

_engine = None


def get_engine(database_url: str | None = None):
    global _engine  # noqa: PLW0603
    if database_url is not None:
        return create_engine(database_url, echo=False)
    if _engine is None:
        settings = Settings()
        _engine = create_engine(settings.database_url, echo=False)
    return _engine


def get_session() -> Generator[Session, None, None]:
    engine = get_engine()
    with Session(engine) as session:
        yield session
