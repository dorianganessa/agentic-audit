# CrewAI Integration

!!! info "Roadmap"
    CrewAI integration is on the roadmap. In the meantime, you can use the [REST API](rest-api.md) to log events from any agent framework, including CrewAI.

## Using the REST API

You can integrate AgenticAudit with CrewAI today by calling the REST API directly from your tool callbacks:

```python
from agentaudit import AgentAudit

audit = AgentAudit(api_key="aa_live_xxxxx")

# Log events from your CrewAI tools
audit.log(
    agent_id="crewai-researcher",
    action="connector_access",
    data={"tool_name": "search_tool", "query": "customer data"},
)
```

A native CrewAI event hook integration is planned. Follow the [GitHub repo](https://github.com/dorianganessa/agentic-audit) for updates.

## Next steps

- [LangChain integration](langchain.md) — callback handler for LangChain
- [REST API](rest-api.md) — integrate any custom agent
- [Risk scoring](../concepts/risk-scoring.md) — how risk levels are determined
