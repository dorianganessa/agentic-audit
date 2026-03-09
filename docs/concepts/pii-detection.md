# PII Detection

AgentAudit automatically scans every event's `data` and `context` fields for personally identifiable information (PII). Detection runs server-side, synchronously, with zero external dependencies.

## How it works

The PII detector recursively walks all string values in the event data and context dictionaries. It applies regex patterns against each value, collecting any matches.

No machine learning models or external services are used. Detection is purely regex and heuristic-based, which means:

- **Fast**: microsecond-level per event
- **Deterministic**: same input always produces the same result
- **Offline**: no network calls, no data leaves your server

## Patterns detected

| PII Type | Pattern | Examples |
|---|---|---|
| **Email** | `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` | `user@example.com` |
| **IPv4 address** | `\b(?:\d{1,3}\.){3}\d{1,3}\b` | `192.168.1.1` |
| **Phone number** | International format with optional country code | `+1 555-123-4567` |
| **Credit card** | 16 digits in groups of 4 | `4111-1111-1111-1111` |
| **API keys** | `sk_live_`, `sk_test_`, `ghp_`, `gho_`, `AKIA`, `xox[bpras]`, `Bearer ` | `sk_live_abc123...` |
| **Database connection strings** | PostgreSQL, MySQL, MongoDB, Redis, AMQP URIs | `postgresql://user:pass@host/db` |

## Event fields

When PII is detected, the event is annotated with two fields:

| Field | Type | Description |
|---|---|---|
| `pii_detected` | `bool` | `true` if any PII pattern matched |
| `pii_fields` | `list[str]` | Sorted list of detected PII types (e.g., `["email", "ipv4"]`) |

Example response:

```json
{
  "pii_detected": true,
  "pii_fields": ["credit_card", "email"],
  "risk_level": "medium"
}
```

## How PII affects other systems

- **Risk scoring**: PII detection bumps the risk level to at least `medium`. PII in a production context bumps it to `high`. See [risk scoring](risk-scoring.md).
- **Framework mapping**: PII triggers GDPR Art. 30 (records of processing) and SOC 2 CC6.5 (data classification). See [framework mapping](framework-mapping.md).
- **Policy storage**: In `minimal` logging mode, only events with PII detected are stored. See [policy system](policy-system.md).

## Recursive scanning

The detector walks nested structures:

```python
# All of these are scanned:
data = {
    "customer": {
        "contact": {
            "email": "user@example.com"  # detected
        }
    },
    "notes": ["Call +1-555-0123 for details"]  # detected
}
```

Dictionaries, lists, and nested combinations are all traversed. Only string values are pattern-matched.

## Known limitations

- **False positives**: Some patterns (especially phone numbers and IPv4) can match non-PII data. For example, version numbers like `1.2.3.4` may trigger an IPv4 match.
- **False negatives**: Names, addresses, and unstructured PII in free text are not detected by regex patterns.
- **No context awareness**: The detector doesn't know if an email is a real person's email or a test fixture. All matches are treated equally.

## Next steps

- [Risk scoring](risk-scoring.md) — how PII detection influences risk levels
- [Framework mapping](framework-mapping.md) — which compliance articles PII triggers
- [Policy system](policy-system.md) — control what gets stored based on PII
