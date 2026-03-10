# LangChain Integration Guide

## Overview

AgenticAudit provides a LangChain callback handler that automatically logs tool calls, chain executions, and optionally LLM calls to the audit trail.

## Setup

```bash
pip install "agentaudit[langchain]"
# or
uv pip install "agentaudit[langchain]"
```

## Usage

```python
from agentaudit.integrations.langchain import AgentAuditCallbackHandler

handler = AgentAuditCallbackHandler(
    api_key="aa_live_your_key_here",
    base_url="http://localhost:8000",
    agent_id="my-langchain-agent",
    log_llm_calls=False,  # Set True to also log LLM invocations
)

# Use with any LangChain agent or chain
agent.invoke({"input": "..."}, config={"callbacks": [handler]})
```

## What Gets Logged

| LangChain Event    | AgenticAudit Action | When                        | Logged by Default |
|--------------------|-------------------|-----------------------------|-------------------|
| `on_tool_start`    | `tool_use`        | Tool is invoked             | Yes               |
| `on_tool_end`      | `tool_result`     | Tool returns output         | Yes               |
| `on_chain_start`   | `chain_start`     | Chain execution begins      | Yes               |
| `on_llm_start`     | `llm_call`        | LLM is invoked              | No (`log_llm_calls=True`) |

Tool outputs are truncated to 4,000 characters to avoid excessive payload sizes.

## Configuration

| Parameter       | Default              | Description                              |
|-----------------|----------------------|------------------------------------------|
| `api_key`       | `$AGENTAUDIT_API_KEY`| AgenticAudit API key                       |
| `base_url`      | `http://localhost:8000` | AgenticAudit API URL                    |
| `agent_id`      | `langchain-agent`    | Agent identifier in events               |
| `log_llm_calls` | `False`              | Whether to log LLM invocations           |

## Context Metadata

Each event includes:

```json
{
  "context": {
    "framework": "langchain",
    "run_id": "<langchain run uuid>"
  }
}
```

## Example: Agent with Tools

```python
from langchain.agents import create_react_agent
from langchain_openai import ChatOpenAI
from agentaudit.integrations.langchain import AgentAuditCallbackHandler

audit = AgentAuditCallbackHandler(api_key="aa_live_xxx", agent_id="research-agent")

llm = ChatOpenAI(model="gpt-4")
agent = create_react_agent(llm, tools=[...], prompt=...)

# Every tool call is automatically audited
agent.invoke({"input": "Find the latest sales data"}, config={"callbacks": [audit]})
```
