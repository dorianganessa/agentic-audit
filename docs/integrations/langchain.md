# LangChain Integration

AgenticAudit provides a LangChain callback handler that logs tool calls, chain starts, and agent actions as audit events.

## Installation

```bash
pip install agentic-audit
```

## Setup

```python
from agentaudit.integrations.langchain import AgentAuditCallbackHandler

handler = AgentAuditCallbackHandler(
    api_key="aa_live_xxxxx",
    base_url="http://localhost:8000",
)
```

## Usage

Pass the handler as a callback to any LangChain agent, chain, or tool:

```python
from langchain.agents import AgentExecutor

agent = AgentExecutor(agent=..., tools=..., callbacks=[handler])
result = agent.invoke({"input": "Find customer orders for user@example.com"})
```

## What gets captured

| LangChain Event | AgenticAudit Action | Data |
|---|---|---|
| `on_tool_start` | Tool name (e.g., `sql_query`) | Tool input |
| `on_tool_end` | Tool name + `_result` | Tool output |
| `on_chain_start` | `chain_start` | Chain name, inputs |

Each event goes through the full AgenticAudit pipeline: PII detection, risk scoring, and framework mapping.

## Example: SQL agent with audit trail

```python
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from agentaudit.integrations.langchain import AgentAuditCallbackHandler

audit_handler = AgentAuditCallbackHandler(api_key="aa_live_xxxxx")

llm = ChatOpenAI(model="gpt-4o")
toolkit = SQLDatabaseToolkit(db=db, llm=llm)

agent = create_sql_agent(
    llm=llm,
    toolkit=toolkit,
    callbacks=[audit_handler],
)

# Every SQL query is logged and classified
agent.invoke({"input": "How many customers are in New York?"})
```

## Async support

The callback handler supports async LangChain chains:

```python
result = await agent.ainvoke(
    {"input": "Find customer orders"},
    callbacks=[handler],
)
```

## Next steps

- [CrewAI integration](crewai.md) — event hooks for CrewAI
- [REST API](rest-api.md) — integrate any custom agent
- [PII detection](../concepts/pii-detection.md) — how PII is found in tool inputs/outputs
