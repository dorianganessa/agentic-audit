"""Synchronous and asynchronous HTTP clients for the AgentAudit API."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from agentaudit.exceptions import (
    AgentAuditError,
    AuthenticationError,
    ConnectionError,
    ServerError,
    ValidationError,
)
from agentaudit.models import AuditEvent

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8000"


def _handle_error_response(response: httpx.Response) -> None:
    """Raise appropriate exception based on HTTP status code.

    Args:
        response: The HTTP response to check.

    Raises:
        AuthenticationError: For 401/403 responses.
        ValidationError: For 422 responses.
        ServerError: For 5xx responses.
        AgentAuditError: For other 4xx responses.
    """
    if response.status_code in (401, 403):
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
    if response.status_code >= 500:
        raise ServerError(
            message=response.json().get("detail", f"Server error: HTTP {response.status_code}"),
            status_code=response.status_code,
        )
    if response.status_code >= 400:
        raise AgentAuditError(
            message=response.json().get("detail", f"HTTP {response.status_code}"),
            status_code=response.status_code,
        )


class AgentAudit:
    """Synchronous AgentAudit client.

    Usage::

        with AgentAudit(api_key="aa_live_xxx") as audit:
            event = audit.log(agent_id="my-agent", action="shell_command", data={"command": "ls"})
            print(event.risk_level)
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
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
        data: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        reasoning: str | None = None,
    ) -> AuditEvent:
        """Log an audit event.

        Args:
            agent_id: Identifier for the agent.
            action: The type of action (e.g., shell_command, file_read).
            data: Action-specific payload.
            context: Optional environment metadata.
            reasoning: Optional explanation for the action.

        Returns:
            The created AuditEvent with risk_level and PII populated.

        Raises:
            ConnectionError: If the API server is unreachable.
            AuthenticationError: If the API key is invalid.
        """
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "action": action,
        }
        if data is not None:
            payload["data"] = data
        if context is not None:
            payload["context"] = context
        if reasoning is not None:
            payload["reasoning"] = reasoning

        try:
            response = self._client.post("/v1/events", json=payload)
        except httpx.ConnectError as exc:
            raise ConnectionError(message=f"Cannot connect to {self._base_url}: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise ConnectionError(message=f"Request timed out: {exc}") from exc

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
    ) -> dict[str, Any]:
        """List events with optional filters.

        Returns:
            Dictionary with events, total, limit, and offset keys.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
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
        result: dict[str, Any] = response.json()
        result["events"] = [AuditEvent.from_api_response(e) for e in result["events"]]
        return result

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics."""
        response = self._client.get("/v1/events/stats")
        _handle_error_response(response)
        return response.json()  # type: ignore[no-any-return]

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> AgentAudit:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class AsyncAgentAudit:
    """Asynchronous AgentAudit client.

    Usage::

        async with AsyncAgentAudit(api_key="aa_live_xxx") as audit:
            event = await audit.log(agent_id="my-agent", action="shell_command")
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
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
        data: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        reasoning: str | None = None,
    ) -> AuditEvent:
        """Log an audit event asynchronously.

        Args:
            agent_id: Identifier for the agent.
            action: The type of action.
            data: Action-specific payload.
            context: Optional environment metadata.
            reasoning: Optional explanation for the action.
        """
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "action": action,
        }
        if data is not None:
            payload["data"] = data
        if context is not None:
            payload["context"] = context
        if reasoning is not None:
            payload["reasoning"] = reasoning

        try:
            response = await self._client.post("/v1/events", json=payload)
        except httpx.ConnectError as exc:
            raise ConnectionError(message=f"Cannot connect to {self._base_url}: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise ConnectionError(message=f"Request timed out: {exc}") from exc

        _handle_error_response(response)
        return AuditEvent.from_api_response(response.json())

    async def close(self) -> None:
        """Close the underlying async HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncAgentAudit:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
