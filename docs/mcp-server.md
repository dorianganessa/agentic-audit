# MCP Server Guide

## Overview

The AgentAudit MCP server gives AI agents self-awareness of their audit trail. Agents can query their own events, check risk summaries, and perform dry-run risk checks before executing actions.

## Setup

```bash
pip install agentic-audit-mcp
```

Configure in your MCP client (e.g., Claude Code `~/.claude/mcp.json`):

```json
{
  "mcpServers": {
    "agentaudit": {
      "command": "agentaudit-mcp",
      "env": {
        "AGENTAUDIT_API_KEY": "aa_live_your_key_here",
        "AGENTAUDIT_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

## Tools

### `get_my_audit_events`

List recent audit events for the current session.

**Parameters:**

| Name         | Type   | Default | Description                            |
|--------------|--------|---------|----------------------------------------|
| `limit`      | int    | 20      | Max events to return                   |
| `risk_level` | string | null    | Filter by risk level                   |
| `action`     | string | null    | Filter by action type                  |

**Returns:** `{events: [...], total: int}`

### `get_session_risk_summary`

Get a risk breakdown for the current session.

**Returns:**

```json
{
  "total_events": 42,
  "by_risk_level": {"low": 30, "medium": 8, "high": 3, "critical": 1},
  "pii_events": 5,
  "unique_agents": 2
}
```

### `check_action_risk`

Dry-run risk check without logging the event. Useful for agents to assess risk before executing an action.

**Parameters:**

| Name     | Type   | Description                         |
|----------|--------|-------------------------------------|
| `action` | string | Action type (e.g., `shell_command`) |
| `data`   | object | Action data (e.g., `{command: ...}`)  |

**Returns:**

```json
{
  "risk_level": "high",
  "pii_detected": true,
  "pii_fields": ["email"],
  "note": "Dry-run check only — event was not logged"
}
```

## Risk Checker

The MCP server includes a local risk checker that scores actions without calling the API. It detects:

- **Credential patterns** — API keys, AWS keys, GitHub/Slack tokens, Bearer tokens
- **Dangerous commands** — `rm -rf`, `DROP`, `DELETE FROM`
- **Production access** — Commands targeting prod/production environments
- **PII** — Emails, IP addresses, phone numbers, credit cards
- **Sensitive files** — `.env`, `.pem`, `.key`, `id_rsa`, credentials

## Environment Variables

| Variable               | Required | Description             |
|------------------------|----------|-------------------------|
| `AGENTAUDIT_API_KEY`   | Yes      | API key for auth        |
| `AGENTAUDIT_BASE_URL`  | No       | API URL (default: `http://localhost:8000`) |
