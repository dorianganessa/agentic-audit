# Enterprise Deployment

Deploy AgentAudit across your organization with enforced hooks, per-team policies, and centralized monitoring.

## Claude Code enterprise hooks

Claude Code supports enterprise policy settings that cannot be overridden by developers. Push the AgentAudit hooks at the enterprise level:

```json title="Enterprise Claude Code policy"
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "agentaudit-hook pre"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "agentaudit-hook post"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "agentaudit-hook session-start"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "agentaudit-hook session-end"
          }
        ]
      }
    ]
  }
}
```

!!! tip "Enterprise enforcement"
    Hooks set at the enterprise policy level cannot be removed or overridden
    by individual developers. Every Claude Code session in your organization
    is automatically audited.

## Cowork plugin deployment

For Cowork, publish the AgentAudit plugin to your organization's private marketplace:

1. Fork the plugin from `plugins/cowork/`
2. Configure your organization's API endpoint and key provisioning
3. Publish to your private plugin marketplace
4. Enable auto-install for all users

## Environment provisioning

Each developer needs two environment variables. Distribute them via your configuration management:

```bash
AGENTAUDIT_API_KEY="aa_live_xxxxx"      # Per-user or per-team key
AGENTAUDIT_BASE_URL="https://audit.internal.company.com"  # Your deployment URL
```

Options for provisioning:

- **dotfiles management** (e.g., chezmoi) — inject into shell profile
- **MDM** (e.g., Jamf, Intune) — set system-level environment variables
- **Developer portal** — self-service key generation

## Per-team API keys

Create separate API keys for each team to:

- Attribute events to specific teams
- Apply different policies per team
- Generate team-specific compliance reports

## Recommended policies by team

| Team | Logging Level | Blocking | Rationale |
|---|---|---|---|
| Engineering | `standard` | Disabled | Balanced — captures important events without friction |
| Finance | `paranoid` | `block_on: high` | Maximum protection for financial data |
| Legal | `full` | Disabled | Complete trail for legal review |
| Security | `paranoid` | `block_on: critical` | Prevent credential exposure |

## Production deployment

### Infrastructure

For production, deploy AgentAudit behind a load balancer with:

- **Managed PostgreSQL** (e.g., AWS RDS, Neon) instead of the Docker Compose default
- **TLS termination** at the load balancer
- **Private networking** — the API should not be publicly accessible
- **Monitoring** — health check at `/health`

### Docker deployment

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

See [Docker deployment](../self-hosting/docker.md) for the full production configuration.

### High availability

- Run multiple API instances behind a load balancer
- Use a managed PostgreSQL with read replicas for dashboard queries
- The API is stateless — scale horizontally as needed

## Monitoring

### Health check

```bash
curl https://audit.internal.company.com/health
```

### Metrics to track

- Events per minute (throughput)
- API response time (p95 should be < 100ms)
- Blocked events per day (paranoid mode)
- PII events per day
- Buffer file size on developer machines (indicates API connectivity issues)

## Next steps

- [Docker deployment](../self-hosting/docker.md) — production Docker setup
- [Database](../self-hosting/database.md) — PostgreSQL configuration
- [Policy system](../concepts/policy-system.md) — per-team policy configuration
