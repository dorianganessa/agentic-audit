# Configuration

All configuration is done via environment variables.

## API server

These variables configure the AgenticAudit API server.

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
| `AGENTAUDIT_BASE_URL` | `http://localhost:8000` | AgenticAudit API endpoint URL |
| `AGENTAUDIT_USER_EMAIL` | *(optional)* | User email for event attribution — appears in the dashboard User column |
| `AGENTAUDIT_USER_ID` | *(optional)* | User ID for event attribution (e.g., employee ID, SSO ID) |

!!! tip "Automatic identity"
    Even without setting `AGENTAUDIT_USER_EMAIL` or `AGENTAUDIT_USER_ID`, the hook CLI
    automatically captures the **OS username** and **hostname** with every event.
    The explicit env vars are recommended for enterprise deployments where you need
    email-level attribution for compliance.

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

# Optional: user identity for dashboard attribution
export AGENTAUDIT_USER_EMAIL="you@company.com"
```

This way, every terminal session and Claude Code hook has access to the credentials and user identity.

## Next steps

- [Policy system](../concepts/policy-system.md) — configure logging levels, alerts, and blocking rules via the API
- [Claude Code integration](../integrations/claude-code.md) — hook configuration
