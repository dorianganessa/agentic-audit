# AgenticAudit MCP Server

[MCP](https://modelcontextprotocol.io/) server that lets AI agents query their own [AgenticAudit](https://agentaudit.dev) compliance trail.

Agents can review their recent actions, check risk summaries, dry-run risk checks, and query AI Act compliance status.

## Install

```bash
pip install agentic-audit-mcp
```

Or run directly:

```bash
uvx agentic-audit-mcp
```

## Configure in Claude Code

```json
// ~/.claude/settings.json
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

## Tools

| Tool | Description |
|---|---|
| `get_my_audit_events` | Review recent actions and risk levels |
| `get_session_risk_summary` | Risk breakdown for the current session |
| `check_action_risk` | Dry-run risk check without logging |
| `list_ai_systems` | List registered AI systems with compliance status |
| `get_compliance_status` | AI Act compliance score and check results |
| `suggest_classification` | Suggest risk classification from event patterns |

## Links

- [Documentation](https://docs.agentaudit.dev)
- [GitHub](https://github.com/dorianganessa/agentic-audit)

## License

Apache 2.0
