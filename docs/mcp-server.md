# MCP Server Guide

## Overview

The AgenticAudit MCP server gives AI agents self-awareness of their audit trail. Agents can query their own events, check risk summaries, and perform dry-run risk checks before executing actions.

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

### `list_ai_systems`

List all registered AI systems with their risk classification and compliance status.

**Returns:**

```json
{
  "systems": [
    {
      "id": "01JARQ...",
      "name": "HR Screening Bot",
      "vendor": "Acme AI",
      "risk_classification": "high",
      "annex_iii_category": "employment",
      "fria_status": "completed",
      "contract_has_ai_annex": true,
      "agent_id_patterns": ["hr-bot", "hr-bot-*"],
      "is_active": true
    }
  ],
  "total": 1
}
```

### `get_compliance_status`

Get the organization's AI Act compliance score and check results.

**Returns:**

```json
{
  "score": 80,
  "checks": {
    "all_classified": true,
    "no_prohibited": true,
    "fria_complete": false,
    "contracts_reviewed": true,
    "retention_compliant": true
  },
  "summary": {
    "total_systems": 5,
    "high_risk": 2,
    "fria_completed": 1,
    "retention_days": 365
  },
  "deadlines": [
    {"system": "HR Bot", "type": "fria_review", "date": "2026-07-15T00:00:00"}
  ]
}
```

### `suggest_classification`

Suggest an AI Act risk classification for a system by analyzing its metadata and event patterns. See the [Risk Classification concept](concepts/risk-classification.md) for details on the decision hierarchy (Article 5 prohibited → Annex III high → Art. 50 limited → minimal) and confidence thresholds.

**Parameters:**

| Name        | Type   | Description         |
|-------------|--------|---------------------|
| `system_id` | string | AI system ID        |

**Returns:**

```json
{
  "suggested_classification": "high",
  "suggested_category": "employment",
  "rationale": "Annex III category 'employment' detected (score 42.5)",
  "evidence": {
    "total_events": 1523,
    "pii_events": 45,
    "category_scores": {"employment": 42.5},
    "category_matches": {
      "employment": {"candidate": 12.5, "resume": 12.5, "hiring": 12.5, "salary": 5.0}
    },
    "prohibited_scores": {},
    "category_confidence_threshold": 3.0,
    "prohibited_confidence_threshold": 4.5
  }
}
```

`category_matches` lists the exact keyword phrases that contributed to the score — useful for FRIA evidence and for reviewing whether the suggestion is sound before accepting it.

## Environment Variables

| Variable               | Required | Description             |
|------------------------|----------|-------------------------|
| `AGENTAUDIT_API_KEY`   | Yes      | API key for auth        |
| `AGENTAUDIT_BASE_URL`  | No       | API URL (default: `http://localhost:8000`) |
