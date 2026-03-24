# AgenticAudit Cowork Plugin

Compliance monitoring for Claude Cowork — automatically logs, classifies, and audits every action knowledge workers take.

## What it does

When installed, every Cowork action is automatically captured by AgenticAudit:
- Connector access (Google Drive, Salesforce, DocuSign, etc.)
- File operations (read, write, delete)
- Web browsing
- Sub-agent coordination

Each action is classified for risk (low/medium/high/critical), checked for PII, and mapped to compliance frameworks (GDPR, AI Act, SOC 2).

## Prerequisites

1. AgenticAudit server running (self-hosted or cloud)
2. `agentaudit-hook` CLI installed: `pip install agentic-audit`
3. Environment variables set:
   ```bash
   export AGENTAUDIT_API_KEY="aa_live_xxxxx"
   export AGENTAUDIT_BASE_URL="http://localhost:8000"  # or your cloud URL
   ```

## Install

### For individual users

In Claude Code or Cowork:
```
/plugin install github:dorianganessa/agentic-audit --path plugins/cowork
```

### For enterprise admins

Add to your organization's private plugin marketplace for auto-install across all users. See [Enterprise Setup Guide](../../docs/guides/enterprise-deployment.md).

## Verify it works

1. Open Cowork and do any action (read a file, use a connector)
2. Check the AgenticAudit dashboard at http://localhost:8000/dashboard
3. You should see events appearing in real time

## Configuration

The plugin uses the organization's policy set in AgenticAudit. No per-user configuration needed.

Policy levels: minimal, standard, full, paranoid. Set via API or dashboard.

## License

AGPL-3.0
