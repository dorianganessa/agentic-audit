# Compliance API

EU AI Act compliance endpoints: status scoring, PDF reports, and FRIA generation.

## GET /v1/compliance/ai-act/status

Get the organization's overall AI Act compliance status.

**Authentication:** Bearer token required.

### Compliance score

The score (0–100%) is calculated from five checks:

| Check | Passes when |
|---|---|
| `all_classified` | Every registered system has a risk classification other than `unclassified` |
| `no_prohibited` | No systems are classified as `prohibited` |
| `fria_complete` | All `high`-risk systems have FRIA status `completed` |
| `contracts_reviewed` | All systems have `contract_has_ai_annex = true` |
| `retention_compliant` | Retention period ≥ 180 days (Art 12 requirement) |

### Response (200 OK)

```json
{
  "score": 80,
  "checks": {
    "all_classified": true,
    "no_prohibited": true,
    "fria_complete": false,
    "contracts_reviewed": true,
    "retention_compliant": true
  },
  "summary": {
    "total_systems": 5,
    "classified": 5,
    "high_risk": 2,
    "fria_completed": 1,
    "contracts_with_annex": 5,
    "prohibited_systems": 0,
    "retention_days": 365,
    "retention_compliant": true
  },
  "compliance_preset": "ai_act",
  "deadlines": [
    {
      "system": "HR Bot",
      "type": "fria_review",
      "date": "2026-07-15T00:00:00"
    }
  ]
}
```

### Example

```bash
curl http://localhost:8000/v1/compliance/ai-act/status \
  -H "Authorization: Bearer aa_live_xxxxx"
```

---

## GET /v1/compliance/ai-act/report

Download an AI Act compliance report as a PDF.

**Authentication:** Bearer token required.

### Response

- **Content-Type:** `application/pdf`
- **Content-Disposition:** `attachment; filename="ai_act_compliance_20260323.pdf"`

The report includes:

1. **Executive Summary** — system count, event count, compliance score
2. **AI Systems Inventory** (Art 26.5) — tabular list of all systems
3. **Risk Classification** — distribution across prohibited/high/limited/minimal/unclassified
4. **FRIA Status** (Art 27) — per-system FRIA completion tracking
5. **Vendor Contract Compliance** (Art 26) — AI annex and obligations status
6. **Activity Logging & Retention** (Art 12) — logging level, retention period, compliance check
7. **AI Governance** — active frameworks, blocking rules, compliance preset

### Example

```bash
curl -o compliance_report.pdf \
  http://localhost:8000/v1/compliance/ai-act/report \
  -H "Authorization: Bearer aa_live_xxxxx"
```

---

## GET /v1/compliance/ai-act/fria/{system_id}/pdf

Generate and download a pre-filled Fundamental Rights Impact Assessment (FRIA) PDF for a high-risk AI system.

**Authentication:** Bearer token required.

### Path parameters

| Parameter | Type | Description |
|---|---|---|
| `system_id` | `string` | AI system ID |

### Response

- **Content-Type:** `application/pdf`
- **Content-Disposition:** `attachment; filename="fria_hr_bot_20260323.pdf"`

The FRIA includes:

1. **System Identification** — name, vendor, use case, risk classification, Annex III category
2. **Data Processing Overview** — total events, PII ratio, actions breakdown
3. **Risk Assessment** — events by risk level, warnings for high/critical
4. **Fundamental Rights Impact** — assessment sections for each applicable right (Art 21, 7, 8, 11, 47; plus Art 31 and Art 28 for employment systems)
5. **Mitigation Measures** — logging level, blocking rules, space for additional measures
6. **Monitoring & Review** — FRIA status, last completed, next review date

Sections requiring human input are marked with `[HUMAN REVIEW REQUIRED]`.

### Example

```bash
curl -o fria_hr_bot.pdf \
  http://localhost:8000/v1/compliance/ai-act/fria/01JARQ.../pdf \
  -H "Authorization: Bearer aa_live_xxxxx"
```

### Errors

| Code | Description |
|---|---|
| `404` | System not found |

---

## Retention enforcement

When the organization policy has `compliance_preset` set to `"ai_act"`, the API automatically enforces a minimum retention period of 180 days (6 months), as required by AI Act Article 12.

Setting the preset via `PUT /v1/org/policy`:

```bash
curl -X PUT http://localhost:8000/v1/org/policy \
  -H "Authorization: Bearer aa_live_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{"compliance_preset": "ai_act", "retention_days": 365}'
```

If `retention_days` is below 180 when the AI Act preset is active, it is automatically raised to 180.
