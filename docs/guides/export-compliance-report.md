# Export a Compliance Report

Generate a PDF compliance report for auditors, containing event summaries, risk breakdowns, and framework coverage.

## Generate from the dashboard

1. Open the dashboard at `http://localhost:8000/dashboard/stats`
2. Optionally filter by date range using the date pickers
3. Click **Export PDF**

The PDF downloads immediately as `agentaudit_compliance_report.pdf`.

## Generate via API

```bash
curl -o report.pdf "http://localhost:8000/dashboard/report/pdf?after=2025-01-01&before=2025-02-01" \
  -H "Authorization: Bearer aa_live_xxxxx"
```

### Query parameters

| Parameter | Type | Description |
|---|---|---|
| `after` | `date` | Start of reporting period (ISO 8601) |
| `before` | `date` | End of reporting period (ISO 8601) |

## What the report contains

The PDF includes these sections:

### Header
- Organization name
- Report generation timestamp
- Reporting period

### Summary statistics
- Total events processed
- Events by risk level (low, medium, high, critical)
- Total PII events detected

### Framework coverage
- Which GDPR articles were triggered and how many times
- Which AI Act articles were triggered and how many times
- Which SOC 2 controls were triggered and how many times

### Top risky events
- The most significant events during the period
- Event details: action, agent, risk level, PII, frameworks
- Sorted by risk level (critical first)

### Footer
- Report ID for traceability
- Generation metadata

## Scheduling reports

For periodic compliance reporting, set up a cron job:

```bash
# Generate monthly report on the 1st of each month
0 9 1 * * curl -o "/reports/agentaudit_$(date +\%Y\%m).pdf" \
  "http://localhost:8000/dashboard/report/pdf?after=$(date -d '-1 month' +\%Y-\%m-01)&before=$(date +\%Y-\%m-01)" \
  -H "Authorization: Bearer aa_live_xxxxx"
```

## Next steps

- [Audit a Claude Code session](audit-claude-code-session.md) — see what generates events
- [Framework mapping](../concepts/framework-mapping.md) — understand which articles are triggered
