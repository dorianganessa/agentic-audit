# Risk Scoring

Every event processed by AgentAudit receives a risk level: **low**, **medium**, **high**, or **critical**. The risk scorer evaluates a set of rules against the event's action, data, and context, then assigns the highest matching level.

## Risk levels

| Level | Meaning | Example |
|---|---|---|
| <span class="risk-low">low</span> | Routine, non-sensitive action | `npm install`, reading a README |
| <span class="risk-medium">medium</span> | Contains PII or privileged commands | Email in data, `sudo` command |
| <span class="risk-high">high</span> | Production access or sensitive files | Writing to `.env`, prod shell command |
| <span class="risk-critical">critical</span> | Credentials exposed or destructive action | `sk_live_` in data, `rm -rf /` |

## Rules

Rules are evaluated against the event. The final risk level is the **maximum** across all matching rules.

### Critical rules

| Condition | Triggers when |
|---|---|
| Credential indicators | Data contains `sk_live_`, `sk_test_`, `ghp_`, `AKIA`, or `password=` |
| Destructive shell commands | Command contains `rm -rf`, `DROP`, or `DELETE FROM` |

### High rules

| Condition | Triggers when |
|---|---|
| Production shell command | Shell command contains `prod` or `production` |
| PII in production context | PII detected AND context indicates production environment |
| Sensitive file write | File path contains `.env`, `auth`, `secret`, `credential`, or `token` |
| Sensitive file read | File path contains `.env`, `.pem`, `.key`, `id_rsa`, or `credential` |

### Medium rules

| Condition | Triggers when |
|---|---|
| PII detected | Any PII pattern found in data or context |
| Privileged commands | Shell command contains `sudo` or `chmod` |

### Low rules

| Condition | Triggers when |
|---|---|
| Package manager commands | Command contains `npm install`, `pip install`, or `uv add` |
| Default | No other rules match |

## How it works

1. The scorer receives `action`, `data`, `context`, and `pii_detected`
2. All data values are recursively flattened into strings for pattern matching
3. Each rule is evaluated independently
4. The highest matching risk level wins

```
Event: shell_command with "sudo rm -rf /tmp/old"
  → Matches "sudo" (medium)
  → Matches "rm -rf" (critical)
  → Final risk level: critical
```

## Interaction with PII detection

PII detection runs before risk scoring. The `pii_detected` boolean is passed to the scorer, where it triggers:

- `medium` if PII is found anywhere
- `high` if PII is found in a production context

This means an event with an email address in its data will never be lower than `medium`.

## Interaction with policy

The risk level determines:

- **Storage**: In `standard` mode, only `medium`+ events are stored. See [policy system](policy-system.md).
- **Blocking**: In `paranoid` mode, events at or above the `block_on` threshold are blocked. See [paranoid mode](../guides/paranoid-mode.md).
- **Alerts**: Alert rules can filter by `risk_level_gte`. See [Slack alerts](../guides/slack-alerts.md).

## Next steps

- [PII detection](pii-detection.md) — how PII patterns are detected
- [Framework mapping](framework-mapping.md) — which compliance articles are triggered
- [Policy system](policy-system.md) — how risk levels affect storage and blocking
