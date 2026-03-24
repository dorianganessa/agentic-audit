"""Application configuration loaded from environment variables."""

from __future__ import annotations

import logging

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """AgenticAudit API server settings.

    All settings can be overridden via environment variables
    prefixed with ``AGENTAUDIT_``.
    """

    model_config = SettingsConfigDict(env_prefix="AGENTAUDIT_")

    database_url: str = ""
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    log_level: str = "INFO"
    log_format: str = "text"  # "text" or "json"

    # DB connection pool
    db_pool_size: int = 5
    db_pool_max_overflow: int = 10
    db_pool_recycle: int = 1800  # seconds
    db_pool_pre_ping: bool = True

    # Data retention
    retention_days: int = 90  # 0 = keep forever

    # Request body limits (bytes)
    max_event_data_bytes: int = 65_536  # 64 KB
    max_event_context_bytes: int = 16_384  # 16 KB


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    """Configure stdlib logging with a consistent format.

    Args:
        level: Logging level name (DEBUG, INFO, WARNING, ERROR).
        fmt: "text" for human-readable, "json" for structured JSON lines.
    """
    if fmt == "json":
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter())
        logging.root.handlers = [handler]
        logging.root.setLevel(getattr(logging, level.upper(), logging.INFO))
    else:
        logging.basicConfig(
            format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            level=getattr(logging, level.upper(), logging.INFO),
            force=True,
        )


class JsonLogFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import UTC, datetime

        payload: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1] is not None:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)
