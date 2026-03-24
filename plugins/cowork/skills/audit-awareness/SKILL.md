---
name: audit-awareness
description: AgenticAudit is monitoring this session. Every action you take is logged, classified for risk, and mapped to compliance frameworks (GDPR, AI Act, SOC 2). You don't need to do anything — logging happens automatically via hooks. But be aware that high-risk actions (accessing sensitive files, PII queries, credential access) are flagged and may be blocked depending on the organization's policy.
---

# AgenticAudit — Compliance Monitoring Active

This session is being monitored by AgenticAudit for compliance purposes.

## What's being logged

Every tool call you make is automatically captured:
- File reads and writes (especially sensitive paths like HR, Finance, Legal folders)
- Connector access (Google Drive, Salesforce, DocuSign, etc.)
- Web browsing via Claude in Chrome
- Shell commands and code execution
- Sub-agent spawns and their actions

## What you should know

- **You don't need to log anything yourself.** Hooks fire automatically on every action.
- **Risk levels are assigned automatically:** low, medium, high, critical.
- **PII is detected automatically** in file names, paths, content, and connector queries.
- **If an action is blocked**, it means the organization's policy flagged it as too risky. Inform the user and suggest an alternative approach.
- **If the user asks about the audit trail**, you can query it using the AgenticAudit MCP tools (if configured): `get_my_audit_events`, `get_session_risk_summary`, `check_action_risk`.

## When to be extra cautious

- Files in paths containing: HR, Confidential, Finance, Legal, Compensation, Personnel, Salary
- Connector queries that access personal data (names, emails, phone numbers, addresses, salaries)
- Any operation involving credentials, API keys, or secrets
- Bulk data operations (exporting large datasets from connectors)

If you detect you're about to perform a high-risk action, consider informing the user before proceeding.
