# Cowork Integration Guide

## Overview

The AgentAudit Cowork plugin monitors every action knowledge workers take in Claude Cowork — connector access, file operations, web browsing, and sub-agent coordination.

Anthropic's own audit tools (Audit Logs, Compliance API, Data Exports) do NOT capture Cowork activity. AgentAudit fills this gap.

## How it works

The plugin installs deterministic hooks that fire on every tool call Cowork makes. The same `agentaudit-hook` CLI used for Claude Code handles the event capture. No additional infrastructure needed.

## Individual Setup

1. Install AgentAudit (self-hosted or cloud)
2. Install the hook CLI: `pip install agentaudit`
3. Set environment variables in your shell profile
4. Install the plugin: `/plugin install github:adrianosanges/agentaudit --path plugins/cowork`
5. Open Cowork and verify events appear in the dashboard

## Enterprise Setup

Enterprise admins can deploy the plugin to all users automatically:

1. Set up AgentAudit (self-hosted or cloud)
2. Configure your organization's policy (logging level, frameworks, alert rules)
3. Add the AgentAudit plugin to your private plugin marketplace
4. Enable auto-install for all users (or specific teams)
5. Distribute API keys per team (each key maps to a team policy)

Once deployed, every Cowork session across the organization is audited. Users don't need to do anything — the plugin is invisible.

## What gets captured

| Cowork Action | AgentAudit Event Type | Example |
|---|---|---|
| Read local file | file_read | Reading ~/Documents/report.docx |
| Write local file | file_write | Creating ~/Reports/analysis.xlsx |
| Delete local file | file_delete | Removing temp files |
| Google Drive access | connector_access | Reading "Q3 Revenue.xlsx" from Drive |
| Salesforce query | connector_access | SELECT Name, Email FROM Contact |
| DocuSign operation | connector_access | Creating envelope for signing |
| Gmail access | connector_access | Reading/drafting emails |
| Web browsing | web_browse | Visiting glassdoor.com/salaries |
| Web search | web_search | Searching for market data |
| Sub-agent spawn | sub_agent_spawn | Parallelizing research tasks |
| Shell command | shell_command | Running Python scripts |

## Risk scoring for Cowork

Cowork sessions often involve more sensitive data than coding sessions. The risk scoring engine applies additional rules:

- Files in HR/Finance/Legal/Confidential folders → HIGH
- Connector queries containing personal data fields → HIGH
- Bulk data exports from connectors → HIGH
- Compensation, salary, or performance review data → CRITICAL
- Credential or secret access → CRITICAL

## Compliance mapping

Cowork actions map to the same frameworks as Claude Code:

- **GDPR Art. 30** — Any connector access involving personal data
- **GDPR Art. 15** — Reading customer/employee records
- **GDPR Art. 22** — Automated decision-making with reasoning
- **AI Act Art. 14** — Any agent action (human oversight)
- **SOC 2 CC6.1** — Connector access, file operations
- **SOC 2 CC6.5** — Data classification (PII detection)
