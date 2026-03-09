# Claude Code Integration

AgentAudit integrates with Claude Code via deterministic hooks. Every tool call — file reads, writes, shell commands, web fetches — is logged, classified, and audit-ready without any token overhead.

## Prerequisites

- AgentAudit API running ([quickstart](../getting-started/quickstart.md))
- `agentaudit-hook` CLI installed (`pip install agentic-audit`)
- Environment variables set:

```bash
export AGENTAUDIT_API_KEY="aa_live_xxxxx"
export AGENTAUDIT_BASE_URL="http://localhost:8000"
```

## Setup hooks

Add this to your Claude Code settings file:

=== "User settings (~/.claude/settings.json)"

    ```json
    {
      "hooks": {
        "PreToolUse": [
          {
            "matcher": "",
            "hooks": [
              {
                "type": "command",
                "command": "agentaudit-hook pre"
              }
            ]
          }
        ],
        "PostToolUse": [
          {
            "matcher": "",
            "hooks": [
              {
                "type": "command",
                "command": "agentaudit-hook post"
              }
            ]
          }
        ],
        "SessionStart": [
          {
            "matcher": "",
            "hooks": [
              {
                "type": "command",
                "command": "agentaudit-hook session-start"
              }
            ]
          }
        ],
        "SessionEnd": [
          {
            "matcher": "",
            "hooks": [
              {
                "type": "command",
                "command": "agentaudit-hook session-end"
              }
            ]
          }
        ]
      }
    }
    ```

=== "Project settings (.claude/settings.json)"

    Same format, placed in the project root. Project-level hooks apply only to that repository.

### Hook types explained

| Hook | When it fires | What AgentAudit does |
|---|---|---|
| `PreToolUse` | Before a tool executes | Sends the event to the API. In paranoid mode, may block the action (exit code 2). |
| `PostToolUse` | After a tool completes | Logs the outcome including exit codes and results. |
| `SessionStart` | When a Claude Code session begins | Logs session start for timeline tracking. |
| `SessionEnd` | When a session ends | Logs session end and triggers summary generation. |

## Verify it works

1. Open Claude Code in any project
2. Ask it to do something (e.g., "list files in the current directory")
3. Open the dashboard at `http://localhost:8000/dashboard`
4. Your event should appear in the timeline with a risk level badge

## What gets captured

The hook CLI maps every Claude Code tool to an AgentAudit action:

| Claude Code Tool | AgentAudit Action | Data Extracted |
|---|---|---|
| `Bash` | `shell_command` | command, working_dir, exit_code |
| `Write` | `file_write` | file_path |
| `Edit` / `MultiEdit` | `file_edit` | file_path |
| `Read` | `file_read` | file_path |
| `WebFetch` | `web_fetch` | url |
| `WebSearch` | `web_search` | query |
| `Task` (sub-agent) | `sub_agent_spawn` | task description |
| `mcp__*` (MCP tools) | `connector_access` | connector, operation, args |

The mapper parses MCP tool names (e.g., `mcp__google_drive__read_file`) into structured connector/operation data.

## Zero token overhead

Claude Code hooks run as external shell commands. They receive the tool call context via stdin and communicate back via exit codes. The hook process is completely invisible to the LLM — no system prompt injection, no extra context, no token cost.

The hooks are deterministic: every tool call triggers the hook, regardless of what the LLM "decides." This makes the audit trail tamper-proof from the LLM's perspective.

!!! tip "Enterprise deployment"
    Push the hooks config via Claude Code enterprise policy settings.
    Developers cannot override or remove hooks set at the enterprise level.
    See [Enterprise deployment](../guides/enterprise-deployment.md) for details.

!!! warning "Paranoid mode"
    When blocking is enabled, high-risk actions are stopped *before* execution.
    The `PreToolUse` hook returns exit code 2, which tells Claude Code to abort the tool call.
    Make sure your API is reliable — the hook defaults to "allow" if the API is unreachable.
    See [Configure paranoid mode](../guides/paranoid-mode.md).

## Local buffering

If the AgentAudit API is unreachable, the hook CLI buffers events locally at `~/.agentaudit/buffer.jsonl`. Events are stored in JSON Lines format and can be replayed when the API is back online.

This ensures zero data loss even during API downtime. The hook never blocks Claude Code when the API is down — it falls through with exit code 0 (allow).

## Troubleshooting

**Hook doesn't fire:**

- Check that the `agentaudit-hook` CLI is on your `PATH`:
  ```bash
  which agentaudit-hook
  ```
- Verify the settings file is valid JSON
- Run Claude Code with debug logging: `claude --debug`

**API unreachable:**

- Check the API is running: `curl http://localhost:8000/health`
- Verify `AGENTAUDIT_BASE_URL` is set correctly
- Check `~/.agentaudit/buffer.jsonl` for buffered events

**Events not appearing in dashboard:**

- Check the API key matches: `echo $AGENTAUDIT_API_KEY`
- Check the policy logging level — in `minimal` mode, only PII events are stored
- Try `full` or `paranoid` logging level to capture everything

## Next steps

- [Cowork integration](cowork.md) — audit Cowork sessions
- [Policy system](../concepts/policy-system.md) — configure what gets logged
- [Paranoid mode](../guides/paranoid-mode.md) — enable blocking
- [Audit a Claude Code session](../guides/audit-claude-code-session.md) — end-to-end tutorial
