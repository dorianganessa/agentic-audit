# Claude Code Integration Guide

## Overview

AgentAudit integrates with Claude Code through deterministic hooks. Every tool call — shell commands, file reads/writes, web fetches — is captured, classified for risk, checked for PII, and mapped to compliance frameworks in real time.

## How it works

Claude Code fires hook events at four points:

| Hook Event     | When it fires                    | What AgentAudit does                              |
|----------------|----------------------------------|---------------------------------------------------|
| `PreToolUse`   | Before a tool executes           | Risk check; block if paranoid policy triggers      |
| `PostToolUse`  | After a tool completes           | Log event with full context and tool output        |
| `SessionStart` | When a Claude Code session opens | Log session start with session ID                  |
| `SessionEnd`   | When a session closes            | Log session end                                    |

## Setup

1. Install the hook CLI:

```bash
pip install agentic-audit
# or
uv pip install agentic-audit
```

2. Set environment variables in your shell profile (`~/.zshrc` or `~/.bashrc`):

```bash
export AGENTAUDIT_API_KEY="aa_live_your_key_here"
export AGENTAUDIT_BASE_URL="http://localhost:8000"
```

3. Configure Claude Code hooks in `~/.claude/hooks.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [{ "type": "command", "command": "agentaudit-hook pre" }]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [{ "type": "command", "command": "agentaudit-hook post" }]
      }
    ],
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [{ "type": "command", "command": "agentaudit-hook session-start" }]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [{ "type": "command", "command": "agentaudit-hook session-end" }]
      }
    ]
  }
}
```

4. Open Claude Code and verify events appear in the dashboard at `http://localhost:8000/dashboard`.

## Tool Mapping

| Claude Code Tool | AgentAudit Action  | Data Extracted                     |
|------------------|--------------------|------------------------------------|
| `Bash`           | `shell_command`    | command, working_dir, exit_code    |
| `Write`          | `file_write`       | file_path                          |
| `Edit` / `MultiEdit` | `file_edit`   | file_path                          |
| `Read`           | `file_read`        | file_path                          |
| `WebFetch`       | `web_fetch`        | url                                |
| `WebSearch`      | `web_search`       | query                              |
| `Task`           | `sub_agent_spawn`  | task_description                   |
| `mcp__*`         | `connector_access` | connector, operation, raw args     |

## Blocking (Paranoid Mode)

When the organization policy is set to `paranoid` with blocking enabled, the `PreToolUse` hook will block actions that exceed the risk threshold. The hook CLI exits with code 2, which tells Claude Code to abort the tool call.

Configure blocking in the policy:

```json
{
  "logging_level": "paranoid",
  "blocking_rules": {
    "enabled": true,
    "block_on": "critical"
  }
}
```

## Offline Buffering

If the AgentAudit API is unreachable, events are buffered locally to `~/.agentaudit/buffer.jsonl`. They can be replayed when connectivity is restored.
