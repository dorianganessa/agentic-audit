# REST API Integration

Use the REST API to integrate AgenticAudit with any agent, framework, or custom application.

## Authentication

All requests require a Bearer token:

```bash
-H "Authorization: Bearer aa_live_xxxxx"
```

## Log an event

```bash
curl -X POST http://localhost:8000/v1/events \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-custom-agent",
    "action": "database_query",
    "data": {
      "query": "SELECT * FROM customers WHERE email = '\''user@example.com'\''",
      "database": "production"
    },
    "context": {
      "environment": "production",
      "user_id": "developer-123"
    },
    "reasoning": "Customer requested account information"
  }'
```

Response:

```json
{
  "id": "01JARQ5X...",
  "agent_id": "my-custom-agent",
  "action": "database_query",
  "data": {"query": "...", "database": "production"},
  "context": {"environment": "production", "user_id": "developer-123"},
  "reasoning": "Customer requested account information",
  "risk_level": "high",
  "pii_detected": true,
  "pii_fields": ["email"],
  "frameworks": {
    "gdpr": ["art_30", "art_15"],
    "ai_act": ["art_14", "art_9"]
  },
  "created_at": "2025-01-15T10:30:00Z",
  "stored": true,
  "decision": "allow",
  "reason": null
}
```

## List events

```bash
curl "http://localhost:8000/v1/events?agent_id=my-custom-agent&risk_level=high&limit=10" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Get a single event

```bash
curl http://localhost:8000/v1/events/01JARQ5X... \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Get statistics

```bash
curl http://localhost:8000/v1/events/stats \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Integration patterns

### Wrap your agent's tool calls

```python
import httpx

AGENTAUDIT_URL = "http://localhost:8000"
AGENTAUDIT_KEY = "aa_live_xxxxx"

def audited_tool_call(agent_id: str, action: str, data: dict) -> dict:
    """Log the tool call, check for blocking, then execute."""
    response = httpx.post(
        f"{AGENTAUDIT_URL}/v1/events",
        headers={"Authorization": f"Bearer {AGENTAUDIT_KEY}"},
        json={
            "agent_id": agent_id,
            "action": action,
            "data": data,
        },
    )
    event = response.json()

    if event.get("decision") == "block":
        raise RuntimeError(f"Action blocked: {event.get('reason')}")

    return event
```

### Batch logging

For high-throughput agents, buffer events locally and send in batches:

```python
from agentaudit import AgentAudit

audit = AgentAudit(api_key="aa_live_xxxxx")

# Each call is a separate HTTP request
# For high-throughput scenarios, consider async:
from agentaudit import AsyncAgentAudit

async with AsyncAgentAudit(api_key="aa_live_xxxxx") as audit:
    event = await audit.log(
        agent_id="fast-agent",
        action="process_record",
        data={"record_id": "12345"},
    )
```

## Error handling

| Status Code | Meaning |
|---|---|
| `201` | Event created |
| `401` | Invalid or missing API key |
| `422` | Validation error (check request body) |
| `500` | Server error |

See the full [API Reference](../api-reference/events.md) for complete endpoint documentation.

## Next steps

- [API Reference — Events](../api-reference/events.md) — full endpoint docs
- [API Reference — Authentication](../api-reference/authentication.md) — API key details
- [Python SDK](../getting-started/quickstart.md) — use the SDK instead of raw HTTP
