"""Exception hierarchy for the AgentAudit SDK."""

from __future__ import annotations


class AgentAuditError(Exception):
    """Base exception for AgentAudit SDK errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthenticationError(AgentAuditError):
    """Raised when the API key is invalid or missing."""


class ValidationError(AgentAuditError):
    """Raised when the request payload is invalid."""


class ConnectionError(AgentAuditError):
    """Raised when the API server is unreachable."""


class ServerError(AgentAuditError):
    """Raised when the API returns a 5xx error."""
