"""AI Act compliance API: status, reports, FRIA generation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from agentaudit_api.api.deps import get_org
from agentaudit_api.auth.api_key import get_current_api_key
from agentaudit_api.config import get_settings
from agentaudit_api.database import get_session
from agentaudit_api.models.ai_system import AISystem
from agentaudit_api.models.api_key import ApiKey
from agentaudit_api.models.event import AuditEvent
from agentaudit_api.services.compliance_report_pdf import generate_compliance_report
from agentaudit_api.services.fria_pdf import generate_fria_pdf
from agentaudit_api.services.system_service import (
    get_system,
    get_system_event_stats,
    list_systems,
)

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get(
    "/ai-act/status",
    summary="AI Act compliance status",
)
def compliance_status(
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get overall AI Act compliance status for the organization."""
    org = get_org(session, api_key)
    systems = list_systems(session, org.id)
    policy = dict(org.policy)
    settings = get_settings()
    retention = policy.get("retention_days", settings.retention_days)

    total_systems = len(systems)
    classified = sum(
        1 for s in systems if s.risk_classification != "unclassified"
    )
    high_risk = [s for s in systems if s.risk_classification == "high"]
    fria_completed = sum(1 for s in high_risk if s.fria_status == "completed")
    contracts_ok = sum(1 for s in systems if s.contract_has_ai_annex)
    prohibited = [s for s in systems if s.risk_classification == "prohibited"]

    # Compute score
    checks = {
        "all_classified": total_systems > 0 and classified == total_systems,
        "no_prohibited": len(prohibited) == 0,
        "fria_complete": (
            len(high_risk) == 0 or fria_completed == len(high_risk)
        ),
        "contracts_reviewed": (
            total_systems == 0 or contracts_ok == total_systems
        ),
        "retention_compliant": retention >= 180,
    }
    score = int(sum(checks.values()) / len(checks) * 100) if checks else 0

    return {
        "score": score,
        "checks": checks,
        "summary": {
            "total_systems": total_systems,
            "classified": classified,
            "high_risk": len(high_risk),
            "fria_completed": fria_completed,
            "contracts_with_annex": contracts_ok,
            "prohibited_systems": len(prohibited),
            "retention_days": retention,
            "retention_compliant": retention >= 180,
        },
        "compliance_preset": policy.get("compliance_preset"),
        "deadlines": _get_deadlines(systems),
    }


@router.get(
    "/ai-act/report",
    summary="Download AI Act compliance report PDF",
)
def compliance_report_pdf(
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> Response:
    """Generate and download an AI Act compliance report."""
    org = get_org(session, api_key)
    systems = list_systems(session, org.id)
    policy = dict(org.policy)
    settings = get_settings()
    retention = policy.get("retention_days", settings.retention_days)

    # Per-system stats
    sys_stats: dict[str, dict[str, Any]] = {}
    for s in systems:
        sys_stats[s.id] = get_system_event_stats(session, s, api_key.id)

    # Oldest event
    oldest = (
        session.query(AuditEvent.created_at)
        .filter(AuditEvent.api_key_id == api_key.id)  # type: ignore[arg-type]
        .order_by(AuditEvent.created_at.asc())  # type: ignore[attr-defined]
        .first()
    )
    oldest_date = oldest[0] if oldest else None

    total_events = (
        session.query(AuditEvent)
        .filter(AuditEvent.api_key_id == api_key.id)  # type: ignore[arg-type]
        .count()
    )

    pdf_bytes = generate_compliance_report(
        systems=systems,
        system_stats=sys_stats,
        policy=policy,
        retention_days=retention,
        oldest_event_date=oldest_date,
        total_events=total_events,
    )

    filename = f"ai_act_compliance_{datetime.now(UTC).strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/ai-act/fria/{system_id}/pdf",
    summary="Download FRIA PDF for a system",
)
def fria_pdf(
    system_id: str,
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> Response:
    """Generate a pre-filled FRIA PDF for a specific AI system."""
    org = get_org(session, api_key)
    system = get_system(session, system_id, org.id)
    if system is None:
        raise HTTPException(404, "System not found")

    stats = get_system_event_stats(session, system, api_key.id)
    policy = dict(org.policy)

    pdf_bytes = generate_fria_pdf(
        system=system,
        stats=stats,
        policy=policy,
    )

    safe_name = system.name.replace(" ", "_").lower()[:30]
    filename = f"fria_{safe_name}_{datetime.now(UTC).strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _get_deadlines(systems: list[AISystem]) -> list[dict[str, Any]]:
    """Collect upcoming deadlines from systems."""
    deadlines: list[dict[str, Any]] = []
    now = datetime.now(UTC).replace(tzinfo=None)
    for s in systems:
        if s.next_review_date and s.next_review_date > now:
            deadlines.append({
                "system": s.name,
                "type": "system_review",
                "date": s.next_review_date.isoformat(),
            })
        if s.fria_next_review and s.fria_next_review > now:
            deadlines.append({
                "system": s.name,
                "type": "fria_review",
                "date": s.fria_next_review.isoformat(),
            })
    deadlines.sort(key=lambda d: d["date"])
    return deadlines
