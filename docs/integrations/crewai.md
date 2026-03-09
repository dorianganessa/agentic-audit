# CrewAI Integration

AgentAudit integrates with CrewAI via event hooks, capturing every tool call and agent action across your crew.

## Installation

```bash
pip install agentic-audit
```

## Setup

Register the AgentAudit event hook with your CrewAI crew:

```python
from crewai import Crew, Agent, Task
from agentaudit.integrations.crewai import AgentAuditEventHook

audit_hook = AgentAuditEventHook(
    api_key="aa_live_xxxxx",
    base_url="http://localhost:8000",
)

crew = Crew(
    agents=[...],
    tasks=[...],
    event_hooks=[audit_hook],
)

result = crew.kickoff()
```

## What gets captured

| CrewAI Event | AgentAudit Action | Data |
|---|---|---|
| Tool execution | Tool name | Tool input, agent name |
| Agent delegation | `agent_delegation` | From agent, to agent, task |
| Task start | `task_start` | Task description, assigned agent |
| Task end | `task_end` | Task output, status |

Each event is processed through the standard AgentAudit pipeline — PII detection, risk scoring, and framework mapping happen automatically.

## Multi-agent visibility

CrewAI crews involve multiple agents collaborating. AgentAudit tags each event with the originating `agent_id`, so you can:

- Track which agent accessed what data
- See delegation chains in the dashboard timeline
- Filter events by specific agent within a crew

## Example: research crew with compliance

```python
researcher = Agent(
    role="Researcher",
    goal="Find customer information",
    tools=[search_tool, database_tool],
)

writer = Agent(
    role="Writer",
    goal="Draft customer report",
    tools=[file_tool],
)

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    event_hooks=[audit_hook],
)

# Every tool call by every agent is audited
crew.kickoff()
```

## Next steps

- [LangChain integration](langchain.md) — callback handler for LangChain
- [REST API](rest-api.md) — integrate any custom agent
- [Risk scoring](../concepts/risk-scoring.md) — how risk levels are determined
