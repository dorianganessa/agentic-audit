# AgenticAudit Hook CLI

CLI for auditing [Claude Code](https://docs.agentaudit.dev/integrations/claude-code/) and [Cowork](https://docs.agentaudit.dev/integrations/cowork/) sessions automatically.

Every tool call — file reads, writes, shell commands, web fetches — is logged, classified, and audit-ready with zero token overhead.

## Install

```bash
pip install agentic-audit-hook
```

## Setup

Add hooks to Claude Code:

```json
// ~/.claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {"type": "command", "command": "agentaudit-hook pre"}
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {"type": "command", "command": "agentaudit-hook post"}
        ]
      }
    ]
  }
}
```

Set environment variables:

```bash
export AGENTAUDIT_API_KEY="aa_live_xxxxx"
export AGENTAUDIT_BASE_URL="http://localhost:8000"
```

## Commands

| Command | Hook | Description |
|---|---|---|
| `agentaudit-hook pre` | PreToolUse | Classify risk, optionally block |
| `agentaudit-hook post` | PostToolUse | Log completion |
| `agentaudit-hook session-start` | SessionStart | Log session start |
| `agentaudit-hook session-end` | SessionEnd | Log session end |

## Links

- [Claude Code integration guide](https://docs.agentaudit.dev/integrations/claude-code/)
- [Cowork integration guide](https://docs.agentaudit.dev/integrations/cowork/)
- [GitHub](https://github.com/dorianganessa/agentic-audit)

## License

Apache 2.0
