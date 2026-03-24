"""API router composition: combines events, org, systems, compliance, dashboard, and OTLP routes."""

from __future__ import annotations

from fastapi import APIRouter

from agentaudit_api.api.compliance import router as compliance_router
from agentaudit_api.api.dashboard import router as dashboard_router
from agentaudit_api.api.events import router as events_router
from agentaudit_api.api.org import router as org_router
from agentaudit_api.api.otlp import router as otlp_router
from agentaudit_api.api.systems import router as systems_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(events_router)
api_router.include_router(org_router)
api_router.include_router(otlp_router)
api_router.include_router(systems_router)
api_router.include_router(compliance_router)

# Dashboard is mounted at root level (no /v1 prefix)
__all__ = ["api_router", "dashboard_router"]
