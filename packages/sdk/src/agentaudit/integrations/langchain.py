"""LangChain callback handler that logs agent actions to AgenticAudit."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from agentaudit.client import AgentAudit

logger = logging.getLogger(__name__)


class AgentAuditCallbackHandler(BaseCallbackHandler):
    """LangChain callback that logs agent actions to AgenticAudit.

    Usage::

        from agentaudit.integrations.langchain import AgentAuditCallbackHandler

        handler = AgentAuditCallbackHandler(api_key="aa_live_xxx")
        agent.run("do something", callbacks=[handler])
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "http://localhost:8000",
        agent_id: str = "langchain-agent",
        log_llm_calls: bool = False,
    ) -> None:
        super().__init__()
        self.audit = AgentAudit(api_key=api_key, base_url=base_url)
        self.agent_id = agent_id
        self.log_llm_calls = log_llm_calls
        self._run_to_tool: dict[UUID, str] = {}

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Log tool invocation to AgenticAudit."""
        tool_name = serialized.get("name", "unknown_tool")
        self._run_to_tool[run_id] = tool_name
        try:
            self.audit.log(
                agent_id=self.agent_id,
                action="tool_start",
                data={"tool_name": tool_name, "input": input_str},
                context={"run_id": str(run_id), "framework": "langchain"},
            )
        except Exception:
            logger.exception("Failed to log tool_start to AgenticAudit")

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Log tool result to AgenticAudit."""
        tool_name = self._run_to_tool.pop(run_id, "unknown_tool")
        try:
            output_str = str(output)
            if len(output_str) > 4000:
                output_str = output_str[:4000] + "... [truncated]"
            self.audit.log(
                agent_id=self.agent_id,
                action="tool_end",
                data={"tool_name": tool_name, "output": output_str},
                context={"run_id": str(run_id), "framework": "langchain"},
            )
        except Exception:
            logger.exception("Failed to log tool_end to AgenticAudit")

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Log chain start to AgenticAudit."""
        chain_name = serialized.get("name", serialized.get("id", ["unknown"])[-1])
        try:
            self.audit.log(
                agent_id=self.agent_id,
                action="chain_start",
                data={"chain_name": str(chain_name), "inputs": _safe_serialize(inputs)},
                context={"run_id": str(run_id), "framework": "langchain"},
            )
        except Exception:
            logger.exception("Failed to log chain_start to AgenticAudit")

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Log LLM call (disabled by default — too noisy)."""
        if not self.log_llm_calls:
            return
        model_name = serialized.get("name", "unknown_model")
        try:
            self.audit.log(
                agent_id=self.agent_id,
                action="llm_call",
                data={"model": str(model_name), "prompt_count": len(prompts)},
                context={"run_id": str(run_id), "framework": "langchain"},
            )
        except Exception:
            logger.exception("Failed to log llm_call to AgenticAudit")


def _safe_serialize(obj: Any, max_len: int = 2000) -> dict[str, str]:
    """Safely serialize inputs, truncating large values."""
    if not isinstance(obj, dict):
        s = str(obj)
        return {"value": s[:max_len] + "..." if len(s) > max_len else s}
    result: dict[str, str] = {}
    for k, v in obj.items():
        s = str(v)
        result[str(k)] = s[:max_len] + "..." if len(s) > max_len else s
    return result
