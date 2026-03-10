# Self-Hosting Guide

## Overview

AgenticAudit runs as a FastAPI application backed by PostgreSQL. The simplest way to deploy is with Docker Compose.

## Quick Start

```bash
git clone https://github.com/dorianganessa/agentic-audit.git
cd agentic-audit
cp .env.example .env
docker compose up -d
```

The API will be available at `http://localhost:8000`. On first start, a default organization and API key are created — check the logs:

```bash
docker compose logs api | grep "aa_live_"
```

## Docker Compose

The default `docker-compose.yml` includes:

| Service | Image              | Port | Description          |
|---------|--------------------|------|----------------------|
| `api`   | Built from source  | 8000 | AgenticAudit API       |
| `db`    | postgres:16-alpine | 5432 | PostgreSQL database  |

### Startup sequence

1. PostgreSQL starts and passes health check
2. Alembic runs database migrations (`alembic upgrade head`)
3. Seed script creates default org + API key (if none exists)
4. Uvicorn starts the FastAPI application

## Environment Variables

### API Server

| Variable                  | Default                          | Description                    |
|---------------------------|----------------------------------|--------------------------------|
| `AGENTAUDIT_DATABASE_URL` | (required)                       | PostgreSQL connection string   |
| `AGENTAUDIT_API_HOST`     | `0.0.0.0`                        | Bind host                      |
| `AGENTAUDIT_API_PORT`     | `8000`                           | Bind port                      |
| `AGENTAUDIT_DEBUG`        | `false`                          | Enable debug mode              |
| `AGENTAUDIT_LOG_LEVEL`    | `INFO`                           | Log level                      |

### Client / Hook CLI

| Variable               | Default                    | Description            |
|------------------------|----------------------------|------------------------|
| `AGENTAUDIT_API_KEY`   | (required)                 | API key for auth       |
| `AGENTAUDIT_BASE_URL`  | `http://localhost:8000`    | API URL                |

## Production Deployment

### Database

Use a managed PostgreSQL instance (AWS RDS, Cloud SQL, etc.):

```bash
AGENTAUDIT_DATABASE_URL=postgresql+psycopg2://user:pass@your-db-host:5432/agentaudit
```

### Reverse Proxy

Place the API behind a reverse proxy (nginx, Caddy, ALB) with TLS:

```nginx
server {
    listen 443 ssl;
    server_name audit.yourcompany.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Running Without Docker

```bash
# Install dependencies
uv sync

# Run migrations
cd packages/api
uv run alembic -c src/agentaudit_api/alembic.ini upgrade head

# Seed default data
uv run python -m agentaudit_api.seed

# Start the server
uv run uvicorn agentaudit_api.main:app --host 0.0.0.0 --port 8000
```

## Endpoints

| Endpoint                        | Description                  |
|---------------------------------|------------------------------|
| `GET /health`                   | Health check                 |
| `POST /v1/events`              | Ingest an audit event        |
| `GET /v1/events`               | List events with filters     |
| `GET /v1/events/{id}`          | Get event by ID              |
| `GET /v1/events/stats`         | Aggregate statistics         |
| `GET /v1/org/policy`           | Get organization policy      |
| `PUT /v1/org/policy`           | Update organization policy   |
| `GET /dashboard`               | Web dashboard                |
| `GET /dashboard/stats`         | Stats page                   |
| `GET /dashboard/report/pdf`    | Download PDF report          |
| `GET /docs`                    | OpenAPI documentation        |

## Backup

Back up the PostgreSQL data volume regularly:

```bash
docker compose exec db pg_dump -U agentaudit agentaudit > backup.sql
```
