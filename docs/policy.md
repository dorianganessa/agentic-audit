# Policy Configuration Guide

## Overview

AgentAudit's policy engine controls what gets logged, which compliance frameworks are evaluated, and whether high-risk actions are blocked. Each organization has one policy, configurable via the API or dashboard.

## Default Policy

```json
{
  "logging_level": "standard",
  "frameworks": {
    "gdpr": true,
    "ai_act": true,
    "soc2": false
  },
  "alert_rules": [],
  "blocking_rules": {
    "enabled": false,
    "block_on": "critical"
  }
}
```

## Logging Levels

| Level      | What gets stored                        | Use case                          |
|------------|-----------------------------------------|-----------------------------------|
| `minimal`  | Only events with PII detected           | Low-overhead compliance scanning  |
| `standard` | Medium+ risk events, or events with PII | Default — balanced coverage       |
| `full`     | All events                              | Full audit trail                  |
| `paranoid` | All events + blocking enabled           | High-security environments        |

## Compliance Frameworks

Enable or disable framework mapping per organization:

- **GDPR** — Maps events to Articles 13, 15, 17, 22, 30
- **EU AI Act** — Maps events to Articles 9, 13, 14
- **SOC 2** — Maps events to CC6.1, CC6.5, CC7.2

### GDPR Mapping Rules

| Condition                        | Article | Description                  |
|----------------------------------|---------|------------------------------|
| PII detected                     | Art. 30 | Records of processing        |
| Access action + PII              | Art. 15 | Right of access              |
| Delete action + PII              | Art. 17 | Right to erasure             |
| Reasoning provided               | Art. 22 | Automated decision-making    |
| PII + developer context          | Art. 13 | Information to data subject  |

### EU AI Act Mapping Rules

| Condition                        | Article | Description                  |
|----------------------------------|---------|------------------------------|
| Agent ID present                 | Art. 14 | Human oversight              |
| High/critical risk               | Art. 9  | Risk management              |
| Reasoning provided               | Art. 13 | Transparency                 |

### SOC 2 Mapping Rules

| Condition                        | Control | Description                  |
|----------------------------------|---------|------------------------------|
| Shell command or file write      | CC6.1   | Logical access               |
| Critical risk                    | CC7.2   | Incident management          |
| PII detected                    | CC6.5   | Data classification          |

## Blocking Rules

Blocking only works in `paranoid` logging level. When enabled, the PreToolUse hook will reject actions that meet or exceed the configured risk threshold.

```json
{
  "logging_level": "paranoid",
  "blocking_rules": {
    "enabled": true,
    "block_on": "high"
  }
}
```

Risk levels in order: `low` < `medium` < `high` < `critical`.

Setting `block_on: "high"` blocks both `high` and `critical` actions.

## Alert Rules

Configure Slack webhook alerts for specific conditions:

```json
{
  "alert_rules": [
    {
      "name": "Critical action alert",
      "condition": {"risk_level": "critical"},
      "notify": {"slack_webhook": "https://hooks.slack.com/services/T.../B.../xxx"}
    }
  ]
}
```

## Managing Policy

### Via API

```bash
# Get current policy
curl -s http://localhost:8000/v1/org/policy \
  -H "Authorization: Bearer $AA_KEY" | jq .

# Update policy
curl -s -X PUT http://localhost:8000/v1/org/policy \
  -H "Authorization: Bearer $AA_KEY" \
  -H "Content-Type: application/json" \
  -d '{"logging_level": "full", "frameworks": {"gdpr": true, "ai_act": true, "soc2": true}}'
```

### Via Dashboard

Navigate to `http://localhost:8000/dashboard/policy` to manage settings through the web UI.
