# Database

AgentAudit uses PostgreSQL as its data store. Events are stored in an append-only event table with indexes for efficient querying.

## Requirements

- **PostgreSQL 16+** (tested with 16-alpine)
- Any PostgreSQL-compatible service: AWS RDS, Google Cloud SQL, Neon, Supabase, etc.

## Connection string

Set the connection string via environment variable:

```bash
AGENTAUDIT_DATABASE_URL="postgresql+psycopg2://user:password@host:5432/agentaudit"
```

The URL uses SQLAlchemy's `psycopg2` dialect.

## Schema overview

AgentAudit uses three main tables:

### audit_events

The core table. Append-only — events are never updated or deleted.

| Column | Type | Description |
|---|---|---|
| `id` | `VARCHAR` (ULID) | Primary key, sortable by time |
| `agent_id` | `VARCHAR` | Agent identifier |
| `action` | `VARCHAR` | Action type |
| `data` | `JSON` | Action-specific data |
| `context` | `JSON` | Additional context |
| `reasoning` | `TEXT` | Agent's reasoning |
| `risk_level` | `VARCHAR` | Computed risk level |
| `pii_detected` | `BOOLEAN` | PII detection result |
| `pii_fields` | `JSON` | List of PII types found |
| `frameworks` | `JSON` | Mapped compliance articles |
| `api_key_id` | `VARCHAR` | FK to API key (for scoping) |
| `created_at` | `TIMESTAMP` | Event timestamp |

### Indexes

| Index | Columns | Purpose |
|---|---|---|
| `ix_audit_events_agent_id` | `agent_id` | Filter by agent |
| `ix_audit_events_action` | `action` | Filter by action |
| `ix_audit_events_created_at` | `created_at` | Time-range queries |
| `ix_audit_events_risk_level` | `risk_level` | Filter by risk |
| `ix_audit_events_api_key_id` | `api_key_id` | Scope to organization |

### organizations

| Column | Type | Description |
|---|---|---|
| `id` | `VARCHAR` | Primary key |
| `name` | `VARCHAR` | Organization name |
| `policy` | `JSON` | Policy configuration |

### api_keys

| Column | Type | Description |
|---|---|---|
| `id` | `VARCHAR` | Primary key |
| `key_hash` | `VARCHAR` | SHA-256 hash of the API key |
| `org_id` | `VARCHAR` | FK to organization |
| `is_active` | `BOOLEAN` | Soft delete flag |

## Migrations

AgentAudit uses Alembic for schema migrations. Migrations run automatically on API startup.

To run manually:

```bash
# Inside the API container
alembic upgrade head

# Or with Docker Compose
docker compose exec api alembic upgrade head
```

## Append-only design

The `audit_events` table is append-only by design:

- Events are **never updated** after creation
- Events are **never deleted** by the application
- This creates a tamper-evident audit trail
- ULIDs provide time-ordered unique identifiers

## Data retention

AgentAudit does not automatically delete old events. For data retention:

```sql
-- Delete events older than 1 year (run manually or via cron)
DELETE FROM audit_events WHERE created_at < NOW() - INTERVAL '1 year';

-- Or archive to cold storage first
COPY (SELECT * FROM audit_events WHERE created_at < NOW() - INTERVAL '1 year')
TO '/tmp/archive.csv' WITH CSV HEADER;
```

!!! warning "Retention and compliance"
    Check your compliance requirements before deleting events.
    GDPR Art. 30 records may need to be retained for the duration of data processing.
    SOC 2 typically requires 1 year of audit logs.

## Neon compatibility

AgentAudit is compatible with [Neon](https://neon.tech/) serverless PostgreSQL. Use the Neon connection string directly:

```bash
AGENTAUDIT_DATABASE_URL="postgresql+psycopg2://user:pass@ep-xxx.us-east-2.aws.neon.tech/agentaudit?sslmode=require"
```

## Performance

For high-throughput deployments:

- Use connection pooling (PgBouncer or built-in pool)
- Add read replicas for dashboard queries
- The ULID primary key eliminates index fragmentation from random UUIDs
- JSON columns use PostgreSQL's native JSON type for efficient storage

## Next steps

- [Docker deployment](docker.md) — container setup
- [Upgrading](upgrading.md) — how to update
