# AI Systems API

Register and manage AI systems for EU AI Act compliance tracking. Systems link to audit events via `agent_id_patterns`, enabling retroactive classification and monitoring.

## POST /v1/systems

Register a new AI system.

**Authentication:** Bearer token required.

### Request body

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | `string` | Yes | — | System name |
| `vendor` | `string` | No | `""` | Vendor/provider name |
| `description` | `string` | No | `""` | System description (max 2000 chars) |
| `use_case` | `string` | No | `""` | Intended use case (max 1000 chars) |
| `agent_id_patterns` | `list[string]` | No | `[]` | Patterns to match events (supports `*` wildcards) |
| `risk_classification` | `string` | No | `"unclassified"` | One of: `prohibited`, `high`, `limited`, `minimal`, `unclassified` |
| `classification_rationale` | `string` | No | `""` | Why this classification was chosen |
| `annex_iii_category` | `string` | No | `null` | Annex III category (see below) |
| `role` | `string` | No | `"deployer"` | `deployer`, `provider`, or `both` |
| `contract_has_ai_annex` | `bool` | No | `false` | Vendor contract includes AI annex |
| `provider_obligations_documented` | `bool` | No | `false` | Provider obligations documented |
| `contract_notes` | `string` | No | `""` | Notes on contract review |
| `fria_status` | `string` | No | `"not_started"` | FRIA status (see below) |
| `fria_completed_at` | `datetime` | No | `null` | When FRIA was last completed |
| `fria_next_review` | `datetime` | No | `null` | Next FRIA review date |
| `next_review_date` | `datetime` | No | `null` | Next system review date |

### Annex III categories

`biometric`, `critical_infrastructure`, `education`, `employment`, `essential_services`, `law_enforcement`, `migration`, `democratic_processes`

### FRIA statuses

`not_started`, `in_progress`, `completed`, `due_for_review`

### Example

```bash
curl -X POST http://localhost:8000/v1/systems \
  -H "Authorization: Bearer aa_live_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "HR Screening Bot",
    "vendor": "Acme AI",
    "use_case": "Resume screening for hiring",
    "agent_id_patterns": ["hr-bot", "hr-bot-*"],
    "risk_classification": "high",
    "annex_iii_category": "employment",
    "role": "deployer",
    "contract_has_ai_annex": true
  }'
```

### Response (201 Created)

Full system object with `id`, `created_at`, `updated_at`, and all fields.

---

## GET /v1/systems

List all registered AI systems for the organization.

**Authentication:** Bearer token required.

### Query parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `include_inactive` | `bool` | `false` | Include soft-deleted systems |

### Response (200 OK)

```json
{
  "systems": [
    {
      "id": "01JARQ...",
      "name": "HR Screening Bot",
      "vendor": "Acme AI",
      "risk_classification": "high",
      "annex_iii_category": "employment",
      "fria_status": "completed",
      "contract_has_ai_annex": true,
      "agent_id_patterns": ["hr-bot", "hr-bot-*"],
      "is_active": true
    }
  ],
  "total": 1
}
```

---

## GET /v1/systems/{system_id}

Get a single system by ID.

**Authentication:** Bearer token required.

---

## PUT /v1/systems/{system_id}

Partially update a system. Only include fields you want to change.

**Authentication:** Bearer token required.

### Example

```bash
curl -X PUT http://localhost:8000/v1/systems/01JARQ... \
  -H "Authorization: Bearer aa_live_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "risk_classification": "high",
    "annex_iii_category": "employment",
    "fria_status": "in_progress"
  }'
```

---

## DELETE /v1/systems/{system_id}

Soft-delete (deactivate) a system. The system is retained for audit trail but excluded from default listings.

**Authentication:** Bearer token required.

### Response: 204 No Content

---

## GET /v1/systems/{system_id}/events

List audit events matching the system's `agent_id_patterns`.

**Authentication:** Bearer token required.

### Query parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | `int` | `50` | Max results (1–200) |
| `offset` | `int` | `0` | Skip N results |

### How pattern matching works

Patterns use `*` as a wildcard. For example, `["hr-bot", "hr-bot-*"]` matches events with `agent_id` of `"hr-bot"`, `"hr-bot-v2"`, `"hr-bot-staging"`, etc.

This is retroactive: registering a system with patterns immediately links it to all existing events that match, without modifying the events.

---

## GET /v1/systems/{system_id}/stats

Get aggregate event statistics for a system based on its `agent_id_patterns`.

**Authentication:** Bearer token required.

### Response (200 OK)

```json
{
  "total_events": 1523,
  "pii_events": 45,
  "by_risk_level": {"low": 1200, "medium": 280, "high": 38, "critical": 5},
  "by_action": {"shell_command": 800, "file_read": 500, "connector_access": 223}
}
```

---

## GET /v1/systems/{system_id}/classification-suggestion

Analyze system metadata and observed events to suggest an AI Act risk classification.

**Authentication:** Bearer token required.

### How the classifier works

The engine builds a normalized text corpus from two sources and scores it against weighted keyword phrases:

1. **System metadata** (`name`, `description`, `use_case`, `vendor`, `role`) — weighted 3× because it is authoritative.
2. **Recent event payloads** (`data`, `context`, `action`, `reasoning`, up to 500 events) — weighted 1×. Noisy JSON keys (IDs, timestamps, hashes, user agents) are excluded so identifiers like `req-salary-123` don't leak into the signal.

Matches use word boundaries (so `"cv"` does not match inside `"cvs"` or `"received"`), and repeated hits are dampened with `sqrt(count)` so a single log-spammed field cannot dominate the score.

### Decision hierarchy

The output follows a strict priority order:

1. **Article 5 prohibited practices** — if any of the following signals score ≥ **4.5**, the system is suggested as `prohibited`:
    - Social scoring (e.g., `"social score"`, `"citizen score"`, `"social credit"`)
    - Emotion recognition in workplace or education
    - Biometric categorization by protected traits (race, ethnicity, political opinion, religion, sexual orientation, trade union)
    - Subliminal or manipulative techniques
    - Untargeted biometric scraping
    - Individual-level predictive policing
2. **Annex III high-risk category** — if the top Annex III category scores ≥ **3.0**, the system is suggested as `high` with that category:
    - `employment`, `education`, `essential_services`, `law_enforcement`, `biometric`, `critical_infrastructure`, `migration`, `democratic_processes`
3. **Art. 50 transparency hint** — otherwise, if ≥ 20% of events contain PII, the system is suggested as `limited`.
4. Else — `minimal`.

If no signal clears its confidence threshold, `suggested_category` is `null` and the rationale says "No high-risk patterns detected in event data". This prevents single accidental keyword hits from forcing a category.

### Response (200 OK)

```json
{
  "suggested_classification": "high",
  "suggested_category": "employment",
  "rationale": "Annex III category 'employment' detected (score 42.5); 45/1523 events contain PII (3%) — Art. 50 transparency may apply",
  "evidence": {
    "total_events": 1523,
    "by_risk_level": {"low": 1200, "medium": 280, "high": 38, "critical": 5},
    "by_action": {"shell_command": 800, "file_read": 500},
    "pii_events": 45,
    "pii_ratio": 0.03,
    "category_scores": {"employment": 42.5, "education": 2.1},
    "category_matches": {
      "employment": {"candidate": 12.5, "resume": 12.5, "hiring": 12.5, "salary": 5.0}
    },
    "category_confidence_threshold": 3.0,
    "prohibited_scores": {},
    "prohibited_matches": {},
    "prohibited_confidence_threshold": 4.5
  }
}
```

- `category_scores` — total weighted score per Annex III category
- `category_matches` — which phrases matched and their contribution to the score (for explainability / FRIA evidence)
- `prohibited_scores` / `prohibited_matches` — same for Article 5 practices
- `*_confidence_threshold` — minimum score for that tier to fire

Suggestions are non-binding. A human reviewer should confirm and record the final `risk_classification`, `annex_iii_category`, and `classification_rationale` on the system record.

---

## Errors

| Code | Description |
|---|---|
| `401` | Missing or invalid API key |
| `404` | System or organization not found |
| `422` | Invalid field value (e.g., bad risk_classification) |
