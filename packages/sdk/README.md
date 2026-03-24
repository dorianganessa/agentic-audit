# AgenticAudit

Python SDK for [AgenticAudit](https://agentaudit.dev) — open-source compliance monitoring for AI agents.

Log every AI agent action, auto-detect PII, score risk, and map to GDPR / AI Act / SOC 2.

## Install

```bash
pip install agentic-audit
```

## Quick start

```python
from agentaudit import AgentAudit

audit = AgentAudit(api_key="aa_live_xxxxx")

event = audit.log(
    agent_id="booking-agent-v2",
    action="access_customer_record",
    data={"customer_email": "maria@example.com"},
)

print(event.risk_level)   # "medium"
print(event.pii_detected) # True
print(event.frameworks)   # {"gdpr": ["art_30"], "ai_act": ["art_14"]}
```

## Async support

```python
from agentaudit import AsyncAgentAudit

async with AsyncAgentAudit(api_key="aa_live_xxxxx") as audit:
    event = await audit.log(
        agent_id="my-agent",
        action="database_query",
        data={"query": "SELECT * FROM users"},
    )
```

## Integrations

- **Claude Code** — zero-overhead deterministic hooks via [`agentic-audit-hook`](https://pypi.org/project/agentic-audit-hook/)
- **Cowork** — plugin with automatic hook registration
- **LangChain** — `pip install agentic-audit[langchain]` for callback handler
- **CrewAI** — event hook for multi-agent crews
- **Any agent** — REST API / this SDK

## Links

- [Documentation](https://docs.agentaudit.dev)
- [GitHub](https://github.com/dorianganessa/agentic-audit)
- [Quickstart](https://docs.agentaudit.dev/getting-started/quickstart/)

## License

Apache 2.0
