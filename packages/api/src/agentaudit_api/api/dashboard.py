"""Dashboard routes: Jinja2 + HTMX web UI with cookie-based authentication."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Cookie, Depends, Form, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from agentaudit_api.config import get_settings
from agentaudit_api.database import get_session
from agentaudit_api.models.ai_system import AISystemRead
from agentaudit_api.models.api_key import ApiKey, hash_api_key
from agentaudit_api.models.event import AuditEvent, AuditEventRead
from agentaudit_api.models.organization import Organization
from agentaudit_api.services.event_service import get_event, get_stats, list_events
from agentaudit_api.services.report_pdf import generate_pdf
from agentaudit_api.services.system_service import list_systems

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

router = APIRouter()

COOKIE_NAME = "agentaudit_session"
COOKIE_MAX_AGE = 86400 * 7  # 7 days


def _org_event_scope(session: Session, org_id: str | None) -> Any:
    """SQL predicate: audit_events belonging to any API key in the given org."""
    keys_for_org = (
        session.query(ApiKey.id)  # type: ignore[call-overload]
        .filter(ApiKey.org_id == org_id)
        .subquery()
    )
    return AuditEvent.api_key_id.in_(keys_for_org.select())  # type: ignore[attr-defined]


def _get_authenticated_api_key(
    session: Session,
    agentaudit_session: str | None = Cookie(None),
) -> ApiKey | None:
    """Validate the dashboard session cookie and return the API key."""
    if not agentaudit_session:
        return None
    api_key = (
        session.query(ApiKey)
        .filter(
            ApiKey.key_hash == agentaudit_session,  # type: ignore[arg-type]
            ApiKey.is_active.is_(True),  # type: ignore[attr-defined]
        )
        .first()
    )
    return api_key


def _require_auth(session: Session, request: Request) -> ApiKey | None:
    """Check auth cookie and return the API key or None for redirect."""
    cookie_val = request.cookies.get(COOKIE_NAME)
    if not cookie_val:
        return None
    return _get_authenticated_api_key(session, cookie_val)


def _login_redirect() -> RedirectResponse:
    return RedirectResponse("/dashboard/login", status_code=303)


def _time_range_to_dates(time_range: str) -> tuple[datetime | None, datetime | None]:
    """Convert a time range string to (after, before) datetime tuple."""
    now = datetime.now(UTC)
    if time_range == "24h":
        return now - timedelta(hours=24), now
    if time_range == "7d":
        return now - timedelta(days=7), now
    if time_range == "30d":
        return now - timedelta(days=30), now
    return None, None


def _prettify_json(data: object) -> str:
    """Pretty-print JSON for display."""
    return json.dumps(data, indent=2, default=str)


def _risk_explanation(event: AuditEvent) -> str | None:
    """Brief explanation of why the risk level was assigned."""
    risk = event.risk_level
    if risk == "low":
        return None
    data: dict[str, Any] = event.data or {}
    command = str(data.get("command", ""))

    if risk == "critical":
        if any(kw in command.lower() for kw in ["rm -rf", "drop ", "delete from"]):
            return "Destructive command detected"
        return "Credential indicators detected"
    if risk == "high":
        if "prod" in command.lower():
            return "Production environment command"
        return "Sensitive file or PII+production"
    if risk == "medium":
        if event.pii_detected:
            return "PII detected in event data"
        return "Privileged command (sudo/chmod)"
    return None


# ---------- Login / Logout ----------


@router.get("/dashboard/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request) -> Response:
    """Render the login form."""
    return templates.TemplateResponse(
        "dashboard/login.html",
        {"request": request, "error": None, "active_page": ""},
    )


@router.post("/dashboard/login", response_class=HTMLResponse, include_in_schema=False)
def login_submit(
    request: Request,
    api_key: str = Form(...),
    session: Session = Depends(get_session),
) -> Response:
    """Validate API key and set session cookie."""
    key_hash = hash_api_key(api_key)
    db_key = (
        session.query(ApiKey)
        .filter(
            ApiKey.key_hash == key_hash,  # type: ignore[arg-type]
            ApiKey.is_active.is_(True),  # type: ignore[attr-defined]
        )
        .first()
    )
    if db_key is None:
        return templates.TemplateResponse(
            "dashboard/login.html",
            {"request": request, "error": "Invalid API key", "active_page": ""},
            status_code=401,
        )

    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=key_hash,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/dashboard/logout", include_in_schema=False)
def logout() -> Response:
    """Clear the session cookie and redirect to login."""
    response = RedirectResponse("/dashboard/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


# ---------- Protected dashboard routes ----------


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def timeline(
    request: Request,
    risk_level: str | None = Query(None),
    agent_id: str | None = Query(None),
    action: str | None = Query(None),
    pii_detected: str | None = Query(None),
    after: str | None = Query(None),
    before: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> Response:
    """Render the event timeline dashboard."""
    api_key = _require_auth(session, request)
    if api_key is None:
        return _login_redirect()

    pii_bool = None
    if pii_detected == "true":
        pii_bool = True
    elif pii_detected == "false":
        pii_bool = False

    after_dt = datetime.fromisoformat(after) if after else None
    before_dt = datetime.fromisoformat(before) if before else None

    events, total = list_events(
        session,
        org_id=api_key.org_id,
        agent_id=agent_id or None,
        action=action or None,
        risk_level=risk_level or None,
        pii_detected=pii_bool,
        after=after_dt,
        before=before_dt,
        limit=limit,
        offset=offset,
    )

    filters: dict[str, str] = {}
    if risk_level:
        filters["risk_level"] = risk_level
    if agent_id:
        filters["agent_id"] = agent_id
    if action:
        filters["action"] = action
    if pii_detected:
        filters["pii_detected"] = pii_detected
    if after:
        filters["after"] = after
    if before:
        filters["before"] = before

    has_more = offset + limit < total
    next_offset = offset + limit

    # HTMX partial: only return the table rows
    is_htmx = request.headers.get("HX-Request") == "true"
    template_name = "dashboard/_events_rows.html" if is_htmx else "dashboard/timeline.html"

    return templates.TemplateResponse(
        template_name,
        {
            "request": request,
            "events": events,
            "total": total,
            "filters": filters,
            "has_more": has_more,
            "next_offset": next_offset,
            "active_page": "timeline",
        },
    )


@router.get("/dashboard/events/{event_id}", response_class=HTMLResponse, include_in_schema=False)
def event_detail(
    request: Request,
    event_id: str,
    session: Session = Depends(get_session),
) -> Response:
    """Render the event detail page."""
    api_key = _require_auth(session, request)
    if api_key is None:
        return _login_redirect()

    event = get_event(session, event_id, org_id=api_key.org_id)
    if event is None:
        return HTMLResponse("<h1>Event not found</h1>", status_code=404)

    event_read = AuditEventRead.model_validate(event)

    return templates.TemplateResponse(
        "dashboard/event_detail.html",
        {
            "request": request,
            "event": event_read,
            "data_json": _prettify_json(event.data),
            "context_json": _prettify_json(event.context),
            "risk_explanation": _risk_explanation(event),
            "active_page": "timeline",
        },
    )


@router.get("/dashboard/policy", response_class=HTMLResponse, include_in_schema=False)
def policy_page(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Render the policy management page."""
    api_key = _require_auth(session, request)
    if api_key is None:
        return _login_redirect()

    org = (
        session.query(Organization)
        .filter(Organization.id == api_key.org_id)  # type: ignore[arg-type]
        .first()
    )
    if org is None:
        return HTMLResponse("<h1>Organization not found</h1>", status_code=404)

    policy = org.policy

    return templates.TemplateResponse(
        "dashboard/policy.html",
        {
            "request": request,
            "policy": policy,
            "policy_json": _prettify_json(policy),
            "active_page": "policy",
        },
    )


@router.put("/dashboard/policy", response_class=HTMLResponse, include_in_schema=False)
def update_policy_form(
    request: Request,
    session: Session = Depends(get_session),
    logging_level: str = Query("standard"),
    fw_gdpr: bool = Query(False),
    fw_ai_act: bool = Query(False),
    fw_soc2: bool = Query(False),
    blocking_enabled: bool = Query(False),
    block_on: str = Query("critical"),
) -> Response:
    """Update the policy via the dashboard form (HTMX)."""
    api_key = _require_auth(session, request)
    if api_key is None:
        return HTMLResponse("Unauthorized", status_code=401)

    org = (
        session.query(Organization)
        .filter(Organization.id == api_key.org_id)  # type: ignore[arg-type]
        .first()
    )
    if org is None:
        return HTMLResponse('<div class="flash flash-error">Organization not found</div>')

    current: dict[str, Any] = dict(org.policy)
    current["logging_level"] = logging_level
    current["frameworks"] = {"gdpr": fw_gdpr, "ai_act": fw_ai_act, "soc2": fw_soc2}
    current["blocking_rules"] = {"enabled": blocking_enabled, "block_on": block_on}

    org.policy = current
    org.updated_at = datetime.now(UTC)
    session.add(org)
    session.commit()

    return HTMLResponse('<div class="flash flash-success">Policy updated successfully</div>')


@router.get("/dashboard/compliance", response_class=HTMLResponse, include_in_schema=False)
def compliance_page(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Render the AI Act compliance dashboard."""
    api_key = _require_auth(session, request)
    if api_key is None:
        return _login_redirect()

    org = (
        session.query(Organization)
        .filter(Organization.id == api_key.org_id)  # type: ignore[arg-type]
        .first()
    )
    if org is None:
        return HTMLResponse("<h1>Organization not found</h1>", status_code=404)

    systems = list_systems(session, org.id)
    policy = dict(org.policy)
    settings = get_settings()
    retention = policy.get("retention_days", settings.retention_days)

    high_risk = [s for s in systems if s.risk_classification == "high"]
    classified = sum(1 for s in systems if s.risk_classification != "unclassified")
    fria_completed = sum(1 for s in high_risk if s.fria_status == "completed")
    contracts_ok = sum(1 for s in systems if s.contract_has_ai_annex)
    prohibited = [s for s in systems if s.risk_classification == "prohibited"]

    checks = {
        "all_classified": len(systems) > 0 and classified == len(systems),
        "no_prohibited": len(prohibited) == 0,
        "fria_complete": len(high_risk) == 0 or fria_completed == len(high_risk),
        "contracts_reviewed": len(systems) == 0 or contracts_ok == len(systems),
        "retention_compliant": retention >= 180,
    }
    score = int(sum(checks.values()) / len(checks) * 100) if checks else 0

    # Deadlines
    now = datetime.now(UTC).replace(tzinfo=None)
    deadlines: list[dict[str, Any]] = []
    for s in systems:
        if s.next_review_date and s.next_review_date > now:
            deadlines.append(
                {
                    "system": s.name,
                    "type": "system_review",
                    "date": s.next_review_date.isoformat(),
                }
            )
        if s.fria_next_review and s.fria_next_review > now:
            deadlines.append(
                {
                    "system": s.name,
                    "type": "fria_review",
                    "date": s.fria_next_review.isoformat(),
                }
            )
    deadlines.sort(key=lambda d: d["date"])

    return templates.TemplateResponse(
        "dashboard/compliance.html",
        {
            "request": request,
            "score": score,
            "checks": checks,
            "summary": {
                "total_systems": len(systems),
                "classified": classified,
                "high_risk": len(high_risk),
                "fria_completed": fria_completed,
                "contracts_with_annex": contracts_ok,
                "prohibited_systems": len(prohibited),
                "retention_days": retention,
                "retention_compliant": retention >= 180,
            },
            "systems": [AISystemRead.model_validate(s) for s in systems],
            "high_risk_systems": [AISystemRead.model_validate(s) for s in high_risk],
            "deadlines": deadlines,
            "compliance_preset": policy.get("compliance_preset"),
            "active_page": "compliance",
        },
    )


@router.get("/dashboard/stats", response_class=HTMLResponse, include_in_schema=False)
def stats_page(
    request: Request,
    range: str = Query("7d"),
    session: Session = Depends(get_session),
) -> Response:
    """Render the stats overview page."""
    api_key = _require_auth(session, request)
    if api_key is None:
        return _login_redirect()

    after, before = _time_range_to_dates(range)
    stats = get_stats(session, org_id=api_key.org_id, after=after, before=before)

    org_scope = _org_event_scope(session, api_key.org_id)

    # Top agents
    agents_q = session.query(AuditEvent.agent_id, func.count()).filter(org_scope)  # type: ignore[call-overload]
    if after:
        agents_q = agents_q.filter(AuditEvent.created_at > after)
    if before:
        agents_q = agents_q.filter(AuditEvent.created_at < before)
    top_agents = agents_q.group_by(AuditEvent.agent_id).order_by(func.count().desc()).limit(5).all()

    # Top actions by risk (high/critical actions first)
    actions_q = session.query(AuditEvent.action, func.count()).filter(  # type: ignore[call-overload]
        org_scope,
        AuditEvent.risk_level.in_(["high", "critical"]),  # type: ignore[union-attr]
    )
    if after:
        actions_q = actions_q.filter(AuditEvent.created_at > after)
    if before:
        actions_q = actions_q.filter(AuditEvent.created_at < before)
    top_actions = actions_q.group_by(AuditEvent.action).order_by(func.count().desc()).limit(5).all()

    return templates.TemplateResponse(
        "dashboard/stats.html",
        {
            "request": request,
            "stats": stats,
            "top_agents": top_agents,
            "top_actions": top_actions,
            "time_range": range,
            "active_page": "stats",
        },
    )


@router.get("/dashboard/report/pdf", include_in_schema=False)
def report_pdf(
    request: Request,
    range: str = Query("7d"),
    session: Session = Depends(get_session),
) -> Response:
    """Generate and download a PDF compliance report."""
    api_key = _require_auth(session, request)
    if api_key is None:
        return _login_redirect()

    after, before = _time_range_to_dates(range)
    stats = get_stats(session, org_id=api_key.org_id, after=after, before=before)

    # Get high/critical events for the report
    high_events, _ = list_events(
        session,
        org_id=api_key.org_id,
        risk_level=None,
        after=after,
        before=before,
        limit=200,
        offset=0,
    )
    risky = [e for e in high_events if e.risk_level in ("high", "critical")][:10]

    # Framework coverage
    framework_counts: dict[str, dict[str, int]] = {}
    all_events, _ = list_events(
        session, org_id=api_key.org_id, after=after, before=before, limit=1000, offset=0
    )
    for ev in all_events:
        for fw_name, articles in (ev.frameworks or {}).items():
            if fw_name not in framework_counts:
                framework_counts[fw_name] = {}
            for art in articles:
                framework_counts[fw_name][art] = framework_counts[fw_name].get(art, 0) + 1

    pdf_bytes = generate_pdf(
        stats=stats,
        risky_events=risky,
        framework_counts=framework_counts,
        after=after,
        before=before,
        time_range=range,
    )

    filename = f"agentaudit_report_{range}_{datetime.now(UTC).strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
