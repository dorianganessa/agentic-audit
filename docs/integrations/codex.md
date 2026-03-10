# Codex Integration

AgenticAudit provides partial support for OpenAI Codex through transcript parsing.

!!! warning "Partial support"
    Codex does not currently offer pre/post execution hooks or a callback system.
    AgenticAudit integration relies on parsing session transcripts after the fact.
    This means **real-time blocking is not available** for Codex.

## How it works

AgenticAudit provides a transcript parser that processes Codex session logs and extracts tool calls, converting them into audit events.

```python
from agentaudit.integrations.codex import parse_codex_transcript

events = parse_codex_transcript(
    transcript_path="~/.codex/sessions/latest.json",
    api_key="aa_live_xxxxx",
    base_url="http://localhost:8000",
)

print(f"Parsed {len(events)} events")
for event in events:
    print(f"  {event.action}: {event.risk_level}")
```

## What gets captured

| Codex Action | AgenticAudit Action | Notes |
|---|---|---|
| Shell commands | `shell_command` | Extracted from transcript |
| File writes | `file_write` | Detected from apply patches |
| File reads | `file_read` | Detected from context loading |

## Limitations

- **Post-hoc only**: Events are parsed after the session ends, not in real time
- **No blocking**: Cannot prevent high-risk actions since there are no pre-execution hooks
- **Transcript format**: Depends on Codex's internal transcript format, which may change

## Automating transcript ingestion

Run the parser on a schedule to continuously ingest Codex sessions:

```bash
# Add to crontab
*/5 * * * * agentaudit-codex-ingest --watch ~/.codex/sessions/
```

## The path forward

We are tracking the Codex governance hooks proposal. When Codex adds native hook support, AgenticAudit will provide a real-time integration similar to the [Claude Code integration](claude-code.md).

## Next steps

- [Claude Code integration](claude-code.md) — full real-time hook support
- [REST API](rest-api.md) — integrate any agent directly
