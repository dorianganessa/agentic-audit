# Policy System

The policy system controls what AgentAudit logs, stores, alerts on, and blocks. Each organization has one policy, configurable via the API or dashboard.

## Default policy

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

## Logging levels

The logging level determines which events are persisted to the database.

| Level | What gets stored | Use case |
|---|---|---|
| `minimal` | Only events with PII detected | Low-overhead scanning, PII monitoring only |
| `standard` | Events with risk `medium`+ OR PII detected | **Default.** Balanced — captures important events without noise |
| `full` | All events regardless of risk | Complete audit trail for high-compliance environments |
| `paranoid` | All events + blocking enabled | Maximum security — blocks high-risk actions in real time |

### Storage decision logic

| Level | Stored if... |
|---|---|
| `minimal` | `pii_detected == true` |
| `standard` | `risk_level != "low"` OR `pii_detected == true` |
| `full` | Always |
| `paranoid` | Always |

!!! note "Events are always classified"
    Even when an event is not stored (e.g., a `low` risk event in `standard` mode), it is still fully classified — PII detection, risk scoring, and framework mapping all run. The response includes all fields. The event is just not persisted to the database.

## Frameworks

Enable or disable compliance framework mapping per organization:

```json
{
  "frameworks": {
    "gdpr": true,
    "ai_act": true,
    "soc2": false
  }
}
```

When a framework is disabled, its articles are not included in the event's `frameworks` field. See [framework mapping](framework-mapping.md).

## Alert rules

Alert rules send notifications when events match specific conditions. Currently, Slack webhooks are supported.

### Rule format

```json
{
  "name": "High risk PII alert",
  "condition": {
    "risk_level_gte": "high",
    "pii_detected": true
  },
  "notify": {
    "slack_webhook_url": "https://hooks.slack.com/services/T.../B.../xxx"
  }
}
```

### Supported conditions

All conditions use AND logic — every specified condition must match.

| Condition | Type | Description |
|---|---|---|
| `risk_level_gte` | `string` | Risk level >= this value (`low`, `medium`, `high`, `critical`) |
| `action_contains` | `string` | Action name contains this substring |
| `pii_detected` | `bool` | PII detection matches this value |
| `agent_id_eq` | `string` | Agent ID equals this value |

### Example: alert on critical events

```json
{
  "alert_rules": [
    {
      "name": "Critical events",
      "condition": {
        "risk_level_gte": "critical"
      },
      "notify": {
        "slack_webhook_url": "https://hooks.slack.com/services/..."
      }
    }
  ]
}
```

See [Set up Slack alerts](../guides/slack-alerts.md) for a step-by-step guide.

## Blocking rules

Blocking rules prevent high-risk actions from executing. They only take effect in `paranoid` logging level.

```json
{
  "blocking_rules": {
    "enabled": true,
    "block_on": "critical"
  }
}
```

| Field | Type | Description |
|---|---|---|
| `enabled` | `bool` | Whether blocking is active |
| `block_on` | `string` | Minimum risk level to block (`medium`, `high`, `critical`) |

When an event's risk level meets or exceeds `block_on`:

1. The API returns `"decision": "block"` with a `"reason"`
2. The hook CLI exits with code 2
3. Claude Code / Cowork aborts the tool call
4. The developer sees a message explaining why the action was blocked

!!! warning "Fallback behavior"
    If the API is unreachable, the hook CLI defaults to `"allow"` (exit code 0).
    This prevents the audit system from blocking all work during an outage.

See [Configure paranoid mode](../guides/paranoid-mode.md) for setup instructions.

## Configure via API

### Get current policy

```bash
curl http://localhost:8000/v1/org/policy \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Update policy (partial)

```bash
curl -X PUT http://localhost:8000/v1/org/policy \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "logging_level": "full",
    "frameworks": {"soc2": true}
  }'
```

Only the fields you include are updated. Omitted fields keep their current values.

### Configure via dashboard

Open `http://localhost:8000/dashboard/policy` to manage the policy through a web form.

## Next steps

- [Slack alerts guide](../guides/slack-alerts.md) — set up notifications
- [Paranoid mode guide](../guides/paranoid-mode.md) — enable blocking
- [Enterprise deployment](../guides/enterprise-deployment.md) — per-team policies
