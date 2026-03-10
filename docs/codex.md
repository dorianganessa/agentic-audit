# Codex Integration Guide

## Overview

AgenticAudit can monitor OpenAI Codex sessions by tailing JSONL transcript files. The Codex parser watches `~/.codex/sessions/*.jsonl` for new entries and forwards tool calls to the AgenticAudit API.

## How it works

Codex writes session transcripts as JSONL files. The parser polls for new lines, extracts tool call entries, and maps them to AgenticAudit events.

## Setup

### As a background process

```python
from agentaudit.integrations.codex_parser import CodexTranscriptParser

parser = CodexTranscriptParser(
    api_key="aa_live_your_key_here",
    base_url="http://localhost:8000",
    codex_home="~/.codex",
    agent_id="codex",
    poll_interval=1.0,
)
parser.start()  # Blocks until stopped
```

### As a CLI watcher

```bash
export AGENTAUDIT_API_KEY="aa_live_your_key_here"
export AGENTAUDIT_BASE_URL="http://localhost:8000"

# Run the watcher (blocks, Ctrl+C to stop)
python -c "from agentaudit.integrations.codex_parser import watch_codex; watch_codex()"
```

## Tool Mapping

| Codex Tool    | AgenticAudit Action | Data Extracted |
|---------------|-------------------|----------------|
| `shell`       | `shell_command`   | command        |
| `apply_patch` | `file_edit`       | file_path      |
| `read_file`   | `file_read`       | file_path      |
| `write_file`  | `file_write`      | file_path      |
| `web_fetch`   | `web_fetch`       | tool_name, args|

The parser handles both `tool_call` and `function_call` entry types, and parses arguments from string or dict format.

## Configuration

| Parameter        | Default              | Description                          |
|------------------|----------------------|--------------------------------------|
| `api_key`        | `$AGENTAUDIT_API_KEY`| AgenticAudit API key                   |
| `base_url`       | `$AGENTAUDIT_BASE_URL`| AgenticAudit API URL                 |
| `codex_home`     | `~/.codex`           | Codex home directory                 |
| `agent_id`       | `codex`              | Agent identifier in events           |
| `poll_interval`  | `1.0`                | Seconds between file scans           |

## Context Metadata

Each event includes:

```json
{
  "context": {
    "tool": "codex",
    "session_id": "<from transcript entry>"
  }
}
```
