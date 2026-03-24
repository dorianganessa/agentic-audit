"""AgenticAudit MCP server — lets AI agents query their own audit trail."""

from __future__ import annotations

import os
from typing import Any

import httpx
from agentaudit import AgentAudit
from mcp.server.fastmcp import FastMCP

from agentaudit_mcp.risk_checker import check_risk

server = FastMCP("agentaudit")

_client: AgentAudit | None = None
_http: httpx.Client | None = None


def _get_client() -> AgentAudit:
    """Return the singleton AgentAudit client, creating it on first use."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = AgentAudit(
            api_key=os.environ.get("AGENTAUDIT_API_KEY", ""),
            base_url=os.environ.get("AGENTAUDIT_BASE_URL", "http://localhost:8000"),
        )
    return _client


def _get_http() -> httpx.Client:
    """Return a raw httpx client for endpoints not covered by the SDK."""
    global _http  # noqa: PLW0603
    if _http is None:
        base = os.environ.get("AGENTAUDIT_BASE_URL", "http://localhost:8000").rstrip("/")
        key = os.environ.get("AGENTAUDIT_API_KEY", "")
        _http = httpx.Client(
            base_url=base,
            headers={"Authorization": f"Bearer {key}"},
            timeout=30.0,
        )
    return _http


def _session_id() -> str | None:
    """Read the current session ID from the environment."""
    return os.environ.get("AGENTAUDIT_SESSION_ID")


@server.tool()
def get_my_audit_events(
    limit: int = 20,
    risk_level: str | None = None,
    action: str | None = None,
) -> dict[str, Any]:
    """Get recent audit events for this agent's session.

    Use this to review what actions you've taken and their risk levels.
    """
    client = _get_client()
    result = client.list_events(
        session_id=_session_id(),
        risk_level=risk_level,
        action=action,
        limit=limit,
    )
    return {
        "events": [
            {
                "id": e.id,
                "action": e.action,
                "risk_level": e.risk_level,
                "pii_detected": e.pii_detected,
                "created_at": str(e.created_at),
                "data": e.data,
                "decision": e.decision,
            }
            for e in result["events"]
        ],
        "total": result["total"],
    }


@server.tool()
def get_session_risk_summary() -> dict[str, Any]:
    """Get a summary of risk levels for the current session.

    Shows count of events by risk level and any PII detections.
    """
    client = _get_client()
    stats = client.get_stats()
    return {
        "total_events": stats["total_events"],
        "by_risk_level": stats["by_risk_level"],
        "pii_events": stats["pii_events"],
        "unique_agents": stats["unique_agents"],
    }


@server.tool()
def check_action_risk(
    action: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Check what risk level an action would be classified as, without logging it.

    Use this before taking a potentially risky action.
    """
    return check_risk(action, data)


@server.tool()
def list_ai_systems() -> dict[str, Any]:
    """List all AI systems registered for compliance tracking.

    Returns systems with their risk classification, FRIA status, and contract info.
    """
    resp = _get_http().get("/v1/systems")
    resp.raise_for_status()
    data = resp.json()
    return {
        "systems": [
            {
                "id": s["id"],
                "name": s["name"],
                "vendor": s["vendor"],
                "risk_classification": s["risk_classification"],
                "annex_iii_category": s["annex_iii_category"],
                "fria_status": s["fria_status"],
                "contract_has_ai_annex": s["contract_has_ai_annex"],
                "agent_id_patterns": s["agent_id_patterns"],
                "is_active": s["is_active"],
            }
            for s in data["systems"]
        ],
        "total": data["total"],
    }


@server.tool()
def get_compliance_status() -> dict[str, Any]:
    """Get the organization's AI Act compliance status.

    Returns a compliance score (0-100), individual check results,
    a summary of system counts, and upcoming deadlines.
    """
    resp = _get_http().get("/v1/compliance/ai-act/status")
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


@server.tool()
def suggest_classification(system_id: str) -> dict[str, Any]:
    """Suggest an AI Act risk classification for a system based on its event patterns.

    Analyzes the system's audit events and returns a suggested risk level
    (minimal, limited, high), Annex III category, rationale, and evidence.
    """
    resp = _get_http().get(f"/v1/systems/{system_id}/classification-suggestion")
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


def main() -> None:
    """Run the MCP server using stdio transport."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
