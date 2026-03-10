# AgentAudit

Open-source API to log, classify and audit every AI agent action for **GDPR / AI Act / SOC2** compliance.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  AI Agents                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │Claude Code│  │LangChain │  │  Codex   │  │  Any Agent   │   │
│  │  (hooks) │  │(callback)│  │ (parser) │  │   (SDK)      │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
│       │              │             │               │            │
│  ┌────▼─────┐        │        ┌────▼─────┐   ┌────▼─────┐     │
│  │Hook CLI  │        │        │Codex     │   │Python SDK│     │
│  │agentaudit│        │        │Parser    │   │AgentAudit│     │
│  │-hook     │        │        │          │   │.log()    │     │
│  └────┬─────┘        │        └────┬─────┘   └────┬─────┘     │
│       └──────────────┼─────────────┴───────────────┘            │
│                      │                                          │
│              ┌───────▼───────┐                                  │
│              │  AgentAudit   │                                  │
│              │  API Server   │◄── MCP Server (query only)       │
│              │  :8000        │                                  │
│              └───────┬───────┘                                  │
│                      │                                          │
│  ┌───────────────────┼───────────────────────┐                  │
│  │  ┌────────┐ ┌─────▼─────┐ ┌────────────┐  │                 │
│  │  │PII     │ │Risk       │ │Framework   │  │                 │
│  │  │Detector│ │Scorer     │ │Mapper      │  │                 │
│  │  └────────┘ └───────────┘ └────────────┘  │                 │
│  │  ┌────────┐ ┌───────────┐ ┌────────────┐  │                 │
│  │  │Policy  │ │Slack      │ │PDF Report  │  │                 │
│  │  │Engine  │ │Alerter    │ │Generator   │  │                 │
│  │  └────────┘ └───────────┘ └────────────┘  │                 │
│  └───────────────────┬───────────────────────┘                  │
│                      │                                          │
│              ┌───────▼───────┐                                  │
│              │  PostgreSQL   │                                  │
│              │  :5432        │                                  │
│              └───────────────┘                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Docker Compose

```bash
docker compose up
```

The API starts at `http://localhost:8000`. A default API key is printed in the logs on first run.
Dashboard available at `http://localhost:8000/dashboard`.

### Manual Setup

```bash
# Install dependencies
uv sync

# Start Postgres (or use docker compose up db)
# Run migrations
cd packages/api
AGENTAUDIT_DATABASE_URL=postgresql+psycopg2://agentaudit:agentaudit@localhost:5432/agentaudit \
  uv run alembic -c src/agentaudit_api/alembic.ini upgrade head

# Seed default API key
uv run python -m agentaudit_api.seed

# Start the API
uv run uvicorn agentaudit_api.main:app --host 0.0.0.0 --port 8000
```

## API Reference

### Events

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/events` | Ingest an audit event |
| `GET` | `/v1/events` | List events (filters: agent_id, action, risk_level, pii_detected, session_id, after, before) |
| `GET` | `/v1/events/{id}` | Get event by ID |
| `GET` | `/v1/events/stats` | Aggregate statistics |

### Policy

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/org/policy` | Get current policy |
| `PUT` | `/v1/org/policy` | Update policy |

### Dashboard

| Route | Description |
|-------|-------------|
| `/dashboard` | Event timeline with HTMX filters |
| `/dashboard/events/{id}` | Event detail view |
| `/dashboard/stats` | Stats overview with charts |
| `/dashboard/policy` | Policy management UI |
| `/dashboard/report/pdf` | PDF compliance report export |

### Ingest Example

```bash
curl -X POST http://localhost:8000/v1/events \
  -H "Authorization: Bearer aa_live_YOUR_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "claude-code",
    "action": "shell_command",
    "data": {"command": "ls -la", "exit_code": 0},
    "context": {"tool": "claude_code", "session_id": "abc123"},
    "reasoning": "User requested directory listing"
  }'
```

## Python SDK

```python
from agentaudit import AgentAudit

audit = AgentAudit(api_key="aa_live_xxx", base_url="http://localhost:8000")

# Log an event
event = audit.log(
    agent_id="my-agent",
    action="shell_command",
    data={"command": "ls -la"},
    reasoning="User requested directory listing",
)
print(event.risk_level)  # "low"

# Query events
result = audit.list_events(risk_level="high", limit=10)
for e in result["events"]:
    print(f"{e.action} — {e.risk_level}")

# Get stats
stats = audit.get_stats()
print(stats["total_events"], stats["by_risk_level"])
```

## Claude Code Hooks

Configure in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [{ "command": "agentaudit-hook pre" }],
    "PostToolUse": [{ "command": "agentaudit-hook post" }],
    "SessionStart": [{ "command": "agentaudit-hook session-start" }],
    "SessionEnd": [{ "command": "agentaudit-hook session-end" }]
  }
}
```

Set environment variables:
```bash
export AGENTAUDIT_API_KEY="aa_live_xxx"
export AGENTAUDIT_BASE_URL="http://localhost:8000"
```

In **paranoid** mode with blocking enabled, `agentaudit-hook pre` exits with code 2 for high-risk actions, preventing Claude Code from executing them.

## Cowork Integration

Install the AgentAudit plugin in Claude Cowork to audit every knowledge worker action — connector access (Google Drive, Salesforce, DocuSign), file operations, web browsing, and sub-agent coordination.

```
/plugin install github:dorianganessa/agentic-audit --path plugins/cowork
```

The plugin uses the same `agentaudit-hook` CLI. MCP connector calls (e.g., `mcp__google_drive__read_file`) are automatically mapped to `connector_access` events with connector and operation metadata.

See [Cowork Integration Guide](docs/cowork.md) for full setup including enterprise deployment.

## MCP Server

Lets AI agents query their own audit trail for self-awareness.

Configure in Claude Code MCP settings:

```json
{
  "mcpServers": {
    "agentaudit": {
      "command": "uvx",
      "args": ["agentic-audit-mcp"],
      "env": {
        "AGENTAUDIT_API_KEY": "aa_live_xxxxx",
        "AGENTAUDIT_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

**Tools exposed:**
- `get_my_audit_events` — review recent actions and risk levels
- `get_session_risk_summary` — summary of risk levels for current session
- `check_action_risk` — dry-run risk check before taking an action

## LangChain Integration

```python
from agentaudit.integrations.langchain import AgentAuditCallbackHandler

handler = AgentAuditCallbackHandler(api_key="aa_live_xxx")
agent.run("do something", callbacks=[handler])
```

Logs `tool_start`, `tool_end`, and `chain_start` events automatically.

## Codex Integration

Watch Codex session transcripts and forward events:

```bash
export AGENTAUDIT_API_KEY="aa_live_xxx"
agentaudit-codex-watch
```

Automatically tails `~/.codex/sessions/*.jsonl` and maps Codex tool calls (shell, apply_patch, read_file, etc.) to AgentAudit events.

## Policy Levels

| Level | Stores | Blocks |
|-------|--------|--------|
| `minimal` | PII events only | No |
| `standard` | Medium+ risk or PII | No |
| `full` | All events | No |
| `paranoid` | All events | Yes (configurable threshold) |

## Compliance Frameworks

Events are automatically mapped to compliance articles:

**GDPR:** Art. 13 (transparency), Art. 15 (access), Art. 17 (erasure), Art. 22 (automated decisions), Art. 30 (processing records)

**AI Act:** Art. 9 (risk management), Art. 13 (transparency), Art. 14 (human oversight)

**SOC 2:** CC6.1 (logical access), CC6.5 (data classification), CC7.2 (incident management)

## Slack Alerts

Configure alert rules in the org policy:

```json
{
  "alert_rules": [
    {
      "name": "Production DB access",
      "condition": {"risk_level_gte": "high"},
      "notify": {"slack_webhook_url": "https://hooks.slack.com/services/xxx"}
    }
  ]
}
```

Conditions (AND logic): `risk_level_gte`, `action_contains`, `pii_detected`, `agent_id_eq`.

## Testing

```bash
uv run pytest tests/ -v
```

Tests use `testcontainers` to spin up a real Postgres instance — Docker must be running.

## Project Structure

```
packages/
├── api/          # FastAPI server + dashboard + PDF reports
├── sdk/          # Python SDK + LangChain + Codex integrations
├── hook-cli/     # Claude Code hooks CLI
└── mcp-server/   # MCP server for agent self-awareness
plugins/
└── cowork/       # Claude Cowork plugin (hooks + skill)
docs/
└── cowork.md     # Cowork integration guide
```

## License

Apache 2.0
