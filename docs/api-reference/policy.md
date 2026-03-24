# Policy API

## GET /v1/org/policy

Get the current organization policy.

**Authentication:** Bearer token required.

### Example

```bash
curl http://localhost:8000/v1/org/policy \
  -H "Authorization: Bearer aa_live_xxxxx"
```

### Response (200 OK)

```json
{
  "logging_level": "standard",
  "frameworks": {
    "gdpr": true,
    "ai_act": true,
    "soc2": false
  },
  "alert_rules": [
    {
      "name": "Critical events",
      "condition": {
        "risk_level_gte": "critical"
      },
      "notify": {
        "slack_webhook_url": "https://hooks.slack.com/services/T.../B.../xxx"
      }
    }
  ],
  "blocking_rules": {
    "enabled": false,
    "block_on": "critical"
  }
}
```

---

## PUT /v1/org/policy

Update the organization policy. Supports partial updates — only include the fields you want to change.

**Authentication:** Bearer token required.

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `logging_level` | `string` | No | `minimal`, `standard`, `full`, or `paranoid` |
| `frameworks` | `object` | No | Enable/disable frameworks: `{"gdpr": bool, "ai_act": bool, "soc2": bool}` |
| `alert_rules` | `list[object]` | No | Alert rule definitions (replaces existing rules) |
| `blocking_rules` | `object` | No | Blocking configuration: `{"enabled": bool, "block_on": string}` |
| `compliance_preset` | `string` | No | Compliance preset (e.g., `"ai_act"`). Enables automatic enforcement of preset-specific rules |
| `retention_days` | `int` | No | Event retention period in days. When `compliance_preset` is `"ai_act"`, automatically enforced to ≥ 180 days (Art 12) |

### Policy schema

#### logging_level

| Value | Events stored |
|---|---|
| `minimal` | Only PII events |
| `standard` | Risk `medium`+ or PII events |
| `full` | All events |
| `paranoid` | All events + blocking enabled |

#### frameworks

```json
{
  "gdpr": true,
  "ai_act": true,
  "soc2": false
}
```

#### alert_rules

```json
[
  {
    "name": "Rule name",
    "condition": {
      "risk_level_gte": "high",
      "action_contains": "shell",
      "pii_detected": true,
      "agent_id_eq": "claude-code"
    },
    "notify": {
      "slack_webhook_url": "https://hooks.slack.com/services/..."
    }
  }
]
```

All conditions use AND logic. Omit a condition to not filter on it.

#### blocking_rules

```json
{
  "enabled": true,
  "block_on": "critical"
}
```

`block_on` accepts: `medium`, `high`, `critical`.

### Example: enable paranoid mode

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

### Example: add alert rules

```bash
curl -X PUT http://localhost:8000/v1/org/policy \
  -H "Authorization: Bearer aa_live_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_rules": [
      {
        "name": "High risk with PII",
        "condition": {
          "risk_level_gte": "high",
          "pii_detected": true
        },
        "notify": {
          "slack_webhook_url": "https://hooks.slack.com/services/T.../B.../xxx"
        }
      }
    ]
  }'
```

### Example: enable AI Act compliance preset

```bash
curl -X PUT http://localhost:8000/v1/org/policy \
  -H "Authorization: Bearer aa_live_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "compliance_preset": "ai_act",
    "retention_days": 365
  }'
```

When `compliance_preset` is `"ai_act"`, retention is automatically enforced to a minimum of 180 days.

### Response (200 OK)

Returns the full updated policy object.

### Errors

| Status Code | Description |
|---|---|
| `401` | Missing or invalid API key |
| `422` | Invalid policy values |

---

## POST /v1/org/api-keys/rotate

Generate a new API key and deactivate the current one. The new raw key is returned once and cannot be retrieved again.

**Authentication:** Bearer token required.

### Response (200 OK)

```json
{
  "api_key": "aa_live_NEW_KEY_HERE",
  "key_prefix": "aa_live_NEW",
  "id": "01JARQ...",
  "previous_key_id": "01JARQ..."
}
```
