# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-03-24

### Changed

- **License** — Changed from Apache-2.0 to AGPL-3.0
- **Blocked events are no longer stored** — Events with `decision="block"` are returned to the caller but not persisted to the database

### Fixed

- **Policy update race condition** — Added optimistic locking (version column) to prevent concurrent policy updates from losing writes. Concurrent conflicts return HTTP 409.
- **Dead documentation link** — Fixed broken enterprise setup guide link in Cowork plugin README

### Added

- **CrewAI Integration** — Event listener for CrewAI agents that logs agent execution and tool usage events
- **DCO requirement** — Contributions now require Developer Certificate of Origin sign-off
- **GitHub issue templates** — Structured bug report and feature request forms
- **PR template** — Pull request checklist with test/lint/DCO checks
- **`.mcp.json.example`** — Template for MCP server configuration (`.mcp.json` is now gitignored)

## [0.2.0] - 2026-03-23

### Added

- **AI Systems Registry** — CRUD API for registering and managing AI systems with risk classification, Annex III categories, vendor contract tracking, and FRIA status (`POST/GET/PUT/DELETE /v1/systems`)
- **Agent ID Pattern Matching** — Link systems to events retroactively via wildcard patterns (`agent_id_patterns`), with event listing and stats per system
- **Classification Suggestion** — Heuristic engine that analyzes event patterns (PII ratios, risk distributions, keyword matching) to suggest AI Act risk classification and Annex III category (`GET /v1/systems/{id}/classification-suggestion`)
- **Compliance Status API** — AI Act compliance scoring (0–100%) based on 5 checks: all classified, no prohibited, FRIA complete, contracts reviewed, retention compliant (`GET /v1/compliance/ai-act/status`)
- **Compliance Report PDF** — Org-wide AI Act compliance report with systems inventory, risk distribution, FRIA status, vendor contracts, and governance sections (`GET /v1/compliance/ai-act/report`)
- **FRIA PDF Generation** — Pre-filled Fundamental Rights Impact Assessment for high-risk systems, with employment-specific rights sections and `[HUMAN REVIEW REQUIRED]` markers (`GET /v1/compliance/ai-act/fria/{id}/pdf`)
- **Compliance Dashboard** — Web UI page showing compliance score, checks, systems inventory, upcoming deadlines, and PDF download links (`/dashboard/compliance`)
- **Retention Enforcement** — `compliance_preset: "ai_act"` in org policy automatically enforces 180-day minimum retention (Art 12)
- **Policy Fields** — Added `compliance_preset` and `retention_days` to org policy
- **API Key Rotation** — `POST /v1/org/api-keys/rotate` generates a new key and deactivates the old one
- **MCP Tools** — `list_ai_systems`, `get_compliance_status`, `suggest_classification` added to MCP server

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
