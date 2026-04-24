# AgenticAudit

[![CI](https://github.com/dorianganessa/agentic-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/dorianganessa/agentic-audit/actions/workflows/ci.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/agentic-audit.svg)](https://pypi.org/project/agentic-audit/)

**Security for AI agents.** Know what they're doing. Prove it to auditors.

## Why

Your AI agents access customer data, modify production systems, and make autonomous decisions — with zero paper trail. The EU AI Act is in force. Your auditor is going to ask what your agents did last Tuesday. You need an answer.

AgenticAudit gives you that answer. Every action your AI agents take gets logged, classified by risk, and mapped to the compliance frameworks you already care about (GDPR, AI Act, SOC 2). Self-hosted, open-source, and working in minutes.

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

## How It Works

1. **Connect your agents** — Claude Code hooks, LangChain callback, Python SDK, or REST API
2. **Actions get logged automatically** — every tool call, file access, API request
3. **Risk is classified in real-time** — low / medium / high / critical, with personal data detection
4. **Compliance mapping happens instantly** — each action maps to GDPR, AI Act, and SOC 2 articles
5. **Block dangerous actions before they happen** — optional paranoid mode stops high-risk operations

Works with Claude Code, LangChain, Codex, Cowork, or any agent via the REST API.

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
│              │ AgenticAudit  │                                  │
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
│  │  ┌────────────┐ ┌──────────┐ ┌─────────┐ │                 │
│  │  │AI Systems  │ │Compliance│ │FRIA     │ │                 │
│  │  │Registry    │ │Scorer    │ │Generator│ │                 │
│  │  └────────────┘ └──────────┘ └─────────┘ │                 │
│  └───────────────────┬───────────────────────┘                  │
│                      │                                          │
│              ┌───────▼───────┐                                  │
│              │  PostgreSQL   │                                  │
│              │  :5432        │                                  │
│              └───────────────┘                                  │
└─────────────────────────────────────────────────────────────────┘
```

## API Reference

### Events

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/events` | Ingest an audit event |
| `GET` | `/v1/events` | List events (filters: agent_id, action, risk_level, pii_detected, session_id, after, before) |
| `GET` | `/v1/events/{id}` | Get event by ID |
| `GET` | `/v1/events/stats` | Aggregate statistics |

### AI Systems

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/systems` | Register an AI system |
| `GET` | `/v1/systems` | List AI systems |
| `GET` | `/v1/systems/{id}` | Get system by ID |
| `PUT` | `/v1/systems/{id}` | Update system |
| `DELETE` | `/v1/systems/{id}` | Deactivate system (soft-delete) |
| `GET` | `/v1/systems/{id}/events` | Events matching system's agent_id_patterns |
| `GET` | `/v1/systems/{id}/stats` | Aggregate event stats for system |
| `GET` | `/v1/systems/{id}/classification-suggestion` | Suggest AI Act risk classification (Annex III + Article 5 prohibited detection, with per-phrase evidence) |

### Compliance

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/compliance/ai-act/status` | Compliance score and checks |
| `GET` | `/v1/compliance/ai-act/report` | Download compliance report (PDF) |
| `GET` | `/v1/compliance/ai-act/fria/{id}/pdf` | Download FRIA for a system (PDF) |

### Policy & Organization

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/org/policy` | Get current policy |
| `PUT` | `/v1/org/policy` | Update policy (supports `compliance_preset`, `retention_days`) |
| `POST` | `/v1/org/api-keys/rotate` | Rotate API key |

### Dashboard

| Route | Description |
|-------|-------------|
| `/dashboard` | Event timeline with HTMX filters |
| `/dashboard/events/{id}` | Event detail view |
| `/dashboard/stats` | Stats overview with charts |
| `/dashboard/compliance` | AI Act compliance dashboard |
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

# AI Systems
systems = audit.list_systems()
system = audit.create_system(name="My Bot", agent_id_patterns=["my-bot-*"])

# Compliance
status = audit.get_compliance_status()
print(status["score"], status["checks"])
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

Install the AgenticAudit plugin in Claude Cowork to audit every knowledge worker action — connector access (Google Drive, Salesforce, DocuSign), file operations, web browsing, and sub-agent coordination.

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
- `list_ai_systems` — list registered AI systems with compliance status
- `get_compliance_status` — AI Act compliance score and check results
- `suggest_classification` — suggest risk classification from system metadata + event patterns, with Article 5 prohibited-practice detection and per-phrase evidence

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

Automatically tails `~/.codex/sessions/*.jsonl` and maps Codex tool calls (shell, apply_patch, read_file, etc.) to AgenticAudit events.

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

AGPL-3.0
