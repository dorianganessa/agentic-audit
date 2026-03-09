from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class AuditEvent:
    """Represents an audit event returned by the API."""

    id: str
    agent_id: str
    action: str
    data: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    reasoning: str | None = None
    risk_level: str | None = None
    pii_detected: bool = False
    pii_fields: list[str] = field(default_factory=list)
    frameworks: dict = field(default_factory=dict)
    created_at: datetime | None = None
    stored: bool = True
    decision: str = "allow"
    reason: str | None = None

    @classmethod
    def from_api_response(cls, data: dict) -> AuditEvent:
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            id=data["id"],
            agent_id=data["agent_id"],
            action=data["action"],
            data=data.get("data", {}),
            context=data.get("context", {}),
            reasoning=data.get("reasoning"),
            risk_level=data.get("risk_level"),
            pii_detected=data.get("pii_detected", False),
            pii_fields=data.get("pii_fields", []),
            frameworks=data.get("frameworks", {}),
            created_at=created_at,
            stored=data.get("stored", True),
            decision=data.get("decision", "allow"),
            reason=data.get("reason"),
        )
