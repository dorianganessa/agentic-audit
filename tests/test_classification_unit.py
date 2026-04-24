"""Pure-unit tests for the classification service — no DB required."""

from __future__ import annotations

import math

from agentaudit_api.services.classification_service import (
    _CATEGORY_SIGNALS,
    _category_matchers,
    _is_noisy_key,
    _normalize,
    _prohibited_matchers,
    _score_group,
    _walk,
)


def test_normalize_collapses_non_alphanum():
    assert _normalize("Hello, World!") == "hello world"
    assert _normalize("credit_score-123") == "credit score 123"
    assert _normalize("  multiple   spaces  ") == "multiple spaces"


def test_is_noisy_key_catches_ids_and_timestamps():
    # Exact-match noisy keys
    assert _is_noisy_key("id")
    assert _is_noisy_key("request_id")
    assert _is_noisy_key("created_at")
    assert _is_noisy_key("trace_id")
    # Suffix-match noisy keys
    assert _is_noisy_key("session_token")
    assert _is_noisy_key("config_hash")
    assert _is_noisy_key("document_uuid")
    assert _is_noisy_key("record_ulid")
    assert _is_noisy_key("expires_at")
    # Case-insensitive
    assert _is_noisy_key("Request_ID")
    assert _is_noisy_key("CREATED_AT")
    # Not noisy
    assert not _is_noisy_key("salary")
    assert not _is_noisy_key("candidate_name")
    assert not _is_noisy_key("file_path")
    assert not _is_noisy_key("description")


def test_walk_skips_noisy_key_subtrees():
    parts: list[str] = []
    _walk(
        {
            "request_id": "req-salary-123",
            "trace_id": "candidate-trace",
            "candidate_name": "Alice",
            "nested": {"salary": 50000, "internal_id": "skip-this-credit-score"},
        },
        parts,
    )
    text = " ".join(parts).lower()
    assert "salary" in text
    assert "alice" in text
    assert "candidate" in text
    assert "req-salary-123" not in text
    assert "candidate-trace" not in text
    assert "skip" not in text


def test_walk_ignores_none_and_bool():
    parts: list[str] = []
    _walk({"flag": True, "other": None, "name": "alice"}, parts)
    assert "alice" in " ".join(parts)
    assert "true" not in " ".join(parts).lower()


def test_score_group_respects_word_boundaries():
    text = _normalize("the agent received a cvs file")
    scores, _ = _score_group(text, _category_matchers, 1.0)
    assert "employment" not in scores or scores["employment"] == 0


def test_score_group_matches_whole_words():
    text = _normalize("reviewing candidate resume for hiring")
    scores, details = _score_group(text, _category_matchers, 1.0)
    assert "employment" in scores
    assert scores["employment"] > 0
    assert "candidate" in details["employment"]
    assert "resume" in details["employment"]
    assert "hiring" in details["employment"]


def test_score_group_matches_multiword_phrases():
    text = _normalize("compute credit_score for applicant")
    scores, details = _score_group(text, _category_matchers, 1.0)
    assert "essential_services" in scores
    assert "credit score" in details["essential_services"]


def test_score_group_damps_repeated_hits_exactly_with_sqrt():
    """Score for n repeats must equal weight * sqrt(n), not linear or log."""
    salary_weight = _CATEGORY_SIGNALS["employment"]["salary"]
    text = _normalize(" ".join(["salary"] * 100))
    scores, details = _score_group(text, _category_matchers, 1.0)
    expected = salary_weight * math.sqrt(100)  # 2.5 * 10 = 25.0
    # Only "salary" contributes for the employment category in this text.
    assert details["employment"]["salary"] == round(expected, 2)
    assert scores["employment"] == round(expected, 2)


def test_score_group_applies_corpus_weight_multiplier():
    """`corpus_weight` (used for 3x metadata) must linearly scale the score."""
    text = _normalize("reviewing candidate resume for hiring")
    low, _ = _score_group(text, _category_matchers, 1.0)
    high, _ = _score_group(text, _category_matchers, 3.0)
    # 3x corpus weight must produce a 3x score (within float rounding).
    assert low["employment"] > 0
    assert high["employment"] == round(low["employment"] * 3.0, 2)


def test_prohibited_matchers_detect_social_scoring():
    text = _normalize("assigning social score to citizens")
    scores, _ = _score_group(text, _prohibited_matchers, 1.0)
    # "social score" has weight 5.0; single hit gives exactly 5.0 (weight * sqrt(1) * 1).
    assert scores.get("social_scoring") == 5.0


def test_prohibited_matchers_detect_predictive_policing():
    text = _normalize("predictive policing model for offender risk")
    scores, _ = _score_group(text, _prohibited_matchers, 1.0)
    assert "predictive_policing_individual" in scores


def test_weak_prohibited_hit_stays_below_threshold():
    """A lower-weight prohibited phrase alone must not clear the 4.5 threshold."""
    # "dark pattern" has weight 3.5 → sqrt(1) * 3.5 = 3.5, below 4.5.
    text = _normalize("detected a dark pattern in onboarding flow")
    scores, _ = _score_group(text, _prohibited_matchers, 1.0)
    assert scores.get("subliminal_manipulation", 0.0) < 4.5


def test_all_annex_iii_categories_have_signals():
    from agentaudit_api.models.ai_system import ANNEX_III_CATEGORIES
    from agentaudit_api.services.classification_service import _CATEGORY_SIGNALS

    for cat in ANNEX_III_CATEGORIES:
        assert cat in _CATEGORY_SIGNALS, f"Missing signals for Annex III category: {cat}"
        assert len(_CATEGORY_SIGNALS[cat]) >= 3
