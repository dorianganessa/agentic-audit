# Configuration

All configuration is done via environment variables.

## API server

These variables configure the AgentAudit API server.

| Variable | Default | Description |
|---|---|---|
| `AGENTAUDIT_DATABASE_URL` | `postgresql+psycopg2://agentaudit:agentaudit@localhost:5432/agentaudit` | PostgreSQL connection string |
| `AGENTAUDIT_API_HOST` | `0.0.0.0` | API server bind host |
| `AGENTAUDIT_API_PORT` | `8000` | API server bind port |
| `AGENTAUDIT_DEBUG` | `false` | Enable debug mode (verbose logging, stack traces) |
| `AGENTAUDIT_LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

## SDK and hook CLI

These variables configure the Python SDK and the `agentaudit-hook` CLI.

| Variable | Default | Description |
|---|---|---|
| `AGENTAUDIT_API_KEY` | *(required)* | API key for authentication (`aa_live_` prefix) |
| `AGENTAUDIT_BASE_URL` | `http://localhost:8000` | AgentAudit API endpoint URL |

## Docker Compose defaults

When using Docker Compose, the following defaults are pre-configured in `docker-compose.yml`:

| Service | Variable | Value |
|---|---|---|
| `api` | `AGENTAUDIT_DATABASE_URL` | `postgresql+psycopg2://agentaudit:agentaudit@db:5432/agentaudit` |
| `api` | `AGENTAUDIT_API_HOST` | `0.0.0.0` |
| `api` | `AGENTAUDIT_API_PORT` | `8000` |
| `db` | `POSTGRES_DB` | `agentaudit` |
| `db` | `POSTGRES_USER` | `agentaudit` |
| `db` | `POSTGRES_PASSWORD` | `agentaudit` |

!!! warning "Change defaults in production"
    The default database credentials are intended for local development only.
    In production, set strong credentials and use a managed PostgreSQL instance.

## .env file

Copy the example and customize:

```bash
cp .env.example .env
```

The API server reads from `.env` automatically via `pydantic-settings`.

## Shell profile

For the SDK and hook CLI, add to your shell profile (`~/.zshrc`, `~/.bashrc`):

```bash
export AGENTAUDIT_API_KEY="aa_live_xxxxx"
export AGENTAUDIT_BASE_URL="http://localhost:8000"
```

This way, every terminal session and Claude Code hook has access to the credentials.

## Next steps

- [Policy system](../concepts/policy-system.md) — configure logging levels, alerts, and blocking rules via the API
- [Claude Code integration](../integrations/claude-code.md) — hook configuration
