# Cowork Integration

AgentAudit captures every Cowork action — connector access, file operations, web browsing, sub-agent spawning — with full compliance classification.

!!! note "Why Cowork needs AgentAudit"
    Anthropic explicitly states: *"Cowork activity is not captured in Audit Logs,
    Compliance API, or Data Exports. Do not use Cowork for regulated workloads."*
    AgentAudit fills this gap.

## How it works

Cowork sends events via **OpenTelemetry (OTLP)** — the standard observability protocol. AgentAudit provides a native OTLP-compatible endpoint that receives these events, maps them to audit records, and runs them through the full compliance pipeline (PII detection, risk scoring, framework mapping).

No plugins or CLI tools needed. Just point Cowork's OTLP endpoint to AgentAudit.

## Setup

### 1. Prerequisites

- AgentAudit API running ([quickstart](../getting-started/quickstart.md))
- Your AgentAudit API key

### 2. Configure Cowork's OTLP endpoint

In your Cowork organization settings:

| Setting | Value |
|---|---|
| **OTLP Endpoint** | `http://localhost:8000/v1/otlp` (or your cloud URL) |
| **Protocol** | `http/json` |
| **Headers** | `Authorization=Bearer aa_live_xxxxx` |

That's it. Every Cowork action is now captured by AgentAudit.

!!! tip "Cloud deployment"
    For production, use your public AgentAudit URL:
    `https://your-agentaudit.example.com/v1/otlp`

### 3. Verify it works

1. Open Cowork and perform any action (use a connector, read a file, browse the web)
2. Check the AgentAudit dashboard at `http://localhost:8000/dashboard`
3. Events should appear in real time with risk levels and compliance tags

## What gets captured

Cowork sends 5 event types via OTLP. AgentAudit maps each to the appropriate audit action:

| Cowork Event | AgentAudit Action | Description |
|---|---|---|
| `cowork.tool_result` | `connector_access` / `file_read` / `shell_command` / etc. | Tool execution results — auto-mapped by tool name |
| `cowork.tool_decision` | `tool_decision` | Agent's decision to use a tool |
| `cowork.user_prompt` | `user_prompt` | User messages to Cowork |
| `cowork.api_request` | `api_request` | LLM API calls |
| `cowork.api_error` | `api_error` | Failed API calls |

### Tool name mapping

For `cowork.tool_result` events, the tool name determines the audit action:

| Tool | AgentAudit Action |
|---|---|
| `Read`, `Glob`, `Grep` | `file_read` |
| `Write`, `Edit` | `file_write` |
| `Bash` | `shell_command` |
| `WebFetch` | `web_browse` |
| `WebSearch` | `web_search` |
| `Agent` | `sub_agent_spawn` |
| `mcp__*` (connectors) | `connector_access` |

MCP connector tools (e.g., `mcp__google_drive__read_file`) are automatically parsed to extract the connector name and operation.

### Data extracted from OTLP events

```json
{
  "action": "connector_access",
  "data": {
    "tool_name": "mcp__google_drive__read_file",
    "connector": "google_drive",
    "operation": "read_file",
    "tool_parameters": {"file_id": "1abc..."},
    "success": true,
    "duration_ms": 342,
    "mcp_server_scope": "google_drive"
  },
  "context": {
    "session_id": "sess_abc123",
    "organization_id": "org_xyz",
    "user_email": "user@company.com",
    "source": "otlp",
    "otlp_event_name": "cowork.tool_result"
  }
}
```

## OTLP protocol details

AgentAudit accepts the standard **OTLP HTTP/JSON** format:

- **Endpoint**: `POST /v1/otlp/v1/logs`
- **Content-Type**: `application/json`
- **Body**: `ExportLogsServiceRequest` (OTLP Logs spec)
- **Auth**: `Authorization: Bearer <api_key>`

The endpoint is fully compatible with any OTLP-capable client, not just Cowork.

### Request format

```json
{
  "resourceLogs": [{
    "resource": {
      "attributes": [
        {"key": "service.name", "value": {"stringValue": "cowork"}},
        {"key": "service.version", "value": {"stringValue": "1.0.0"}}
      ]
    },
    "scopeLogs": [{
      "logRecords": [{
        "attributes": [
          {"key": "event.name", "value": {"stringValue": "cowork.tool_result"}},
          {"key": "tool_name", "value": {"stringValue": "mcp__google_drive__read_file"}},
          {"key": "session.id", "value": {"stringValue": "sess_abc123"}},
          {"key": "success", "value": {"boolValue": true}}
        ]
      }]
    }]
  }]
}
```

## Risk scoring for Cowork

Standard risk rules apply, plus Cowork-specific patterns are detected:

| Pattern | Risk Level | Why |
|---|---|---|
| Connector accessing PII data | Medium | Personal data processing requires tracking |
| Sensitive file paths (HR, compensation, auth) | High | Access control monitoring |
| Credential patterns in data | Critical | Secret exposure prevention |
| Bulk export operations | Medium | Data exfiltration signal |
| Production environment access | High | Change management tracking |

## Enterprise deployment

For organizations deploying Cowork at scale:

1. **Central OTLP endpoint**: Point all Cowork instances to a single AgentAudit deployment
2. **Per-team API keys**: Provision individual API keys so events are attributed to specific teams
3. **Policy per team**: Set different logging levels (e.g., `paranoid` for finance, `standard` for engineering)
4. **OTLP headers**: Distribute API keys via Cowork org settings — users don't need to configure anything

See [Enterprise deployment](../guides/enterprise-deployment.md) for the full guide.

## Dashboard

Cowork sessions appear in the dashboard alongside Claude Code sessions. Filter by `agent_id` or `session_id` to isolate Cowork activity.

Each event shows:

- Tool/connector name and operation
- Risk level badge
- PII detection result
- Mapped compliance frameworks (GDPR, AI Act, SOC 2)

## Next steps

- [Claude Code integration](claude-code.md) — audit Claude Code sessions
- [Policy system](../concepts/policy-system.md) — configure what gets logged
- [Risk scoring](../concepts/risk-scoring.md) — how risk levels are assigned
