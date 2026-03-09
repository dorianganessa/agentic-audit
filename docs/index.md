---
hide:
  - navigation
  - toc
---

# AgentAudit

**The missing audit layer for AI agents.**

Every action your AI agents take — logged, classified, and audit-ready. From Claude Code to Cowork.

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } __Get started in 5 minutes__

    ---

    Start AgentAudit with Docker Compose, log your first event, and see it classified.

    [:octicons-arrow-right-24: Quickstart](getting-started/quickstart.md)

-   :material-connection:{ .lg .middle } __Integrate with your agents__

    ---

    Claude Code hooks, Cowork plugin, LangChain callback, REST API — pick your path.

    [:octicons-arrow-right-24: Integrations](integrations/claude-code.md)

-   :material-shield-check:{ .lg .middle } __Understand the concepts__

    ---

    How PII detection, risk scoring, and compliance framework mapping work.

    [:octicons-arrow-right-24: Concepts](concepts/pii-detection.md)

-   :material-api:{ .lg .middle } __API Reference__

    ---

    Every endpoint documented. Request/response schemas, error codes, examples.

    [:octicons-arrow-right-24: API Reference](api-reference/events.md)

</div>

## What it does

Your agent does something → AgentAudit captures it → classifies risk and detects PII → maps to GDPR, AI Act, and SOC 2 articles. Automatically.

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
| **CrewAI** | :white_check_mark: Full | Event hook |
| **Codex** | :material-progress-clock: Partial | Transcript parsing |
| **Any agent** | :white_check_mark: Full | REST API / Python SDK |
