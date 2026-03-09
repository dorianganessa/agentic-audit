# AgentAudit MCP Server

[MCP](https://modelcontextprotocol.io/) server that lets AI agents query their own [AgentAudit](https://agentaudit.dev) compliance trail.

Agents can review their recent actions, check risk summaries, and dry-run risk checks before executing.

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

## Links

- [Documentation](https://docs.agentaudit.dev)
- [GitHub](https://github.com/dorianganessa/agentaudit)

## License

Apache 2.0
