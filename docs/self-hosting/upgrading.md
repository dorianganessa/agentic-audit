# Upgrading

How to update AgenticAudit to a new version.

## Docker Compose

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker compose build
docker compose up -d
```

Alembic migrations run automatically on startup. The API will apply any new schema changes before accepting requests.

## pip

```bash
pip install --upgrade agentaudit agentaudit-api
```

If you run the API server, apply migrations:

```bash
alembic upgrade head
```

## From source

```bash
git pull origin main
uv sync
```

Apply migrations:

```bash
uv run alembic upgrade head
```

## Pre-upgrade checklist

1. **Back up your database** before upgrading:
   ```bash
   docker compose exec db pg_dump -U agentaudit agentaudit > backup_$(date +%Y%m%d).sql
   ```

2. **Check the changelog** for breaking changes:
   ```bash
   cat CHANGELOG.md
   ```

3. **Test in staging** before upgrading production

## Breaking changes policy

- **Patch versions** (0.1.x): Bug fixes, no breaking changes
- **Minor versions** (0.x.0): New features, backwards-compatible
- **Major versions** (x.0.0): May include breaking changes (documented in CHANGELOG.md)

Breaking changes are always documented with migration instructions.

## Rollback

If something goes wrong:

```bash
# Docker: revert to previous image
docker compose down
git checkout <previous-tag>
docker compose build
docker compose up -d
```

!!! warning "Database rollback"
    Alembic supports `downgrade`, but rolling back migrations after data has been written
    may cause data loss. Always back up before upgrading.

## Next steps

- [Docker deployment](docker.md) — container configuration
- [Database](database.md) — schema and migration details
