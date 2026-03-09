# Audit a Claude Code Session

This guide walks you through auditing a complete Claude Code session — from setting up hooks to viewing the classified events in the dashboard.

## Prerequisites

- AgentAudit running locally (`docker compose up -d`)
- `agentaudit-hook` CLI installed (`pip install agentic-audit`)
- API key from `docker compose logs api | grep "Default API key"`

## Step 1: Configure hooks

Add the hooks to your Claude Code settings:

```json title="~/.claude/settings.json"
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
    ]
  }
}
```

Set environment variables in your shell profile:

```bash
export AGENTAUDIT_API_KEY="aa_live_xxxxx"
export AGENTAUDIT_BASE_URL="http://localhost:8000"
```

## Step 2: Run a Claude Code session

Open Claude Code in any project and give it a task. For example:

> "Read the README, check the test files, and add a new test for the login function."

Claude Code will use several tools: `Read` to read files, `Bash` to run tests, `Write` or `Edit` to create the test file. Each tool call fires the hooks.

## Step 3: View events in the dashboard

Open [http://localhost:8000/dashboard](http://localhost:8000/dashboard).

You'll see a timeline of events from your session:

- **file_read** events for each file Claude Code read (risk: low)
- **shell_command** events for test runs (risk: low–medium)
- **file_write** or **file_edit** events for code changes (risk: low–high depending on the file)

Each event shows:

- Risk level badge (color-coded)
- PII detection indicator
- Mapped compliance frameworks
- Timestamp

## Step 4: Inspect an event

Click on any event to see the full detail:

- **Action**: What was done (e.g., `shell_command`)
- **Data**: The specific details (e.g., the command that was run)
- **Risk level**: Why it was scored at that level
- **PII fields**: Any personal data detected
- **Frameworks**: Which GDPR/AI Act/SOC 2 articles apply

## Step 5: Filter by session

Use the session filter in the dashboard to isolate events from a specific Claude Code session. This gives you a complete audit trail for that work session.

## Step 6: Export a compliance report

Go to the stats page at [http://localhost:8000/dashboard/stats](http://localhost:8000/dashboard/stats) and click **Export PDF**. The report includes:

- Summary statistics (total events, risk breakdown)
- Framework coverage (which articles were triggered)
- Top risky events with details

See [Export a compliance report](export-compliance-report.md) for more details.

## What you learned

- Claude Code hooks fire on every tool call without any token overhead
- Events are classified in real time with risk levels and PII detection
- The dashboard provides a filterable timeline of all agent actions
- Compliance reports can be exported for auditors

## Next steps

- [Set up Slack alerts](slack-alerts.md) — get notified on high-risk events
- [Configure paranoid mode](paranoid-mode.md) — block risky actions in real time
- [Policy system](../concepts/policy-system.md) — tune what gets logged
