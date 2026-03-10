# Installation

AgenticAudit can be installed in three ways depending on your use case.

## Docker Compose (recommended)

The fastest way to get the full stack — API server, dashboard, and PostgreSQL.

**Prerequisites:** Docker and Docker Compose installed.

```bash
git clone https://github.com/dorianganessa/agentic-audit.git
cd agentic-audit
docker compose up -d
```

This starts:

- **API server** on `http://localhost:8000`
- **Dashboard** on `http://localhost:8000/dashboard`
- **PostgreSQL 16** on `localhost:5432`

On first run, the API creates a default organization and API key. Retrieve it:

```bash
docker compose logs api | grep "Default API key"
```

## pip (SDK + hook CLI only)

If you already have a PostgreSQL database and want to run the API server separately, or you only need the SDK and hook CLI:

**Prerequisites:** Python 3.12+

```bash
pip install agentic-audit
```

This installs:

- **`agentic-audit` Python SDK** — log events programmatically
- **`agentic-audit-hook` CLI** — Claude Code and Cowork hook integration

The SDK connects to a running AgenticAudit API. Set the connection:

```bash
export AGENTAUDIT_API_KEY="aa_live_xxxxx"
export AGENTAUDIT_BASE_URL="http://localhost:8000"
```

To also install the API server via pip:

```bash
pip install agentic-audit-api
```

Then run it:

```bash
agentaudit-api
```

!!! note "External PostgreSQL required"
    When installing via pip, you need to provide your own PostgreSQL database.
    Set `AGENTAUDIT_DATABASE_URL` to your connection string.

## From source (contributors)

**Prerequisites:** Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/dorianganessa/agentic-audit.git
cd agentic-audit
uv sync
```

This installs all workspace packages in development mode:

- `packages/api` — FastAPI server
- `packages/sdk` — Python SDK
- `packages/hook-cli` — Hook CLI
- `packages/mcp-server` — MCP server

Run the API server locally:

```bash
uv run uvicorn agentaudit_api.main:create_app --factory --reload
```

Run tests:

```bash
uv run pytest
```

## Verify installation

```python
import agentaudit
print(agentaudit.__version__)
```

Or check the hook CLI:

```bash
agentaudit-hook --help
```

## Next steps

- [Configuration](configuration.md) — all environment variables
- [Quickstart](quickstart.md) — log your first event
