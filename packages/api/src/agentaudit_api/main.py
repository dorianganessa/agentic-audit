"""FastAPI application factory and global instance."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from agentaudit_api import __version__
from agentaudit_api.api.router import api_router, dashboard_router
from agentaudit_api.config import configure_logging, get_settings
from agentaudit_api.database import get_session

logger = logging.getLogger(__name__)

# ---------- Rate limiting middleware ----------

# Defaults: 100 requests per minute per IP for API, 30 for dashboard
API_RATE_LIMIT = 100
DASHBOARD_RATE_LIMIT = 30
RATE_WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory per-IP rate limiter."""

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Any) -> StarletteResponse:
        # Skip health check
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        path = request.url.path

        # Choose limit based on path
        limit = DASHBOARD_RATE_LIMIT if path.startswith("/dashboard") else API_RATE_LIMIT
        key = f"{client_ip}:{'/dashboard' if path.startswith('/dashboard') else '/api'}"

        # Prune old entries
        timestamps = self._requests[key]
        cutoff = now - RATE_WINDOW_SECONDS
        self._requests[key] = [ts for ts in timestamps if ts > cutoff]

        if len(self._requests[key]) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(RATE_WINDOW_SECONDS)},
            )

        self._requests[key].append(now)
        return await call_next(request)


def create_app(database_url: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        database_url: Optional database URL override (used in tests).
    """
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)

    application = FastAPI(
        title="AgenticAudit",
        description="Log, classify and audit AI agent actions for GDPR/AI Act/SOC2 compliance",
        version=__version__,
    )

    application.add_middleware(RateLimitMiddleware)

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
    def health(session: Session = Depends(get_session)) -> dict[str, Any]:
        """Health check endpoint with database connectivity verification."""
        try:
            session.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False
        health_status = "ok" if db_ok else "degraded"
        return {
            "status": health_status,
            "version": __version__,
            "database": "connected" if db_ok else "unreachable",
        }

    application.include_router(api_router)
    application.include_router(dashboard_router)

    return application


app = create_app()
