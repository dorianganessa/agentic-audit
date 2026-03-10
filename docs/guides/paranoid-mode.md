# Configure Paranoid Mode

Paranoid mode blocks high-risk agent actions in real time before they execute. When a Claude Code or Cowork tool call exceeds the risk threshold, the hook returns exit code 2 and the action is aborted.

## How it works

1. Agent calls a tool (e.g., `Bash` with `rm -rf /`)
2. `PreToolUse` hook fires → `agentaudit-hook pre` sends the event to the API
3. API classifies the event → risk level `critical`
4. Policy has `block_on: "high"` → critical >= high → **blocked**
5. API returns `{"decision": "block", "reason": "Risk level critical >= threshold high"}`
6. Hook CLI exits with code 2
7. Claude Code aborts the tool call and shows the block reason

## Enable paranoid mode

### Via API

```bash
curl -X PUT http://localhost:8000/v1/org/policy \
  -H "Authorization: Bearer aa_live_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "logging_level": "paranoid",
    "blocking_rules": {
      "enabled": true,
      "block_on": "high"
    }
  }'
```

### Via dashboard

1. Open `http://localhost:8000/dashboard/policy`
2. Set logging level to **Paranoid**
3. Enable blocking rules
4. Set the threshold (e.g., **High** — blocks high and critical events)
5. Save

## Blocking thresholds

| `block_on` value | Blocks these risk levels |
|---|---|
| `medium` | medium, high, critical |
| `high` | high, critical |
| `critical` | critical only |

!!! warning "Start with `critical`"
    Begin with `block_on: "critical"` to only block the most dangerous actions
    (credentials, destructive commands). Move to `"high"` once you've verified
    your API is reliable and the risk rules match your expectations.

## Test blocking

Trigger a critical event:

```bash
# This simulates what happens when Claude Code tries to run a destructive command
curl -X POST http://localhost:8000/v1/events \
  -H "Authorization: Bearer aa_live_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test-agent",
    "action": "shell_command",
    "data": {"command": "rm -rf /important-data"}
  }'
```

Response:

```json
{
  "risk_level": "critical",
  "decision": "block",
  "reason": "Risk level critical >= threshold high"
}
```

In a real Claude Code session, the developer would see a message that the action was blocked.

## What the developer sees

When an action is blocked, Claude Code displays the hook's stderr output explaining why. The agent can then suggest an alternative approach.

## Fallback behavior

!!! note "Fail-open by default"
    If the AgenticAudit API is unreachable, the hook CLI defaults to **allow** (exit code 0).
    This prevents the audit system from becoming a single point of failure.
    Events are buffered locally at `~/.agentaudit/buffer.jsonl` for later replay.

## Combine with alerts

For maximum visibility, combine paranoid mode with Slack alerts:

```bash
curl -X PUT http://localhost:8000/v1/org/policy \
  -H "Authorization: Bearer aa_live_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "logging_level": "paranoid",
    "blocking_rules": {
      "enabled": true,
      "block_on": "high"
    },
    "alert_rules": [
      {
        "name": "Blocked actions",
        "condition": {
          "risk_level_gte": "high"
        },
        "notify": {
          "slack_webhook_url": "https://hooks.slack.com/services/..."
        }
      }
    ]
  }'
```

Now blocked actions are both prevented and reported to your security team.

## Next steps

- [Policy system](../concepts/policy-system.md) — full policy reference
- [Risk scoring](../concepts/risk-scoring.md) — understand what triggers each level
- [Enterprise deployment](enterprise-deployment.md) — enforce paranoid mode org-wide
