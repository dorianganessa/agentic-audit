from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentaudit_api import __version__
from agentaudit_api.api.router import api_router, dashboard_router
from agentaudit_api.database import get_session


def create_app(database_url: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AgentAudit",
        description="Log, classify and audit AI agent actions for GDPR/AI Act/SOC2 compliance",
        version=__version__,
    )

    if database_url is not None:
        engine = create_engine(database_url, echo=False)

        def override_session():
            with Session(engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_session

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__}

    app.include_router(api_router)
    app.include_router(dashboard_router)

    return app


app = create_app()
