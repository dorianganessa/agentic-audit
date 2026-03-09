# Set Up Slack Alerts

Get notified in Slack when AgentAudit detects high-risk events or PII exposure.

## Step 1: Create a Slack webhook

1. Go to [Slack App Management](https://api.slack.com/apps)
2. Create a new app (or use an existing one)
3. Enable **Incoming Webhooks**
4. Add a webhook to your target channel
5. Copy the webhook URL (starts with `https://hooks.slack.com/services/`)

## Step 2: Add an alert rule

Update your organization policy via the API:

```bash
curl -X PUT http://localhost:8000/v1/org/policy \
  -H "Authorization: Bearer aa_live_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_rules": [
      {
        "name": "High risk events",
        "condition": {
          "risk_level_gte": "high"
        },
        "notify": {
          "slack_webhook_url": "https://hooks.slack.com/services/T.../B.../xxx"
        }
      }
    ]
  }'
```

Or configure via the dashboard at `http://localhost:8000/dashboard/policy`.

## Step 3: Test the alert

Trigger a high-risk event. For example, log an event with a credential pattern:

```bash
curl -X POST http://localhost:8000/v1/events \
  -H "Authorization: Bearer aa_live_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test-agent",
    "action": "shell_command",
    "data": {"command": "echo sk_live_abc123def456"}
  }'
```

This triggers a `critical` risk event. Check your Slack channel — you should see a formatted alert with the event details.

## Alert message format

The Slack message includes:

- Event action and agent ID
- Risk level (color-coded)
- PII detection status
- Matched compliance frameworks
- Timestamp

## Multiple alert rules

You can configure multiple rules for different channels or conditions:

```json
{
  "alert_rules": [
    {
      "name": "Critical to #security-incidents",
      "condition": {
        "risk_level_gte": "critical"
      },
      "notify": {
        "slack_webhook_url": "https://hooks.slack.com/services/.../security"
      }
    },
    {
      "name": "PII events to #compliance",
      "condition": {
        "pii_detected": true
      },
      "notify": {
        "slack_webhook_url": "https://hooks.slack.com/services/.../compliance"
      }
    },
    {
      "name": "Production shell commands to #devops",
      "condition": {
        "action_contains": "shell_command",
        "risk_level_gte": "high"
      },
      "notify": {
        "slack_webhook_url": "https://hooks.slack.com/services/.../devops"
      }
    }
  ]
}
```

## Condition reference

All conditions use AND logic — every specified condition must match for the alert to fire.

| Condition | Type | Example |
|---|---|---|
| `risk_level_gte` | `string` | `"high"` — matches high and critical |
| `action_contains` | `string` | `"shell"` — matches shell_command |
| `pii_detected` | `bool` | `true` — only PII events |
| `agent_id_eq` | `string` | `"claude-code"` — only this agent |

## Next steps

- [Configure paranoid mode](paranoid-mode.md) — block risky actions, not just alert
- [Policy system](../concepts/policy-system.md) — full policy reference
