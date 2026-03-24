# Quickstart

Get AgenticAudit running and log your first event in under 5 minutes.

## 1. Start AgenticAudit

```bash
git clone https://github.com/dorianganessa/agentic-audit.git
cd agentic-audit
docker compose up -d
```

Wait for services to be healthy, then get your API key:

```bash
docker compose logs api | grep "Default API key"
```

## 2. Log your first event

=== "Python SDK"

    ```bash
    pip install agentic-audit
    ```

    ```python
    from agentaudit import AgentAudit

    audit = AgentAudit(
        api_key="aa_live_xxxxx",
        base_url="http://localhost:8000",
    )

    event = audit.log(
        agent_id="my-first-agent",
        action="access_customer_record",
        data={"customer_email": "user@example.com"},
    )

    print(f"Event ID: {event.id}")
    print(f"Risk level: {event.risk_level}")
    print(f"PII detected: {event.pii_detected}")
    print(f"Frameworks: {event.frameworks}")
    ```

=== "cURL"

    ```bash
    curl -X POST http://localhost:8000/v1/events \
      -H "Authorization: Bearer YOUR_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "agent_id": "my-first-agent",
        "action": "access_customer_record",
        "data": {"customer_email": "user@example.com"}
      }'
    ```

You should see a response with `risk_level`, `pii_detected`, and `frameworks` populated.

## 3. View the dashboard

Open [http://localhost:8000/dashboard](http://localhost:8000/dashboard) in your browser. You will be redirected to the login page.

!!! note "Dashboard authentication"
    The dashboard requires login. Navigate to `/dashboard/login` and enter your API key to authenticate.

    - Your session is stored as an HTTP-only cookie, valid for **7 days**
    - To log out, visit `/dashboard/logout`

Once logged in, your event should appear in the timeline with its risk level and PII badge.

## 4. Connect Claude Code (optional)

If you use Claude Code, add hooks to audit every action automatically:

```json title=".claude/settings.json"
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
    ]
  }
}
```

Set environment variables:

```bash
export AGENTAUDIT_API_KEY="aa_live_xxxxx"
export AGENTAUDIT_BASE_URL="http://localhost:8000"

# Optional: user identity for the dashboard
export AGENTAUDIT_USER_EMAIL="you@company.com"
```

Now every Claude Code action is logged automatically with your identity. See the [Claude Code integration guide](../integrations/claude-code.md) for details.

## 5. Connect Cowork (optional)

If you use Cowork, configure the OTLP endpoint in your organization settings:

| Setting | Value |
|---|---|
| **OTLP Endpoint** | `http://localhost:8000/v1/otlp` |
| **Protocol** | `http/json` |
| **Headers** | `Authorization=Bearer aa_live_xxxxx` |

Every Cowork action is now captured — connectors, file operations, web browsing. See the [Cowork integration guide](../integrations/cowork.md) for details.

## Next steps

- [Installation options](installation.md) — pip, Docker, from source
- [Configuration reference](configuration.md) — all environment variables
- [Claude Code integration](../integrations/claude-code.md) — full setup guide
- [Cowork integration](../integrations/cowork.md) — native OTLP integration
- [Policy system](../concepts/policy-system.md) — configure logging levels
