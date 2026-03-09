# Contributing to AgentAudit

Thank you for your interest in contributing! This guide will help you get started.

## Development Setup

**Prerequisites:** Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker (for Postgres).

```bash
# Clone the repo
git clone https://github.com/adrianosanges/agentaudit.git
cd agentaudit

# Install dependencies
uv sync

# Start Postgres
docker compose up db -d

# Run migrations
cd packages/api
AGENTAUDIT_DATABASE_URL=postgresql+psycopg2://agentaudit:agentaudit@localhost:5432/agentaudit \
  uv run alembic -c src/agentaudit_api/alembic.ini upgrade head

# Seed default API key
uv run python -m agentaudit_api.seed

# Start the API server
cd ../..
uv run uvicorn agentaudit_api.main:app --host 0.0.0.0 --port 8000 --reload
```

## Running Tests

Tests use `testcontainers` to spin up a real Postgres instance — Docker must be running.

```bash
uv run pytest tests/ -v
```

## Code Style

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
# Check
uv run ruff check .
uv run ruff format --check .

# Fix
uv run ruff check --fix .
uv run ruff format .
```

Key settings (from `pyproject.toml`):
- Target: Python 3.12
- Line length: 100
- Rules: E, F, I, N, UP, B, SIM

## Project Structure

```
packages/
├── api/          # FastAPI server, dashboard, PDF reports
├── sdk/          # Python SDK, LangChain & Codex integrations
├── hook-cli/     # Claude Code hooks CLI
└── mcp-server/   # MCP server for agent self-awareness
```

## Pull Request Process

1. Fork the repo and create a branch from `main`.
2. Add tests for new functionality.
3. Ensure all tests pass: `uv run pytest tests/ -v`
4. Ensure linting passes: `uv run ruff check . && uv run ruff format --check .`
5. Update documentation if you changed public APIs.
6. Open a PR with a clear description of your changes.

## Commit Messages

Use clear, descriptive commit messages:
- `fix: resolve PII detection false positive for IPv6`
- `feat: add webhook retry with exponential backoff`
- `docs: update self-hosting guide for ARM64`

## Reporting Issues

Use GitHub Issues. Include:
- Steps to reproduce
- Expected vs actual behavior
- Python version, OS, Docker version

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
