# Events API

!!! tip "OpenAPI spec"
    The full OpenAPI 3.1 schema is available at [`openapi.json`](openapi.json) and
    auto-generated from the source code on every release.

## POST /v1/events

Ingest an audit event. The event is classified (PII detection, risk scoring, framework mapping) synchronously and returned with all computed fields.

**Authentication:** Bearer token required.

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `agent_id` | `string` | Yes | Identifier for the agent (e.g., `"claude-code"`, `"booking-agent-v2"`) |
| `action` | `string` | Yes | Action type (e.g., `"shell_command"`, `"file_write"`, `"connector_access"`) |
| `data` | `object` | No | Action-specific data (e.g., `{"command": "ls -la"}`) |
| `context` | `object` | No | Additional context (e.g., `{"environment": "production"}`) |
| `reasoning` | `string` | No | Agent's reasoning for the action |

### Response (201 Created)

| Field | Type | Description |
|---|---|---|
| `id` | `string` | ULID event identifier |
| `agent_id` | `string` | Agent identifier |
| `action` | `string` | Action type |
| `data` | `object` | Action data |
| `context` | `object` | Additional context |
| `reasoning` | `string\|null` | Agent reasoning |
| `risk_level` | `string\|null` | Computed risk: `low`, `medium`, `high`, `critical` |
| `pii_detected` | `bool` | Whether PII was found |
| `pii_fields` | `list[string]` | Types of PII detected (e.g., `["email", "ipv4"]`) |
| `frameworks` | `object` | Mapped compliance articles (e.g., `{"gdpr": ["art_30"]}`) |
| `created_at` | `string\|null` | ISO 8601 timestamp (null if not stored) |
| `stored` | `bool` | Whether the event was persisted to DB |
| `decision` | `string` | `"allow"` or `"block"` |
| `reason` | `string\|null` | Reason for blocking (if blocked) |

### Example

=== "cURL"

    ```bash
    curl -X POST http://localhost:8000/v1/events \
      -H "Authorization: Bearer aa_live_xxxxx" \
      -H "Content-Type: application/json" \
      -d '{
        "agent_id": "claude-code",
        "action": "shell_command",
        "data": {"command": "cat /etc/passwd"},
        "context": {"session_id": "sess_abc123"}
      }'
    ```

=== "Python SDK"

    ```python
    from agentaudit import AgentAudit

    audit = AgentAudit(api_key="aa_live_xxxxx")
    event = audit.log(
        agent_id="claude-code",
        action="shell_command",
        data={"command": "cat /etc/passwd"},
        context={"session_id": "sess_abc123"},
    )
    ```

### Response example

```json
{
  "id": "01JARQ5XKFBN3C8M4VG0ABCD12",
  "agent_id": "claude-code",
  "action": "shell_command",
  "data": {"command": "cat /etc/passwd"},
  "context": {"session_id": "sess_abc123"},
  "reasoning": null,
  "risk_level": "medium",
  "pii_detected": false,
  "pii_fields": [],
  "frameworks": {
    "gdpr": [],
    "ai_act": ["art_14"]
  },
  "created_at": "2025-01-15T10:30:00Z",
  "stored": true,
  "decision": "allow",
  "reason": null
}
```

---

## GET /v1/events

List events with optional filters and pagination.

**Authentication:** Bearer token required.

### Query parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `agent_id` | `string` | — | Filter by agent ID |
| `action` | `string` | — | Filter by action type |
| `risk_level` | `string` | — | Filter by risk level |
| `pii_detected` | `bool` | — | Filter by PII detection |
| `session_id` | `string` | — | Filter by session ID |
| `after` | `datetime` | — | Events after this ISO 8601 timestamp |
| `before` | `datetime` | — | Events before this ISO 8601 timestamp |
| `limit` | `int` | `50` | Max results (1–200) |
| `offset` | `int` | `0` | Skip N results |

### Example

```bash
curl "http://localhost:8000/v1/events?risk_level=high&pii_detected=true&limit=10" \
  -H "Authorization: Bearer aa_live_xxxxx"
```

### Response (200 OK)

```json
{
  "events": [
    {
      "id": "01JARQ5X...",
      "agent_id": "claude-code",
      "action": "shell_command",
      "risk_level": "high",
      "pii_detected": true,
      "pii_fields": ["email"],
      "frameworks": {"gdpr": ["art_30"]},
      "created_at": "2025-01-15T10:30:00Z",
      "stored": true,
      "decision": "allow",
      "reason": null
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0
}
```

---

## GET /v1/events/{event_id}

Get a single event by its ULID.

**Authentication:** Bearer token required.

### Path parameters

| Parameter | Type | Description |
|---|---|---|
| `event_id` | `string` | ULID event identifier |

### Example

```bash
curl http://localhost:8000/v1/events/01JARQ5XKFBN3C8M4VG0ABCD12 \
  -H "Authorization: Bearer aa_live_xxxxx"
```

### Response (200 OK)

Full event object (same schema as POST response).

### Errors

| Code | Description |
|---|---|
| `404` | Event not found |

---

## GET /v1/events/stats

Get aggregate statistics across events.

**Authentication:** Bearer token required.

### Query parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `after` | `datetime` | — | Stats for events after this timestamp |
| `before` | `datetime` | — | Stats for events before this timestamp |

### Example

```bash
curl "http://localhost:8000/v1/events/stats?after=2025-01-01T00:00:00Z" \
  -H "Authorization: Bearer aa_live_xxxxx"
```

### Response (200 OK)

```json
{
  "total_events": 1523,
  "by_risk_level": {
    "low": 890,
    "medium": 412,
    "high": 198,
    "critical": 23
  },
  "by_action": {
    "shell_command": 623,
    "file_write": 341,
    "file_read": 289,
    "connector_access": 156,
    "file_edit": 114
  },
  "by_agent": {
    "claude-code": 1102,
    "cowork": 321,
    "booking-agent": 100
  },
  "pii_events": 287
}
```

---

## Error responses

All endpoints return errors in this format:

```json
{
  "detail": "Error message describing the issue"
}
```

| Status Code | Description |
|---|---|
| `401` | Missing or invalid API key |
| `403` | API key does not have access to this resource |
| `404` | Resource not found |
| `422` | Validation error (check request body or parameters) |
| `500` | Internal server error |
