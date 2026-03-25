"""CrewAI callback handler that logs agent actions to AgenticAudit."""

from __future__ import annotations

import logging

from crewai.utilities.events import (
    AgentExecutionCompletedEvent,
    AgentExecutionStartedEvent,
    ToolUsageFinishedEvent,
    ToolUsageStartedEvent,
)
from crewai.utilities.events.base_event_listener import BaseEventListener

from agentaudit.client import AgentAudit

logger = logging.getLogger(__name__)


class AgentAuditEventListener(BaseEventListener):  # type: ignore[misc]
    """CrewAI event listener that logs agent actions to AgenticAudit.

    Usage::

        from agentaudit.integrations.crewai import AgentAuditEventListener

        listener = AgentAuditEventListener(api_key="aa_live_xxx")
        # The listener is automatically registered with CrewAI's event system.
        crew.kickoff()
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "http://localhost:8000",
        agent_id: str = "crewai-agent",
    ) -> None:
        super().__init__()
        self.audit = AgentAudit(api_key=api_key, base_url=base_url)
        self.agent_id = agent_id

    def on_agent_execution_started(self, event: AgentExecutionStartedEvent) -> None:
        """Log when a CrewAI agent starts executing."""
        try:
            agent_role = getattr(event.agent, "role", "unknown")
            self.audit.log(
                agent_id=self.agent_id,
                action="agent_execution_started",
                data={"agent_role": str(agent_role)},
                context={"framework": "crewai"},
            )
        except Exception:
            logger.exception("Failed to log agent_execution_started to AgenticAudit")

    def on_agent_execution_completed(self, event: AgentExecutionCompletedEvent) -> None:
        """Log when a CrewAI agent completes execution."""
        try:
            agent_role = getattr(event.agent, "role", "unknown")
            output = str(getattr(event, "output", ""))
            if len(output) > 4000:
                output = output[:4000] + "... [truncated]"
            self.audit.log(
                agent_id=self.agent_id,
                action="agent_execution_completed",
                data={"agent_role": str(agent_role), "output": output},
                context={"framework": "crewai"},
            )
        except Exception:
            logger.exception("Failed to log agent_execution_completed to AgenticAudit")

    def on_tool_usage_started(self, event: ToolUsageStartedEvent) -> None:
        """Log when a CrewAI agent starts using a tool."""
        try:
            tool_name = getattr(event, "tool_name", "unknown_tool")
            tool_input = str(getattr(event, "tool_input", ""))
            if len(tool_input) > 4000:
                tool_input = tool_input[:4000] + "... [truncated]"
            self.audit.log(
                agent_id=self.agent_id,
                action="tool_start",
                data={"tool_name": str(tool_name), "input": tool_input},
                context={"framework": "crewai"},
            )
        except Exception:
            logger.exception("Failed to log tool_start to AgenticAudit")

    def on_tool_usage_finished(self, event: ToolUsageFinishedEvent) -> None:
        """Log when a CrewAI tool completes."""
        try:
            tool_name = getattr(event, "tool_name", "unknown_tool")
            output = str(getattr(event, "output", ""))
            if len(output) > 4000:
                output = output[:4000] + "... [truncated]"
            self.audit.log(
                agent_id=self.agent_id,
                action="tool_end",
                data={"tool_name": str(tool_name), "output": output},
                context={"framework": "crewai"},
            )
        except Exception:
            logger.exception("Failed to log tool_end to AgenticAudit")
