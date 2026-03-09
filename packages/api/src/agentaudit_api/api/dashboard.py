"""Dashboard routes: Jinja2 + HTMX web UI."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from agentaudit_api.database import get_session
from agentaudit_api.models.api_key import ApiKey
from agentaudit_api.models.event import AuditEvent, AuditEventRead
from agentaudit_api.models.organization import Organization
from agentaudit_api.services.event_service import get_event, get_stats, list_events
from agentaudit_api.services.report_pdf import generate_pdf

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)

router = APIRouter()


def _get_first_api_key(session: Session) -> ApiKey | None:
    """Get the first active API key (dashboard uses session-less auth for now)."""
    return session.query(ApiKey).filter(ApiKey.is_active.is_(True)).first()


def _time_range_to_dates(time_range: str) -> tuple[datetime | None, datetime | None]:
    now = datetime.now(UTC)
    if time_range == "24h":
        return now - timedelta(hours=24), now
    if time_range == "7d":
        return now - timedelta(days=7), now
    if time_range == "30d":
        return now - timedelta(days=30), now
    return None, None


def _prettify_json(data: object) -> str:
    """Pretty-print JSON with HTML syntax highlighting."""
    raw = json.dumps(data, indent=2, default=str)
    # Simple regex-free approach: just return raw JSON, CSS handles mono styling
    return raw


def _risk_explanation(event: AuditEvent) -> str | None:
    """Brief explanation of why the risk level was assigned."""
    risk = event.risk_level
    if risk == "low":
        return None
    data = event.data or {}
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


@router.get("/dashboard", response_class=HTMLResponse)
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
):
    api_key = _get_first_api_key(session)
    if api_key is None:
        return HTMLResponse("<h1>No API key configured</h1>", status_code=500)

    pii_bool = None
    if pii_detected == "true":
        pii_bool = True
    elif pii_detected == "false":
        pii_bool = False

    after_dt = datetime.fromisoformat(after) if after else None
    before_dt = datetime.fromisoformat(before) if before else None

    events, total = list_events(
        session,
        api_key.id,
        agent_id=agent_id or None,
        action=action or None,
        risk_level=risk_level or None,
        pii_detected=pii_bool,
        after=after_dt,
        before=before_dt,
        limit=limit,
        offset=offset,
    )

    filters = {}
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


@router.get("/dashboard/events/{event_id}", response_class=HTMLResponse)
def event_detail(
    request: Request,
    event_id: str,
    session: Session = Depends(get_session),
):
    api_key = _get_first_api_key(session)
    if api_key is None:
        return HTMLResponse("<h1>No API key configured</h1>", status_code=500)

    event = get_event(session, event_id, api_key.id)
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


@router.get("/dashboard/policy", response_class=HTMLResponse)
def policy_page(
    request: Request,
    session: Session = Depends(get_session),
):
    api_key = _get_first_api_key(session)
    if api_key is None:
        return HTMLResponse("<h1>No API key configured</h1>", status_code=500)

    org = session.query(Organization).filter(Organization.id == api_key.org_id).first()
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


@router.put("/dashboard/policy", response_class=HTMLResponse)
def update_policy_form(
    request: Request,
    session: Session = Depends(get_session),
    logging_level: str = Query("standard"),
    fw_gdpr: bool = Query(False),
    fw_ai_act: bool = Query(False),
    fw_soc2: bool = Query(False),
    blocking_enabled: bool = Query(False),
    block_on: str = Query("critical"),
):
    api_key = _get_first_api_key(session)
    if api_key is None:
        return HTMLResponse('<div class="flash flash-error">No API key configured</div>')

    org = session.query(Organization).filter(Organization.id == api_key.org_id).first()
    if org is None:
        return HTMLResponse('<div class="flash flash-error">Organization not found</div>')

    current = dict(org.policy)
    current["logging_level"] = logging_level
    current["frameworks"] = {"gdpr": fw_gdpr, "ai_act": fw_ai_act, "soc2": fw_soc2}
    current["blocking_rules"] = {"enabled": blocking_enabled, "block_on": block_on}

    org.policy = current
    org.updated_at = datetime.now(UTC)
    session.add(org)
    session.commit()

    return HTMLResponse('<div class="flash flash-success">Policy updated successfully</div>')


@router.get("/dashboard/stats", response_class=HTMLResponse)
def stats_page(
    request: Request,
    range: str = Query("7d"),
    session: Session = Depends(get_session),
):
    api_key = _get_first_api_key(session)
    if api_key is None:
        return HTMLResponse("<h1>No API key configured</h1>", status_code=500)

    after, before = _time_range_to_dates(range)
    stats = get_stats(session, api_key.id, after=after, before=before)

    # Top agents
    agents_q = (
        session.query(AuditEvent.agent_id, func.count())
        .filter(AuditEvent.api_key_id == api_key.id)
    )
    if after:
        agents_q = agents_q.filter(AuditEvent.created_at > after)
    if before:
        agents_q = agents_q.filter(AuditEvent.created_at < before)
    top_agents = (
        agents_q.group_by(AuditEvent.agent_id)
        .order_by(func.count().desc())
        .limit(5)
        .all()
    )

    # Top actions by risk (high/critical actions first)
    actions_q = (
        session.query(AuditEvent.action, func.count())
        .filter(
            AuditEvent.api_key_id == api_key.id,
            AuditEvent.risk_level.in_(["high", "critical"]),
        )
    )
    if after:
        actions_q = actions_q.filter(AuditEvent.created_at > after)
    if before:
        actions_q = actions_q.filter(AuditEvent.created_at < before)
    top_actions = (
        actions_q.group_by(AuditEvent.action)
        .order_by(func.count().desc())
        .limit(5)
        .all()
    )

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


@router.get("/dashboard/report/pdf")
def report_pdf(
    range: str = Query("7d"),
    session: Session = Depends(get_session),
):
    api_key = _get_first_api_key(session)
    if api_key is None:
        return Response("No API key configured", status_code=500)

    after, before = _time_range_to_dates(range)
    stats = get_stats(session, api_key.id, after=after, before=before)

    # Get high/critical events for the report
    high_events, _ = list_events(
        session,
        api_key.id,
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
        session, api_key.id, after=after, before=before, limit=1000, offset=0
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
