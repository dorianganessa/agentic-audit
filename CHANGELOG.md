# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-03-09

### Added

- **Core API** — FastAPI server with event ingestion, querying, and statistics
- **PII Detection** — Regex-based detection for emails, IPs, phone numbers, credit cards, API keys, and DB connection strings
- **Risk Scoring** — Rules-based classification into low, medium, high, critical levels
- **Compliance Frameworks** — Automatic mapping to GDPR, EU AI Act, and SOC 2 articles
- **Policy Engine** — Configurable logging levels (minimal, standard, full, paranoid) with optional blocking rules
- **Python SDK** — Sync and async clients for event logging
- **Claude Code Hook CLI** — `agentaudit-hook` for PreToolUse, PostToolUse, SessionStart, SessionEnd hooks
- **Cowork Plugin** — Plugin for Claude Cowork with connector-aware auditing
- **LangChain Integration** — Callback handler for automatic tool/chain auditing
- **Codex Integration** — Transcript parser that tails JSONL session files
- **MCP Server** — Agent self-awareness tools (get_my_audit_events, get_session_risk_summary, check_action_risk)
- **Dashboard** — HTMX-based web UI with event timeline, filters, stats, and policy management
- **PDF Reports** — Downloadable compliance reports with risk breakdowns and framework coverage
- **Slack Alerts** — Configurable webhook alerts based on risk level and action rules
- **Local Buffering** — JSONL fallback when the API is unreachable
- **Docker Compose** — One-command setup with PostgreSQL
- **CI Pipeline** — GitHub Actions with ruff, mypy strict, and pytest (80% coverage threshold)
