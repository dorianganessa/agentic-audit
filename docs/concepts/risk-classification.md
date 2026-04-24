# Risk Classification

The **EU AI Act** groups AI systems into four risk tiers — `prohibited`, `high`, `limited`, `minimal` — and defines additional obligations for `high` systems that fall under one of eight Annex III categories. AgenticAudit tracks this on every registered system and can **suggest** a classification by analyzing system metadata plus observed event patterns.

Risk classification is separate from per-event **risk scoring** (low / medium / high / critical). Risk scoring describes a single action; risk classification describes the system as a whole under the AI Act.

## The four AI Act tiers

| Tier | When it applies | Typical obligations |
|---|---|---|
| `prohibited` | Practices banned under Article 5 (social scoring, emotion recognition in workplace/education, biometric categorization by protected traits, subliminal manipulation, untargeted biometric scraping, individual predictive policing) | Cannot be deployed in the EU. |
| `high` | Systems used in Annex III areas, or covered under Article 6 as safety components | FRIA, registration, logging, transparency, human oversight, post-market monitoring. |
| `limited` | Systems subject to Art. 50 transparency (chatbots, deepfakes, emotion recognition outside prohibited contexts, personal data processing with transparency obligations) | Disclose AI use to users. |
| `minimal` | Everything else | No specific obligations beyond voluntary codes. |

## Annex III categories

High-risk systems typically fall under one of these eight Annex III categories. Each drives specific FRIA sections and compliance checks:

| Category | Examples |
|---|---|
| `biometric` | Face recognition, voice identification, remote biometric identification |
| `critical_infrastructure` | SCADA, power grid, water treatment, air traffic control |
| `education` | Grading, exam scoring, admission, enrollment triage |
| `employment` | Resume screening, applicant tracking, performance review, payroll |
| `essential_services` | Credit scoring, insurance underwriting, welfare eligibility |
| `law_enforcement` | Evidence evaluation, recidivism prediction, forensics, wiretap |
| `migration` | Visa, asylum, border control, deportation |
| `democratic_processes` | Voter targeting, electoral analytics, campaign optimization |

## Auto-suggestion

`GET /v1/systems/{id}/classification-suggestion` runs a rule-based classifier over two corpora:

1. **System metadata** — `name`, `description`, `use_case`, `vendor`, `role`. Weighted **3×**, because it is the most authoritative signal. This is what a reviewer would read first.
2. **Recent event payloads** — `data`, `context`, `action`, `reasoning` (up to 500 most recent events). Weighted 1×. Noisy JSON keys (`*_id`, `*_hash`, `*_at`, `timestamp`, `trace_id`, `user_agent`, ...) and their subtrees are **excluded**, so identifiers like `req-salary-123` don't leak into the employment score.

Both corpora are normalized (lowercased, non-alphanumeric characters collapsed to spaces) and scored against **weighted keyword phrases**. Weights reflect specificity — `"scada"` (4.5) scores much higher than `"cv"` (0.8). Matches use **word boundaries** so `"cv"` never matches inside `"cvs"` or `"received"`. Repeated hits of the same phrase are dampened with `sqrt(count)` so one log-spammed field can't dominate.

### Decision hierarchy

The classifier walks the following priority order:

1. **Article 5 prohibited practices** — if any prohibited signal scores ≥ **4.5**, the suggestion is `prohibited`. The signal that fired is named in the rationale.
2. **Top Annex III category** — the highest-scoring category, if it clears the **3.0** threshold, is reported as `suggested_category` and the suggestion becomes `high`.
3. **Art. 50 transparency hint** — if no Annex III category cleared the threshold but ≥ 20% of events contain PII, the suggestion is `limited`.
4. Otherwise — `minimal`.

A single accidental keyword hit cannot force a category. If nothing clears the confidence threshold, `suggested_category` is `null` and the rationale says `"No high-risk patterns detected in event data"`.

### Explainability

The `evidence` object returned with every suggestion lets a human reviewer see exactly **why** the classifier chose what it did:

```json
{
  "suggested_classification": "high",
  "suggested_category": "employment",
  "rationale": "Annex III category 'employment' detected (score 42.5)",
  "evidence": {
    "category_scores": {"employment": 42.5, "education": 2.1},
    "category_matches": {
      "employment": {"candidate": 12.5, "resume": 12.5, "hiring": 12.5, "salary": 5.0}
    },
    "category_confidence_threshold": 3.0,
    "prohibited_scores": {},
    "prohibited_confidence_threshold": 4.5
  }
}
```

- `category_scores` — total score per Annex III category
- `category_matches` — per-phrase contribution to each score
- `prohibited_scores` / `prohibited_matches` — same for Article 5 practices
- `*_confidence_threshold` — score needed to fire that tier

Both the score **and** the phrases that produced it should be attached to the FRIA record when accepting a suggestion.

## Suggestions are non-binding

The classifier is a **starting point**. It does not make the determination. A qualified reviewer must confirm and persist the final classification on the system record via `PUT /v1/systems/{id}`:

```json
{
  "risk_classification": "high",
  "annex_iii_category": "employment",
  "classification_rationale": "Screens applicant resumes. Confirmed high-risk under Annex III §4(a). Auto-suggested by AgenticAudit with score 42.5 on 2026-04-24."
}
```

Once set, the classification drives the compliance score, FRIA requirements, and retention rules. See [Compliance API](../api-reference/compliance.md).

## Tuning the classifier

The classifier is intentionally conservative: the thresholds are set so that a clean codebase with ambiguous signals defaults to `minimal` rather than misleadingly escalating. If you need to adjust keyword weights, thresholds, or add signals for a specialized domain, they live in `packages/api/src/agentaudit_api/services/classification_service.py`:

- `_CATEGORY_SIGNALS` — Annex III keyword weights
- `_PROHIBITED_SIGNALS` — Article 5 keyword weights
- `_CATEGORY_CONFIDENCE_THRESHOLD` (default 3.0)
- `_PROHIBITED_CONFIDENCE_THRESHOLD` (default 4.5)
- `_SYSTEM_METADATA_WEIGHT` (default 3.0×)
- `_NOISY_KEY_EXACT` / `_NOISY_KEY_SUFFIXES` — JSON keys ignored during walk

## Next steps

- [Systems API](../api-reference/systems.md) — registering systems and accepting suggestions
- [Compliance API](../api-reference/compliance.md) — how classification feeds the compliance score
- [Framework mapping](framework-mapping.md) — how events map to GDPR, AI Act, and SOC 2 articles
