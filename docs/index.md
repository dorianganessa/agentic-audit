---
hide:
  - navigation
  - toc
---

# Security for AI agents

**Know what your AI agents are doing. Prove it to auditors.**

Your AI agents access customer data, modify production systems, and make autonomous decisions — with zero paper trail. The EU AI Act is in force. Regulators are asking. AgenticAudit is the answer.

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } __Up and running in 5 minutes__

    ---

    One `docker compose up`, log your first event, see it classified and mapped to compliance frameworks.

    [:octicons-arrow-right-24: Quickstart](getting-started/quickstart.md)

-   :material-connection:{ .lg .middle } __Works with your agents__

    ---

    Claude Code, LangChain, Codex, Cowork — or any agent via the Python SDK and REST API.

    [:octicons-arrow-right-24: Integrations](integrations/claude-code.md)

-   :material-shield-check:{ .lg .middle } __Compliance out of the box__

    ---

    Every action automatically maps to GDPR, EU AI Act, and SOC 2 articles. Generate audit-ready PDF reports.

    [:octicons-arrow-right-24: Concepts](concepts/pii-detection.md)

-   :material-api:{ .lg .middle } __API Reference__

    ---

    Every endpoint documented. Request/response schemas, error codes, examples.

    [:octicons-arrow-right-24: API Reference](api-reference/events.md)

</div>

## How it works

Your agent does something. AgenticAudit captures it, classifies the risk, detects personal data, and maps it to the compliance articles that matter. Automatically.

```python
from agentaudit import AgentAudit

audit = AgentAudit(api_key="aa_live_xxxxx")

event = audit.log(
    agent_id="booking-agent-v2",
    action="access_customer_record",
    data={"customer_email": "maria@example.com"},
    reasoning="Customer requested booking modification",
)

print(event.risk_level)   # "medium"
print(event.pii_detected) # True
print(event.frameworks)   # {"gdpr": ["art_30"], "ai_act": ["art_14"]}
```

## Works with

| Agent | Support | Method |
|---|---|---|
| **Claude Code** | :white_check_mark: Full | Deterministic hooks, enterprise-enforceable |
| **Cowork** | :white_check_mark: Full | Plugin with hooks, marketplace deployment |
| **LangChain** | :white_check_mark: Full | Callback handler |
| **CrewAI** | :material-progress-clock: Roadmap | Event hook (planned) |
| **Codex** | :material-progress-clock: Partial | Transcript parsing |
| **Any agent** | :white_check_mark: Full | REST API / Python SDK |
