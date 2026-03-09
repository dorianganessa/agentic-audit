# Framework Mapping

AgentAudit automatically maps each event to relevant articles from compliance frameworks: **GDPR**, **EU AI Act**, and **SOC 2**. Mapping is based on the event's action, risk level, PII detection, and context.

## How it works

After PII detection and risk scoring, the framework mapper evaluates a set of conditions for each enabled framework. Matching articles are attached to the event's `frameworks` field.

Frameworks can be enabled/disabled per organization via the [policy system](policy-system.md).

## GDPR mapping

| Condition | Article | Title |
|---|---|---|
| PII detected | **Art. 30** | Records of processing activities |
| Access action + PII | **Art. 15** | Right of access by the data subject |
| Delete action + PII | **Art. 17** | Right to erasure ("right to be forgotten") |
| Reasoning provided | **Art. 22** | Automated individual decision-making |
| PII + developer context | **Art. 13** | Information to be provided to the data subject |

### When GDPR articles trigger

- **Art. 30** fires on any event with PII — the act of processing personal data must be recorded.
- **Art. 15** fires when the action involves accessing personal data (e.g., reading a customer record).
- **Art. 17** fires when the action involves deleting personal data.
- **Art. 22** fires when the agent provides reasoning — indicating automated decision-making about individuals.
- **Art. 13** fires when PII is processed in a developer context — transparency obligations about how data is handled.

## EU AI Act mapping

| Condition | Article | Title |
|---|---|---|
| Agent ID present | **Art. 14** | Human oversight |
| High or critical risk | **Art. 9** | Risk management system |
| Reasoning provided | **Art. 13** | Transparency and provision of information |

### When AI Act articles trigger

- **Art. 14** fires on any event with an `agent_id` — the AI system must have human oversight mechanisms.
- **Art. 9** fires on high/critical risk events — high-risk AI systems require documented risk management.
- **Art. 13** fires when reasoning is provided — AI systems must be transparent about their decision-making.

## SOC 2 mapping

| Condition | Control | Title |
|---|---|---|
| Shell command or file write | **CC6.1** | Logical and physical access controls |
| Critical risk event | **CC7.2** | System monitoring and incident management |
| PII detected | **CC6.5** | Data classification and protection |

### When SOC 2 controls trigger

- **CC6.1** fires on actions that modify or execute on the system — access must be controlled and logged.
- **CC7.2** fires on critical events — incidents must be detected and managed.
- **CC6.5** fires on PII events — data must be classified and protected appropriately.

## Example event with frameworks

```json
{
  "action": "database_query",
  "data": {"query": "SELECT email FROM customers"},
  "risk_level": "medium",
  "pii_detected": true,
  "frameworks": {
    "gdpr": ["art_30", "art_15"],
    "ai_act": ["art_14"],
    "soc2": ["cc6_5"]
  }
}
```

## Enabling/disabling frameworks

By default, GDPR and AI Act are enabled. SOC 2 is disabled. Configure via the policy API:

```bash
curl -X PUT http://localhost:8000/v1/org/policy \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "frameworks": {
      "gdpr": true,
      "ai_act": true,
      "soc2": true
    }
  }'
```

Or toggle in the dashboard under **Policy > Frameworks**.

## Next steps

- [PII detection](pii-detection.md) — how PII is detected
- [Risk scoring](risk-scoring.md) — how risk levels are assigned
- [Policy system](policy-system.md) — enable/disable frameworks per organization
