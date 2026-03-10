# Hooks Architecture

AgenticAudit uses deterministic hooks — not MCP, not system prompts — to capture agent actions. This page explains why, and how the hook system works.

## Why hooks, not MCP

MCP (Model Context Protocol) is designed for LLM-to-tool communication. It runs inside the LLM's context window, meaning:

- The LLM can choose not to call the MCP tool
- MCP calls consume tokens
- The LLM can tamper with the audit data

Hooks are fundamentally different:

| | Hooks | MCP |
|---|---|---|
| **Trigger** | Every tool call, deterministically | LLM decides when to call |
| **Token cost** | Zero | Tokens per call |
| **Tamper-proof** | LLM cannot see or modify hook behavior | LLM controls the input |
| **Blocking** | Can prevent tool execution (exit code 2) | Cannot block other tools |
| **Visibility** | Invisible to the LLM | Part of the conversation |

!!! tip "AgenticAudit also has an MCP server"
    The [MCP server](../integrations/rest-api.md) exists for a different purpose: **agent self-awareness**.
    It lets the agent query its own audit trail and check risk levels.
    It does not replace hooks for logging — both serve complementary roles.

## Hook flow

Here's what happens when Claude Code or Cowork calls a tool:

```
1. Claude Code decides to use a tool (e.g., Bash)
       │
2. PreToolUse hook fires
       │
       ├─► agentaudit-hook pre
       │     │
       │     ├─ Reads tool context from stdin (JSON)
       │     ├─ Maps tool_name to action (e.g., Bash → shell_command)
       │     ├─ Sends event to AgenticAudit API
       │     ├─ API returns: risk_level, pii_detected, decision
       │     │
       │     ├─ If decision == "allow" → exit code 0
       │     └─ If decision == "block" → exit code 2 (tool aborted)
       │
3. Tool executes (if not blocked)
       │
4. PostToolUse hook fires
       │
       └─► agentaudit-hook post
             │
             ├─ Reads tool result from stdin
             ├─ Logs completion event with outcome
             └─ exit code 0
```

## stdin JSON format

Claude Code passes tool context to hooks via stdin. The format:

### PreToolUse

```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "ls -la /tmp",
    "description": "List files in /tmp"
  },
  "session_id": "abc123",
  "hook_event_name": "PreToolUse"
}
```

### PostToolUse

```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "ls -la /tmp"
  },
  "tool_output": "total 8\ndrwxrwxrwt  2 root root ...",
  "session_id": "abc123",
  "hook_event_name": "PostToolUse"
}
```

### What the hook CLI adds

The hook CLI enriches every event with **user identity** before sending to the API:

| Field | Source | Example |
|---|---|---|
| `os_user` | Auto-detected via OS | `alice` |
| `hostname` | Auto-detected via OS | `alice-macbook` |
| `user_email` | `AGENTAUDIT_USER_EMAIL` env var | `alice@company.com` |
| `user_id` | `AGENTAUDIT_USER_ID` env var | `emp-12345` |
| `session_id` | From stdin JSON | `abc123` |

This identity data appears in the dashboard **User** column, making it possible to trace exactly who triggered a PII-flagged or high-risk action.

## Tool-to-action mapping

The hook CLI's mapper translates Claude Code tool names to AgenticAudit actions:

| Tool Name | Action | Data Keys |
|---|---|---|
| `Bash` | `shell_command` | `command`, `working_dir`, `exit_code` |
| `Write` | `file_write` | `file_path` |
| `Edit` / `MultiEdit` | `file_edit` | `file_path` |
| `Read` | `file_read` | `file_path` |
| `WebFetch` | `web_fetch` | `url` |
| `WebSearch` | `web_search` | `query` |
| `Task` | `sub_agent_spawn` | task description |
| `mcp__*` | `connector_access` | `connector`, `operation`, `args` |

For MCP tools, the mapper parses the triple-underscore naming convention:

```
mcp__google_drive__read_file
      └─ connector    └─ operation
```

## Local buffering

When the API is unreachable, the hook CLI buffers events to `~/.agentaudit/buffer.jsonl`:

```
{"timestamp": "...", "action": "shell_command", "data": {...}}
{"timestamp": "...", "action": "file_write", "data": {...}}
```

The hook always returns exit code 0 (allow) when buffering, so the developer's workflow is never interrupted by API downtime.

## Zero token overhead

Because hooks run as external shell processes:

1. They are not part of the LLM's system prompt
2. They don't inject text into the conversation
3. They don't appear in the context window
4. The LLM has no knowledge of their existence

This means adding AgenticAudit to Claude Code costs exactly **zero additional tokens per session**. The audit layer is completely transparent to the LLM.

## Exit codes

| Code | Meaning | Effect |
|---|---|---|
| `0` | Allow | Tool executes normally |
| `2` | Block | Claude Code/Cowork aborts the tool call |
| Other | Error | Treated as allow (fail-open) |

## Next steps

- [Claude Code integration](../integrations/claude-code.md) — set up hooks
- [Cowork integration](../integrations/cowork.md) — native OTLP integration
- [Policy system](policy-system.md) — configure blocking rules
