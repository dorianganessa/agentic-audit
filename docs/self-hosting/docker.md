# Docker Deployment

AgenticAudit ships with a Docker Compose configuration for both development and production use.

## Quick start

```bash
git clone https://github.com/dorianganessa/agentic-audit.git
cd agentic-audit
docker compose up -d
```

This starts two services:

| Service | Image | Port | Purpose |
|---|---|---|---|
| `api` | Built from `Dockerfile` | `8000` | API server + dashboard |
| `db` | `postgres:16-alpine` | `5432` | PostgreSQL database |

## Startup flow

1. PostgreSQL starts and passes its health check (`pg_isready`)
2. The API container runs Alembic migrations
3. A seed script creates the default organization and API key
4. Uvicorn starts the API on `0.0.0.0:8000`

Retrieve the default API key:

```bash
docker compose logs api | grep "Default API key"
```

## Services

### API server

The API container:

- Runs Alembic migrations on startup (safe to run multiple times)
- Seeds a default organization and API key on first run
- Serves the REST API and HTMX dashboard
- Health check: `GET /health`

### PostgreSQL

- Image: `postgres:16-alpine`
- Data persisted in a Docker volume (`pgdata`)
- Health check: `pg_isready` every 5 seconds

## Environment variables

Override defaults with a `.env` file or inline:

```bash
# .env
AGENTAUDIT_DATABASE_URL=postgresql+psycopg2://agentaudit:strongpassword@db:5432/agentaudit
POSTGRES_PASSWORD=strongpassword
```

See [Configuration](../getting-started/configuration.md) for all available variables.

## Production considerations

### Use a managed database

For production, replace the Docker PostgreSQL with a managed instance:

```yaml
# docker-compose.prod.yml
services:
  api:
    environment:
      AGENTAUDIT_DATABASE_URL: "postgresql+psycopg2://user:pass@your-rds-instance.amazonaws.com:5432/agentaudit"
    depends_on: []  # No local db dependency
```

Run with:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d api
```

### TLS

Terminate TLS at a reverse proxy (nginx, Caddy, or a cloud load balancer) in front of the API container.

### Backups

If using the Docker PostgreSQL, back up the volume:

```bash
docker compose exec db pg_dump -U agentaudit agentaudit > backup_$(date +%Y%m%d).sql
```

To restore:

```bash
cat backup_20250115.sql | docker compose exec -T db psql -U agentaudit agentaudit
```

### Resource limits

For production, add resource limits:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
```

## Logs

```bash
# All services
docker compose logs -f

# API only
docker compose logs -f api

# Database only
docker compose logs -f db
```

## Stop and clean up

```bash
# Stop services (data preserved)
docker compose down

# Stop and remove volumes (destroys data)
docker compose down -v
```

## Next steps

- [Database](database.md) — PostgreSQL schema and requirements
- [Upgrading](upgrading.md) — how to update to new versions
- [Configuration](../getting-started/configuration.md) — all environment variables
