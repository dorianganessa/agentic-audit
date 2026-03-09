"""AgentAudit MCP server — lets AI agents query their own audit trail."""

from __future__ import annotations

import os
from typing import Any

from agentaudit import AgentAudit
from mcp.server.fastmcp import FastMCP

from agentaudit_mcp.risk_checker import check_risk

server = FastMCP("agentaudit")

_client: AgentAudit | None = None


def _get_client() -> AgentAudit:
    """Return the singleton AgentAudit client, creating it on first use."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = AgentAudit(
            api_key=os.environ.get("AGENTAUDIT_API_KEY", ""),
            base_url=os.environ.get("AGENTAUDIT_BASE_URL", "http://localhost:8000"),
        )
    return _client


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


def main() -> None:
    """Run the MCP server using stdio transport."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
