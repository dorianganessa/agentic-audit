# Cowork Integration

AgentAudit provides a Cowork plugin that captures every action — connector access, file operations, web browsing, sub-agent spawning — with full compliance classification.

!!! note "Why Cowork needs AgentAudit"
    Anthropic explicitly states: *"Cowork activity is not captured in Audit Logs,
    Compliance API, or Data Exports. Do not use Cowork for regulated workloads."*
    AgentAudit is the missing piece.

## Prerequisites

- AgentAudit API running ([quickstart](../getting-started/quickstart.md))
- `agentaudit-hook` CLI installed (`pip install agentaudit`)
- Environment variables set:

```bash
export AGENTAUDIT_API_KEY="aa_live_xxxxx"
export AGENTAUDIT_BASE_URL="http://localhost:8000"
```

## Install the plugin

```bash
/plugin install github:dorianganessa/agentaudit --path plugins/cowork
```

The plugin registers four hooks automatically:

| Hook | Command |
|---|---|
| `PreToolUse` | `agentaudit-hook pre` |
| `PostToolUse` | `agentaudit-hook post` |
| `SessionStart` | `agentaudit-hook session-start` |
| `SessionEnd` | `agentaudit-hook session-end` |

## What gets captured

Cowork uses MCP connectors for external service access. The hook CLI parses each `mcp__<connector>__<operation>` tool call into structured audit data:

| Connector | Example Operations | AgentAudit Action |
|---|---|---|
| Google Drive | `read_file`, `write_file`, `list_files` | `connector_access` |
| Salesforce | `query_records`, `update_record` | `connector_access` |
| Gmail | `send_email`, `read_email` | `connector_access` |
| DocuSign | `send_envelope`, `get_status` | `connector_access` |
| Slack | `post_message`, `read_channel` | `connector_access` |

Standard Claude Code tools (Bash, Read, Write, Edit) are also captured with their corresponding actions.

### Data extracted for connector access

```json
{
  "action": "connector_access",
  "data": {
    "connector": "google_drive",
    "operation": "read_file",
    "args": {
      "file_id": "1abc...",
      "format": "text"
    }
  }
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

1. **Private marketplace**: Publish the AgentAudit plugin to your organization's private plugin marketplace
2. **Auto-install**: Configure the plugin to install automatically for all users
3. **Per-user API keys**: Provision individual API keys so events are attributed to specific users
4. **Policy per team**: Set different logging levels per team (e.g., `paranoid` for finance, `standard` for engineering)

See [Enterprise deployment](../guides/enterprise-deployment.md) for the full guide.

## Dashboard

Cowork sessions appear in the dashboard alongside Claude Code sessions. Filter by `agent_id` or `session_id` to isolate Cowork activity.

Each connector access event shows:

- Connector name and operation
- Risk level badge
- PII detection result
- Mapped compliance frameworks (GDPR, AI Act, SOC 2)

## Next steps

- [Claude Code integration](claude-code.md) — audit Claude Code sessions
- [Policy system](../concepts/policy-system.md) — configure what gets logged
- [Risk scoring](../concepts/risk-scoring.md) — how risk levels are assigned
