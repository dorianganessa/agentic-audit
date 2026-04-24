"""Auto-suggest AI Act risk classification from system metadata and observed events.

Tier 1 rule-based classifier. Signals come from three sources, merged into a single
normalized text corpus with per-source weighting:
  - system metadata (description / use_case / vendor / name) — authoritative, 3x
  - event data / context payloads — observed, 1x
  - event reasoning strings — 1x

Each category has weighted keyword phrases; weight reflects specificity. Matches use
word-boundary regex against a normalized (alphanumeric + space) corpus. Scores below
a confidence floor return no category, preventing a single noisy hit from winning.

Output drives risk classification with this hierarchy:
  1. Any Article 5 prohibited practice above threshold → "prohibited"
  2. Top Annex III category above threshold → "high"
  3. PII-dominant traffic (ratio >= 0.2) → "limited"  (Art. 50 transparency hint)
  4. Otherwise → "minimal"
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from agentaudit_api.models.ai_system import ANNEX_III_CATEGORIES, AISystem
from agentaudit_api.models.event import AuditEvent
from agentaudit_api.services.system_service import _build_agent_id_filter

logger = logging.getLogger(__name__)


# Weighted keyword phrases per Annex III category.
# Weights reflect specificity: higher = rarer in unrelated text.
# Phrases are lowercase; multi-word phrases use a single space separator and match
# against the normalized (alphanumeric-only) corpus with word boundaries.
_CATEGORY_SIGNALS: dict[str, dict[str, float]] = {
    "employment": {
        "hiring": 2.5,
        "recruit": 2.5,
        "recruiter": 3.0,
        "recruitment": 3.0,
        "candidate": 2.0,
        "applicant": 2.5,
        "resume": 2.5,
        "cv": 0.8,
        "cover letter": 3.0,
        "interview": 1.5,
        "onboarding": 2.0,
        "employee": 1.5,
        "payroll": 3.5,
        "salary": 2.5,
        "compensation": 2.0,
        "performance review": 4.0,
        "termination": 2.5,
        "promotion": 1.5,
        "hr": 1.0,
        "applicant tracking": 4.5,
        "workforce management": 3.5,
    },
    "education": {
        "student": 2.0,
        "pupil": 2.5,
        "grade": 1.5,
        "gpa": 3.5,
        "transcript": 2.5,
        "enrollment": 2.5,
        "admission": 2.5,
        "university": 2.0,
        "school": 1.0,
        "exam": 2.0,
        "examination": 2.0,
        "course": 1.0,
        "tuition": 3.0,
        "diploma": 3.0,
        "degree": 1.5,
        "scholarship": 3.0,
        "standardized test": 4.0,
    },
    "essential_services": {
        "credit score": 4.5,
        "creditworthiness": 4.5,
        "fico": 4.5,
        "loan": 2.5,
        "mortgage": 3.5,
        "underwriting": 4.0,
        "insurance": 2.0,
        "claim": 1.0,
        "premium": 1.0,
        "benefit": 1.0,
        "welfare": 2.5,
        "social security": 3.5,
        "means test": 4.0,
        "emergency services": 3.0,
        "triage": 2.5,
        "utility disconnection": 4.0,
    },
    "law_enforcement": {
        "arrest": 3.0,
        "suspect": 2.5,
        "warrant": 2.5,
        "forensic": 2.5,
        "surveillance": 2.0,
        "detention": 2.5,
        "criminal record": 4.0,
        "offender": 3.0,
        "recidivism": 4.5,
        "parole": 3.5,
        "probation": 3.0,
        "wiretap": 4.5,
        "lie detection": 4.5,
        "polygraph": 4.0,
        "crime analytics": 4.0,
        "evidence reliability": 4.0,
    },
    "biometric": {
        "biometric": 3.5,
        "fingerprint": 3.5,
        "iris": 3.5,
        "retina": 3.5,
        "face recognition": 4.5,
        "facial recognition": 4.5,
        "face matching": 4.5,
        "voice recognition": 3.5,
        "voiceprint": 4.0,
        "dna": 3.0,
        "gait": 3.0,
        "keystroke dynamics": 4.0,
        "remote biometric identification": 5.0,
    },
    "critical_infrastructure": {
        "scada": 4.5,
        "power grid": 4.5,
        "electrical grid": 4.5,
        "substation": 3.5,
        "water treatment": 4.5,
        "water supply": 3.5,
        "nuclear": 3.5,
        "traffic control": 4.0,
        "air traffic": 4.5,
        "rail signaling": 4.5,
        "gas pipeline": 4.5,
        "digital infrastructure": 3.0,
    },
    "migration": {
        "visa": 3.0,
        "asylum": 4.5,
        "immigration": 3.5,
        "passport": 2.5,
        "border control": 4.0,
        "refugee": 4.0,
        "deportation": 4.5,
        "naturalization": 4.0,
        "residence permit": 3.5,
        "migrant": 3.0,
    },
    "democratic_processes": {
        "election": 3.0,
        "ballot": 3.5,
        "voter": 3.0,
        "voting": 2.5,
        "polling station": 4.0,
        "campaign targeting": 4.5,
        "electoral": 3.5,
        "referendum": 3.5,
        "constituency": 3.0,
        "political advertising": 4.0,
    },
}


# Article 5 prohibited practices. Hits here override the Annex III tier entirely.
_PROHIBITED_SIGNALS: dict[str, dict[str, float]] = {
    "social_scoring": {
        "social score": 5.0,
        "social scoring": 5.0,
        "citizen score": 5.0,
        "trustworthiness score": 4.5,
        "social credit": 5.0,
        "behavior score": 3.5,
    },
    "emotion_recognition_workplace_or_education": {
        "emotion recognition": 4.0,
        "emotion detection": 4.0,
        "mood detection": 3.5,
        "student emotion": 5.0,
        "employee emotion": 5.0,
        "workplace sentiment": 4.0,
        "affect recognition": 4.0,
    },
    "biometric_categorization_protected_traits": {
        "race inference": 5.0,
        "ethnicity prediction": 5.0,
        "ethnicity inference": 5.0,
        "sexual orientation prediction": 5.0,
        "sexual orientation inference": 5.0,
        "political opinion inference": 5.0,
        "religion inference": 5.0,
        "religious belief inference": 5.0,
        "trade union inference": 5.0,
    },
    "subliminal_manipulation": {
        "subliminal": 4.5,
        "subliminal technique": 5.0,
        "manipulative technique": 4.0,
        "dark pattern": 3.5,
        "exploit vulnerability": 4.0,
    },
    "untargeted_biometric_scraping": {
        "facial image scraping": 5.0,
        "face scraping": 5.0,
        "cctv scraping": 5.0,
        "internet facial harvest": 5.0,
    },
    "predictive_policing_individual": {
        "predict crime": 4.5,
        "criminal prediction": 5.0,
        "predictive policing": 5.0,
        "individual risk of offending": 5.0,
        "recidivism prediction": 4.5,
    },
}


# JSON keys whose values (and subtrees) add more noise than signal.
# Matched case-insensitively by exact name OR by suffix (e.g., foo_id, bar_hash).
_NOISY_KEY_EXACT = frozenset(
    {
        "id",
        "uuid",
        "ulid",
        "hash",
        "checksum",
        "signature",
        "token",
        "timestamp",
        "created_at",
        "updated_at",
        "deleted_at",
        "request_id",
        "trace_id",
        "span_id",
        "session_id",
        "correlation_id",
        "ip",
        "ip_address",
        "user_agent",
    }
)
_NOISY_KEY_SUFFIXES = ("_id", "_hash", "_token", "_uuid", "_ulid", "_at")


# Tuning knobs
_CATEGORY_CONFIDENCE_THRESHOLD = 3.0
_PROHIBITED_CONFIDENCE_THRESHOLD = 4.5
_SYSTEM_METADATA_WEIGHT = 3.0
_EVENT_PAYLOAD_WEIGHT = 1.0
_PII_RATIO_LIMITED_THRESHOLD = 0.2


def _compile_matchers(
    signals: dict[str, dict[str, float]],
) -> dict[str, list[tuple[str, float, re.Pattern[str]]]]:
    return {
        group: [(kw, weight, re.compile(rf"\b{re.escape(kw)}\b")) for kw, weight in kws.items()]
        for group, kws in signals.items()
    }


# Compiled at module import — matchers are small and we want stable identity so
# `from module import _category_matchers` returns the real object, not an empty snapshot.
_category_matchers = _compile_matchers(_CATEGORY_SIGNALS)
_prohibited_matchers = _compile_matchers(_PROHIBITED_SIGNALS)


_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _normalize(text: str) -> str:
    """Lowercase, replace non-alphanumeric runs with single space, strip."""
    return _NORMALIZE_RE.sub(" ", text.lower()).strip()


def _is_noisy_key(key: str) -> bool:
    kl = key.lower()
    if kl in _NOISY_KEY_EXACT:
        return True
    return any(kl.endswith(suffix) for suffix in _NOISY_KEY_SUFFIXES)


def _walk(obj: Any, parts: list[str]) -> None:
    """Recurse JSON, appending keys + leaf values to `parts`. Skips noisy key subtrees."""
    if obj is None or isinstance(obj, bool):
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            ks = str(k)
            if _is_noisy_key(ks):
                continue
            parts.append(ks)
            _walk(v, parts)
        return
    if isinstance(obj, list | tuple):
        for v in obj:
            _walk(v, parts)
        return
    parts.append(str(obj))


def _build_system_corpus(system: AISystem) -> str:
    pieces = [
        system.name or "",
        system.description or "",
        system.use_case or "",
        system.vendor or "",
        system.role or "",
        system.annex_iii_category or "",
    ]
    return _normalize(" ".join(pieces))


def _build_event_corpus(events: list[AuditEvent]) -> str:
    parts: list[str] = []
    for ev in events:
        if ev.action:
            parts.append(str(ev.action))
        if ev.reasoning:
            parts.append(str(ev.reasoning))
        if ev.data:
            _walk(ev.data, parts)
        if ev.context:
            _walk(ev.context, parts)
    return _normalize(" ".join(parts))


def _score_group(
    text: str,
    matchers: dict[str, list[tuple[str, float, re.Pattern[str]]]],
    corpus_weight: float,
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """Return (score_per_group, per_keyword_contribution_per_group).

    Per-keyword contribution is dampened with sqrt(count) to prevent one log-spammed
    field from dominating. Score is `weight * sqrt(count) * corpus_weight`.
    """
    scores: dict[str, float] = {}
    details: dict[str, dict[str, float]] = {}
    if not text:
        return scores, details
    for group, items in matchers.items():
        group_score = 0.0
        per_kw: dict[str, float] = {}
        for kw, weight, pat in items:
            count = len(pat.findall(text))
            if count == 0:
                continue
            contribution = weight * math.sqrt(count) * corpus_weight
            group_score += contribution
            per_kw[kw] = round(contribution, 2)
        if group_score > 0:
            scores[group] = round(group_score, 2)
            details[group] = per_kw
    return scores, details


def _merge_scores(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = dict(a)
    for k, v in b.items():
        out[k] = round(out.get(k, 0.0) + v, 2)
    return out


def _merge_details(
    a: dict[str, dict[str, float]], b: dict[str, dict[str, float]]
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {k: dict(v) for k, v in a.items()}
    for group, kws in b.items():
        bucket = out.setdefault(group, {})
        for kw, contrib in kws.items():
            bucket[kw] = round(bucket.get(kw, 0.0) + contrib, 2)
    return out


def suggest_classification(
    session: Session,
    system: AISystem,
    api_key_id: str,
    *,
    event_limit: int = 500,
) -> dict[str, Any]:
    """Analyze system metadata + recent events and suggest a risk classification.

    Returns a dict with suggested_classification, suggested_category, rationale, and
    evidence. `evidence` includes per-keyword contributions for explainability.
    """
    if not system.agent_id_patterns:
        return {
            "suggested_classification": "minimal",
            "suggested_category": None,
            "rationale": "No agent_id_patterns configured — no events to analyze.",
            "evidence": {},
        }

    agent_clauses = _build_agent_id_filter(system.agent_id_patterns)
    base_filter: list[Any] = [
        AuditEvent.api_key_id == api_key_id,
        or_(*agent_clauses),
    ]

    total = session.query(AuditEvent).filter(*base_filter).count()
    if total == 0:
        return {
            "suggested_classification": "unclassified",
            "suggested_category": None,
            "rationale": "No events found for this system yet.",
            "evidence": {"total_events": 0},
        }

    # Aggregate event stats
    risk_rows = (
        session.query(AuditEvent.risk_level, func.count())  # type: ignore[call-overload]
        .filter(*base_filter)
        .group_by(AuditEvent.risk_level)
        .all()
    )
    by_risk = {level: count for level, count in risk_rows}

    pii_count = (
        session.query(AuditEvent)
        .filter(*base_filter, AuditEvent.pii_detected.is_(True))  # type: ignore[attr-defined]
        .count()
    )

    action_rows = (
        session.query(AuditEvent.action, func.count())  # type: ignore[call-overload]
        .filter(*base_filter)
        .group_by(AuditEvent.action)
        .all()
    )
    by_action = {act: count for act, count in action_rows}

    # Build two corpora: system metadata (3x weight) and event payloads (1x)
    recent = (
        session.query(AuditEvent)
        .filter(*base_filter)
        .order_by(AuditEvent.created_at.desc())  # type: ignore[attr-defined]
        .limit(event_limit)
        .all()
    )
    system_text = _build_system_corpus(system)
    event_text = _build_event_corpus(recent)

    sys_cat_scores, sys_cat_details = _score_group(
        system_text, _category_matchers, _SYSTEM_METADATA_WEIGHT
    )
    ev_cat_scores, ev_cat_details = _score_group(
        event_text, _category_matchers, _EVENT_PAYLOAD_WEIGHT
    )
    category_scores = _merge_scores(sys_cat_scores, ev_cat_scores)
    category_details = _merge_details(sys_cat_details, ev_cat_details)

    sys_prh_scores, sys_prh_details = _score_group(
        system_text, _prohibited_matchers, _SYSTEM_METADATA_WEIGHT
    )
    ev_prh_scores, ev_prh_details = _score_group(
        event_text, _prohibited_matchers, _EVENT_PAYLOAD_WEIGHT
    )
    prohibited_scores = _merge_scores(sys_prh_scores, ev_prh_scores)
    prohibited_details = _merge_details(sys_prh_details, ev_prh_details)

    pii_ratio = pii_count / total if total > 0 else 0.0

    # --- Decision hierarchy ---
    reasons: list[str] = []
    suggested = "minimal"
    suggested_category: str | None = None

    # 1. Article 5 prohibited
    top_prohibited: str | None = None
    top_prohibited_score = 0.0
    if prohibited_scores:
        top_prohibited = max(prohibited_scores, key=prohibited_scores.get)  # type: ignore[arg-type]
        top_prohibited_score = prohibited_scores[top_prohibited]

    if top_prohibited and top_prohibited_score >= _PROHIBITED_CONFIDENCE_THRESHOLD:
        suggested = "prohibited"
        reasons.append(
            f"Article 5 prohibited-practice signal detected: {top_prohibited} "
            f"(score {top_prohibited_score})"
        )

    # 2. Top Annex III category
    top_category: str | None = None
    top_category_score = 0.0
    if category_scores:
        top_category = max(category_scores, key=category_scores.get)  # type: ignore[arg-type]
        top_category_score = category_scores[top_category]

    if top_category and top_category_score >= _CATEGORY_CONFIDENCE_THRESHOLD:
        suggested_category = top_category
        if suggested != "prohibited" and top_category in ANNEX_III_CATEGORIES:
            suggested = "high"
            reasons.append(
                f"Annex III category '{top_category}' detected (score {top_category_score})"
            )

    # 3. PII transparency hint (Art. 50)
    if suggested == "minimal" and pii_ratio >= _PII_RATIO_LIMITED_THRESHOLD:
        suggested = "limited"
        reasons.append(
            f"{pii_count}/{total} events contain PII ({pii_ratio:.0%}) — "
            "Art. 50 transparency may apply"
        )

    if not reasons:
        reasons.append("No high-risk patterns detected in event data")

    return {
        "suggested_classification": suggested,
        "suggested_category": suggested_category,
        "rationale": "; ".join(reasons),
        "evidence": {
            "total_events": total,
            "by_risk_level": by_risk,
            "by_action": by_action,
            "pii_events": pii_count,
            "pii_ratio": round(pii_ratio, 3),
            "category_scores": category_scores,
            "category_matches": category_details,
            "category_confidence_threshold": _CATEGORY_CONFIDENCE_THRESHOLD,
            "prohibited_scores": prohibited_scores,
            "prohibited_matches": prohibited_details,
            "prohibited_confidence_threshold": _PROHIBITED_CONFIDENCE_THRESHOLD,
        },
    }
