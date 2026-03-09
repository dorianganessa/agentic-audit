"""Application configuration loaded from environment variables."""

from __future__ import annotations

import logging

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """AgentAudit API server settings.

    All settings can be overridden via environment variables
    prefixed with ``AGENTAUDIT_``.
    """

    model_config = SettingsConfigDict(env_prefix="AGENTAUDIT_")

    database_url: str = "postgresql+psycopg2://agentaudit:agentaudit@localhost:5432/agentaudit"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    log_level: str = "INFO"


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


def configure_logging(level: str = "INFO") -> None:
    """Configure stdlib logging with a consistent format.

    Args:
        level: Logging level name (DEBUG, INFO, WARNING, ERROR).
    """
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
        force=True,
    )
