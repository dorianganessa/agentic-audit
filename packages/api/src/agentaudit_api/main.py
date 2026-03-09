"""FastAPI application factory and global instance."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentaudit_api import __version__
from agentaudit_api.api.router import api_router, dashboard_router
from agentaudit_api.config import configure_logging, get_settings
from agentaudit_api.database import get_session

logger = logging.getLogger(__name__)


def create_app(database_url: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        database_url: Optional database URL override (used in tests).
    """
    settings = get_settings()
    configure_logging(settings.log_level)

    application = FastAPI(
        title="AgentAudit",
        description="Log, classify and audit AI agent actions for GDPR/AI Act/SOC2 compliance",
        version=__version__,
    )

    if database_url is not None:
        engine = create_engine(database_url, echo=False)

        def override_session() -> Any:  # noqa: ANN401
            with Session(engine) as session:
                yield session

        application.dependency_overrides[get_session] = override_session

    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch unhandled exceptions and return a generic 500 response."""
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    @application.get("/health")
    def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok", "version": __version__}

    application.include_router(api_router)
    application.include_router(dashboard_router)

    return application


app = create_app()
