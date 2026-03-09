from __future__ import annotations

import os

import httpx

from agentaudit.exceptions import AgentAuditError, AuthenticationError, ValidationError
from agentaudit.models import AuditEvent

DEFAULT_BASE_URL = "http://localhost:8000"


def _handle_error_response(response: httpx.Response) -> None:
    """Raise appropriate exception based on HTTP status code."""
    if response.status_code == 401 or response.status_code == 403:
        raise AuthenticationError(
            message=response.json().get("detail", "Authentication failed"),
            status_code=response.status_code,
        )
    if response.status_code == 422:
        detail = response.json().get("detail", "Validation error")
        raise ValidationError(
            message=str(detail),
            status_code=response.status_code,
        )
    if response.status_code >= 400:
        raise AgentAuditError(
            message=response.json().get("detail", f"HTTP {response.status_code}"),
            status_code=response.status_code,
        )


class AgentAudit:
    """Synchronous AgentAudit client."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 10.0,
    ):
        self._api_key = api_key or os.environ.get("AGENTAUDIT_API_KEY", "")
        self._base_url = (
            base_url or os.environ.get("AGENTAUDIT_BASE_URL", DEFAULT_BASE_URL)
        ).rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=timeout,
        )

    def log(
        self,
        agent_id: str,
        action: str,
        data: dict | None = None,
        context: dict | None = None,
        reasoning: str | None = None,
    ) -> AuditEvent:
        """Log an audit event."""
        payload: dict = {
            "agent_id": agent_id,
            "action": action,
        }
        if data is not None:
            payload["data"] = data
        if context is not None:
            payload["context"] = context
        if reasoning is not None:
            payload["reasoning"] = reasoning

        response = self._client.post("/v1/events", json=payload)
        _handle_error_response(response)
        return AuditEvent.from_api_response(response.json())

    def list_events(
        self,
        *,
        agent_id: str | None = None,
        action: str | None = None,
        risk_level: str | None = None,
        pii_detected: bool | None = None,
        session_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List events with optional filters. Returns {events, total, limit, offset}."""
        params: dict = {"limit": limit, "offset": offset}
        if agent_id is not None:
            params["agent_id"] = agent_id
        if action is not None:
            params["action"] = action
        if risk_level is not None:
            params["risk_level"] = risk_level
        if pii_detected is not None:
            params["pii_detected"] = str(pii_detected).lower()
        if session_id is not None:
            params["session_id"] = session_id

        response = self._client.get("/v1/events", params=params)
        _handle_error_response(response)
        data = response.json()
        data["events"] = [AuditEvent.from_api_response(e) for e in data["events"]]
        return data

    def get_stats(self) -> dict:
        """Get aggregate statistics."""
        response = self._client.get("/v1/events/stats")
        _handle_error_response(response)
        return response.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AgentAudit:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class AsyncAgentAudit:
    """Asynchronous AgentAudit client."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 10.0,
    ):
        self._api_key = api_key or os.environ.get("AGENTAUDIT_API_KEY", "")
        self._base_url = (
            base_url or os.environ.get("AGENTAUDIT_BASE_URL", DEFAULT_BASE_URL)
        ).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=timeout,
        )

    async def log(
        self,
        agent_id: str,
        action: str,
        data: dict | None = None,
        context: dict | None = None,
        reasoning: str | None = None,
    ) -> AuditEvent:
        """Log an audit event."""
        payload: dict = {
            "agent_id": agent_id,
            "action": action,
        }
        if data is not None:
            payload["data"] = data
        if context is not None:
            payload["context"] = context
        if reasoning is not None:
            payload["reasoning"] = reasoning

        response = await self._client.post("/v1/events", json=payload)
        _handle_error_response(response)
        return AuditEvent.from_api_response(response.json())

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AsyncAgentAudit:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
