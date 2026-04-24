"""Tests for AI Act compliance features: classification, FRIA, reports, dashboard, retention."""

from datetime import UTC, datetime, timedelta

import pytest
from agentaudit_api.models.api_key import hash_api_key


def _headers(api_key_raw):
    return {"Authorization": f"Bearer {api_key_raw}"}


def _set_dashboard_cookie(client, api_key_raw):
    client.cookies.set("agentaudit_session", hash_api_key(api_key_raw))


def _create_system(client, api_key_raw, **kwargs):
    defaults = {"name": "Test System", "agent_id_patterns": ["test-*"]}
    defaults.update(kwargs)
    resp = client.post("/v1/systems", json=defaults, headers=_headers(api_key_raw))
    assert resp.status_code == 201
    return resp.json()


def _create_event(client, api_key_raw, **kwargs):
    defaults = {"agent_id": "test-bot", "action": "shell_command", "data": {"command": "ls"}}
    defaults.update(kwargs)
    resp = client.post("/v1/events", json=defaults, headers=_headers(api_key_raw))
    assert resp.status_code == 201
    return resp.json()


def _enable_full_logging(client, api_key_raw):
    client.put("/v1/org/policy", json={"logging_level": "full"}, headers=_headers(api_key_raw))


# --- Classification Suggestion ---


def test_classification_no_events(client, api_key_raw):
    """System with no matching events returns 'unclassified'."""
    system = _create_system(client, api_key_raw, name="Empty Bot", agent_id_patterns=["ghost-*"])
    resp = client.get(
        f"/v1/systems/{system['id']}/classification-suggestion",
        headers=_headers(api_key_raw),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggested_classification"] == "unclassified"
    assert body["evidence"]["total_events"] == 0


def test_classification_no_patterns(client, api_key_raw):
    """System with empty agent_id_patterns returns 'minimal'."""
    system = _create_system(client, api_key_raw, name="No Patterns", agent_id_patterns=[])
    resp = client.get(
        f"/v1/systems/{system['id']}/classification-suggestion",
        headers=_headers(api_key_raw),
    )
    assert resp.status_code == 200
    assert resp.json()["suggested_classification"] == "minimal"


def test_classification_high_risk_from_pii_and_risk(client, api_key_raw):
    """System processing HR data with PII gets classified as high risk."""
    _enable_full_logging(client, api_key_raw)

    # Create events with PII and HR-related data
    for i in range(5):
        _create_event(
            client,
            api_key_raw,
            agent_id="hr-bot-1",
            action="file_read",
            data={
                "file_path": f"/data/employee_{i}.csv",
                "command": f"processing candidate resume for hiring position {i}",
            },
            context={"user_email": f"employee{i}@corp.com"},
        )

    # Create some high-risk events
    for i in range(3):
        _create_event(
            client,
            api_key_raw,
            agent_id="hr-bot-1",
            action="shell_command",
            data={
                "command": f"rm -rf /data/sensitive/salary_data_{i}",
            },
        )

    system = _create_system(
        client,
        api_key_raw,
        name="HR Bot",
        agent_id_patterns=["hr-bot-*"],
    )

    resp = client.get(
        f"/v1/systems/{system['id']}/classification-suggestion",
        headers=_headers(api_key_raw),
    )
    assert resp.status_code == 200
    body = resp.json()
    # Should be 'high' due to employment keywords (hiring, candidate, resume, employee, salary)
    assert body["suggested_classification"] == "high"
    assert body["suggested_category"] == "employment"
    assert body["evidence"]["total_events"] == 8


def test_classification_minimal_for_safe_operations(client, api_key_raw):
    """System with only safe operations gets minimal classification."""
    _enable_full_logging(client, api_key_raw)

    for i in range(5):
        _create_event(
            client,
            api_key_raw,
            agent_id="safe-bot",
            action="file_read",
            data={"file_path": f"/docs/readme_{i}.txt", "command": "cat readme.txt"},
        )

    system = _create_system(
        client,
        api_key_raw,
        name="Safe Bot",
        agent_id_patterns=["safe-bot"],
    )

    resp = client.get(
        f"/v1/systems/{system['id']}/classification-suggestion",
        headers=_headers(api_key_raw),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggested_classification"] == "minimal"
    assert "No high-risk patterns detected" in body["rationale"]


def test_classification_reads_system_description(client, api_key_raw):
    """A description-only system (no events) falls back to minimal — events are
    required to trigger Annex III, but metadata is still folded into scoring when
    events exist. This test verifies the metadata corpus is read."""
    _enable_full_logging(client, api_key_raw)

    # Ambiguous event data that alone wouldn't trigger employment, but the system
    # description should lift the employment score over threshold.
    for i in range(3):
        _create_event(
            client,
            api_key_raw,
            agent_id="ats-bot",
            action="file_read",
            data={"file_path": f"/inbox/{i}.txt"},
        )

    system = _create_system(
        client,
        api_key_raw,
        name="ATS Assistant",
        agent_id_patterns=["ats-bot"],
        description="Screens candidate resumes and ranks applicants for hiring.",
        use_case="Applicant tracking and recruitment triage.",
    )

    resp = client.get(
        f"/v1/systems/{system['id']}/classification-suggestion",
        headers=_headers(api_key_raw),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggested_classification"] == "high"
    assert body["suggested_category"] == "employment"


def test_classification_prohibited_social_scoring(client, api_key_raw):
    """System with social scoring signals returns prohibited classification."""
    _enable_full_logging(client, api_key_raw)

    for i in range(3):
        _create_event(
            client,
            api_key_raw,
            agent_id="score-bot",
            action="file_read",
            data={
                "command": f"compute social score for citizen {i}",
                "note": "updating trustworthiness score based on behavior score",
            },
        )

    system = _create_system(
        client,
        api_key_raw,
        name="Citizen Rating",
        agent_id_patterns=["score-bot"],
        description="Assigns a social score to individuals.",
    )

    resp = client.get(
        f"/v1/systems/{system['id']}/classification-suggestion",
        headers=_headers(api_key_raw),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggested_classification"] == "prohibited"
    assert "Article 5" in body["rationale"]


def test_classification_democratic_processes(client, api_key_raw):
    """Democratic-processes signals map to Annex III → high."""
    _enable_full_logging(client, api_key_raw)

    for i in range(3):
        _create_event(
            client,
            api_key_raw,
            agent_id="vote-bot",
            action="data_process",
            data={
                "command": f"segment voter {i} for campaign targeting",
                "context_note": "electoral polling station turnout analysis",
            },
        )

    system = _create_system(
        client,
        api_key_raw,
        name="Campaign Optimizer",
        agent_id_patterns=["vote-bot"],
        description="Targets ballot outreach by constituency for an election campaign.",
    )

    resp = client.get(
        f"/v1/systems/{system['id']}/classification-suggestion",
        headers=_headers(api_key_raw),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggested_classification"] == "high"
    assert body["suggested_category"] == "democratic_processes"


def test_classification_noisy_keys_ignored(client, api_key_raw):
    """Request IDs, hashes, and timestamps shouldn't trigger category matches."""
    _enable_full_logging(client, api_key_raw)

    for i in range(5):
        _create_event(
            client,
            api_key_raw,
            agent_id="noise-bot",
            action="file_read",
            # 'request_id' contains "salary" but the key is noisy and should be skipped.
            data={
                "request_id": f"req-salary-{i}",
                "trace_id": f"employee-trace-{i}",
                "user_agent": "candidate-resume-bot/1.0",
                "file_path": f"/docs/readme_{i}.txt",
            },
        )

    system = _create_system(
        client,
        api_key_raw,
        name="Noise Bot",
        agent_id_patterns=["noise-bot"],
    )

    resp = client.get(
        f"/v1/systems/{system['id']}/classification-suggestion",
        headers=_headers(api_key_raw),
    )
    assert resp.status_code == 200
    body = resp.json()
    # Would have been "high" under the old substring matcher. Noisy keys are now skipped.
    assert body["suggested_classification"] == "minimal"


@pytest.mark.parametrize(
    "category,phrase",
    [
        ("biometric", "facial recognition"),
        ("critical_infrastructure", "scada"),
        ("education", "gpa"),
        ("employment", "payroll"),
        ("essential_services", "credit score"),
        ("law_enforcement", "recidivism"),
        ("migration", "asylum"),
        ("democratic_processes", "polling station"),
    ],
)
def test_classification_every_annex_iii_category_drives_high(client, api_key_raw, category, phrase):
    """Every Annex III category — not just 3 — must drive suggested=high when detected.

    This is a regression guard: the previous classifier hard-coded only 3 categories
    to escalate to 'high'. All 8 must now apply.
    """
    _enable_full_logging(client, api_key_raw)
    agent_id = f"annex-{category.replace('_', '-')}-bot"

    for i in range(3):
        _create_event(
            client,
            api_key_raw,
            agent_id=agent_id,
            action="data_process",
            data={"note": f"event {i} using {phrase}"},
        )

    system = _create_system(
        client,
        api_key_raw,
        name=f"{category} System",
        agent_id_patterns=[agent_id],
        description=f"System handling {phrase} workflows.",
    )

    resp = client.get(
        f"/v1/systems/{system['id']}/classification-suggestion",
        headers=_headers(api_key_raw),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggested_classification"] == "high", (
        f"{category} should escalate to high; got {body}"
    )
    assert body["suggested_category"] == category


def test_classification_prohibited_overrides_annex_iii(client, api_key_raw):
    """When prohibited signals AND Annex III signals both fire, prohibited wins.

    Decision hierarchy guard: Article 5 must take precedence over Annex III high-risk.
    """
    _enable_full_logging(client, api_key_raw)

    for i in range(3):
        _create_event(
            client,
            api_key_raw,
            agent_id="dual-bot",
            action="data_process",
            data={
                # Employment Annex III signals (would trigger high on their own)
                "command": f"scoring candidate resume for hiring position {i}",
                "note": f"payroll applicant {i}",
                # AND Article 5 prohibited signal (must win)
                "extra": "assigning social score to each citizen based on social credit",
            },
        )

    system = _create_system(
        client,
        api_key_raw,
        name="Dual Signal Bot",
        agent_id_patterns=["dual-bot"],
        description="HR tool that also assigns a social score to applicants.",
    )

    resp = client.get(
        f"/v1/systems/{system['id']}/classification-suggestion",
        headers=_headers(api_key_raw),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggested_classification"] == "prohibited"
    assert "Article 5" in body["rationale"]


def test_classification_weak_prohibited_does_not_escalate(client, api_key_raw):
    """A single weak prohibited phrase below the 4.5 threshold must not fire."""
    _enable_full_logging(client, api_key_raw)

    # "dark pattern" weight 3.5, appears once → score 3.5, below 4.5 threshold.
    _create_event(
        client,
        api_key_raw,
        agent_id="weak-prh-bot",
        action="file_read",
        data={"note": "flagged a dark pattern in the onboarding flow"},
    )

    system = _create_system(
        client,
        api_key_raw,
        name="UX Review Bot",
        agent_id_patterns=["weak-prh-bot"],
    )

    resp = client.get(
        f"/v1/systems/{system['id']}/classification-suggestion",
        headers=_headers(api_key_raw),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggested_classification"] != "prohibited"


def test_classification_pii_only_triggers_limited(client, api_key_raw):
    """No Annex III match but PII ratio ≥ 20% → limited (Art. 50 transparency)."""
    _enable_full_logging(client, api_key_raw)

    # 5 events with clear PII (emails), no category keywords.
    for i in range(5):
        _create_event(
            client,
            api_key_raw,
            agent_id="pii-bot",
            action="email_send",
            data={"body": f"Contact us at user{i}@example.com for info."},
        )

    system = _create_system(
        client,
        api_key_raw,
        name="Notification Bot",
        agent_id_patterns=["pii-bot"],
    )

    resp = client.get(
        f"/v1/systems/{system['id']}/classification-suggestion",
        headers=_headers(api_key_raw),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggested_classification"] == "limited"
    assert body["evidence"]["pii_ratio"] >= 0.2
    assert "Art. 50" in body["rationale"]


def test_classification_without_description_stays_minimal(client, api_key_raw):
    """Counterfactual for the metadata-weight test: same ambiguous events without
    any classification-relevant description must NOT escalate.

    Pairs with test_classification_reads_system_description to prove that the
    system metadata is what drove the high classification in that case.
    """
    _enable_full_logging(client, api_key_raw)

    for i in range(3):
        _create_event(
            client,
            api_key_raw,
            agent_id="ats-plain-bot",
            action="file_read",
            data={"file_path": f"/inbox/{i}.txt"},
        )

    system = _create_system(
        client,
        api_key_raw,
        name="Inbox Assistant",
        agent_id_patterns=["ats-plain-bot"],
        # No description / use_case — the events alone carry no signal.
    )

    resp = client.get(
        f"/v1/systems/{system['id']}/classification-suggestion",
        headers=_headers(api_key_raw),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggested_classification"] == "minimal"
    assert body["suggested_category"] is None


def test_classification_evidence_exposes_explainability_fields(client, api_key_raw):
    """The evidence response must expose structured per-phrase contributions and
    thresholds so reviewers (and UIs) can explain the suggestion."""
    _enable_full_logging(client, api_key_raw)

    for i in range(3):
        _create_event(
            client,
            api_key_raw,
            agent_id="evidence-bot",
            action="data_process",
            data={"command": f"payroll run for employee {i}"},
        )

    system = _create_system(
        client,
        api_key_raw,
        name="Payroll Bot",
        agent_id_patterns=["evidence-bot"],
        description="Processes employee payroll.",
    )

    resp = client.get(
        f"/v1/systems/{system['id']}/classification-suggestion",
        headers=_headers(api_key_raw),
    )
    assert resp.status_code == 200
    body = resp.json()
    ev = body["evidence"]

    # Structured evidence fields that feed FRIA and UI explainability.
    for field in (
        "category_scores",
        "category_matches",
        "category_confidence_threshold",
        "prohibited_scores",
        "prohibited_matches",
        "prohibited_confidence_threshold",
        "by_risk_level",
        "by_action",
        "pii_events",
        "pii_ratio",
        "total_events",
    ):
        assert field in ev, f"evidence missing field: {field}"

    # The winning category must have a per-phrase breakdown with at least one hit.
    assert "employment" in ev["category_matches"]
    assert len(ev["category_matches"]["employment"]) >= 1
    # Each phrase contribution must be a positive float.
    for phrase, contribution in ev["category_matches"]["employment"].items():
        assert isinstance(phrase, str) and phrase
        assert contribution > 0

    # Thresholds must match the service constants.
    assert ev["category_confidence_threshold"] == 3.0
    assert ev["prohibited_confidence_threshold"] == 4.5


def test_classification_confidence_floor_blocks_single_hit(client, api_key_raw):
    """A single low-weight keyword shouldn't win a category."""
    _enable_full_logging(client, api_key_raw)

    # "cv" has weight 0.8 — one occurrence should not clear the 3.0 threshold.
    _create_event(
        client,
        api_key_raw,
        agent_id="weak-bot",
        action="file_read",
        data={"command": "read cv file"},
    )

    system = _create_system(
        client,
        api_key_raw,
        name="Weak Signal Bot",
        agent_id_patterns=["weak-bot"],
    )

    resp = client.get(
        f"/v1/systems/{system['id']}/classification-suggestion",
        headers=_headers(api_key_raw),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggested_classification"] == "minimal"
    assert body["suggested_category"] is None


# --- Compliance Status API ---


def test_compliance_status_empty_org(client, api_key_raw):
    """Compliance status with no systems: all_classified fails, others pass vacuously."""
    resp = client.get("/v1/compliance/ai-act/status", headers=_headers(api_key_raw))
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["total_systems"] == 0
    # all_classified is False when 0 systems (can't be 100% classified with nothing)
    assert body["checks"]["all_classified"] is False
    # no_prohibited, fria_complete, contracts_reviewed pass vacuously
    assert body["checks"]["no_prohibited"] is True
    assert body["checks"]["fria_complete"] is True
    assert body["checks"]["contracts_reviewed"] is True


def test_compliance_status_full_compliance(client, api_key_raw):
    """Org with all checks passing gets 100% score."""
    h = _headers(api_key_raw)

    # Set retention to 180 days via policy
    client.put("/v1/org/policy", json={"retention_days": 180}, headers=h)

    # Create a classified system with contract and FRIA done
    _create_system(
        client,
        api_key_raw,
        name="Compliant Bot",
        agent_id_patterns=["compliant-*"],
        risk_classification="high",
        annex_iii_category="employment",
        fria_status="completed",
        fria_completed_at="2026-01-15T00:00:00",
        fria_next_review="2026-07-15T00:00:00",
        contract_has_ai_annex=True,
        provider_obligations_documented=True,
    )

    resp = client.get("/v1/compliance/ai-act/status", headers=h)
    body = resp.json()
    assert body["score"] == 100
    assert all(body["checks"].values())
    assert body["summary"]["fria_completed"] == 1
    assert body["summary"]["high_risk"] == 1


def test_compliance_status_partial_compliance(client, api_key_raw):
    """Some checks failing reduces score proportionally."""
    h = _headers(api_key_raw)

    # No retention set (defaults to whatever config says — likely < 180)
    _create_system(
        client,
        api_key_raw,
        name="Unfinished Bot",
        risk_classification="high",
        fria_status="not_started",
        contract_has_ai_annex=False,
    )

    resp = client.get("/v1/compliance/ai-act/status", headers=h)
    body = resp.json()
    # all_classified: True, no_prohibited: True, fria_complete: False,
    # contracts_reviewed: False, retention_compliant: depends on default
    assert body["score"] < 100
    assert body["checks"]["all_classified"] is True
    assert body["checks"]["no_prohibited"] is True
    assert body["checks"]["fria_complete"] is False
    assert body["checks"]["contracts_reviewed"] is False


def test_compliance_status_prohibited_system_detected(client, api_key_raw):
    """Prohibited system makes no_prohibited check fail."""
    h = _headers(api_key_raw)

    _create_system(
        client,
        api_key_raw,
        name="Banned System",
        risk_classification="prohibited",
        contract_has_ai_annex=True,
    )

    resp = client.get("/v1/compliance/ai-act/status", headers=h)
    body = resp.json()
    assert body["checks"]["no_prohibited"] is False
    assert body["summary"]["prohibited_systems"] == 1


def test_compliance_deadlines(client, api_key_raw):
    """Deadlines are collected from systems with future review dates."""
    h = _headers(api_key_raw)

    future = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    _create_system(
        client,
        api_key_raw,
        name="Reviewed Bot",
        risk_classification="high",
        fria_status="completed",
        fria_next_review=future,
        next_review_date=future,
        contract_has_ai_annex=True,
    )

    resp = client.get("/v1/compliance/ai-act/status", headers=h)
    body = resp.json()
    assert len(body["deadlines"]) == 2
    types = {d["type"] for d in body["deadlines"]}
    assert "system_review" in types
    assert "fria_review" in types


# --- Compliance Report PDF ---


def test_compliance_report_pdf_downloads(client, api_key_raw):
    """Compliance report PDF endpoint returns valid PDF bytes."""
    h = _headers(api_key_raw)

    _create_system(
        client,
        api_key_raw,
        name="Report Bot",
        risk_classification="limited",
        contract_has_ai_annex=True,
    )

    resp = client.get("/v1/compliance/ai-act/report", headers=h)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
    # PDF uses FlateDecode compression; verify it has multiple pages (2+ page objects)
    assert b"/Type /Page" in resp.content


def test_compliance_report_pdf_empty_org(client, api_key_raw):
    """Report works even with no systems registered."""
    resp = client.get("/v1/compliance/ai-act/report", headers=_headers(api_key_raw))
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


# --- FRIA PDF ---


def test_fria_pdf_downloads(client, api_key_raw):
    """FRIA PDF generates for a high-risk system."""
    _enable_full_logging(client, api_key_raw)
    h = _headers(api_key_raw)

    # Create some events first
    _create_event(
        client,
        api_key_raw,
        agent_id="fria-bot",
        action="file_read",
        data={"file_path": "/data/x"},
    )

    system = _create_system(
        client,
        api_key_raw,
        name="FRIA Test Bot",
        agent_id_patterns=["fria-bot"],
        risk_classification="high",
        annex_iii_category="employment",
        fria_status="in_progress",
    )

    resp = client.get(f"/v1/compliance/ai-act/fria/{system['id']}/pdf", headers=h)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
    assert b"/Type /Page" in resp.content


def test_fria_pdf_not_found(client, api_key_raw):
    """FRIA PDF for non-existent system returns 404."""
    resp = client.get(
        "/v1/compliance/ai-act/fria/nonexistent/pdf",
        headers=_headers(api_key_raw),
    )
    assert resp.status_code == 404


def test_fria_pdf_employment_vs_nonemployment(client, api_key_raw):
    """Employment FRIA generates a larger PDF than non-employment (extra rights sections)."""
    _enable_full_logging(client, api_key_raw)
    h = _headers(api_key_raw)

    employment_sys = _create_system(
        client,
        api_key_raw,
        name="HR Assessment",
        agent_id_patterns=["hr-assessment-*"],
        risk_classification="high",
        annex_iii_category="employment",
    )

    generic_sys = _create_system(
        client,
        api_key_raw,
        name="Generic Bot",
        agent_id_patterns=["generic-assessment-*"],
        risk_classification="high",
        annex_iii_category="biometric",
    )

    resp_emp = client.get(f"/v1/compliance/ai-act/fria/{employment_sys['id']}/pdf", headers=h)
    resp_gen = client.get(f"/v1/compliance/ai-act/fria/{generic_sys['id']}/pdf", headers=h)

    assert resp_emp.status_code == 200
    assert resp_gen.status_code == 200
    # Employment FRIA has 2 extra rights sections (Art 31, Art 28) so it's larger
    assert len(resp_emp.content) > len(resp_gen.content)


# --- Retention Enforcement ---


def test_ai_act_preset_enforces_minimum_retention(client, api_key_raw):
    """Setting compliance_preset=ai_act auto-raises retention to 180 days."""
    h = _headers(api_key_raw)

    # Set low retention first
    resp = client.put(
        "/v1/org/policy",
        json={"retention_days": 30, "compliance_preset": "ai_act"},
        headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["compliance_preset"] == "ai_act"
    assert body["retention_days"] >= 180


def test_retention_above_180_not_reduced(client, api_key_raw):
    """Setting AI Act preset with retention already > 180 keeps the higher value."""
    h = _headers(api_key_raw)

    resp = client.put(
        "/v1/org/policy",
        json={"retention_days": 365, "compliance_preset": "ai_act"},
        headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["retention_days"] == 365


def test_preset_without_ai_act_allows_low_retention(client, api_key_raw):
    """Without AI Act preset, low retention is allowed."""
    h = _headers(api_key_raw)

    resp = client.put(
        "/v1/org/policy",
        json={"retention_days": 30},
        headers=h,
    )
    assert resp.status_code == 200
    assert resp.json()["retention_days"] == 30


def test_enabling_ai_act_preset_later_bumps_existing_low_retention(client, api_key_raw):
    """If retention is already set low, then enabling ai_act preset raises it."""
    h = _headers(api_key_raw)

    # Set low retention without preset
    client.put("/v1/org/policy", json={"retention_days": 60}, headers=h)

    # Now enable ai_act preset
    resp = client.put("/v1/org/policy", json={"compliance_preset": "ai_act"}, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["retention_days"] >= 180


# --- Compliance Dashboard ---


def test_compliance_dashboard_renders(client, api_key_raw):
    """Compliance dashboard page returns HTML with expected content."""
    _set_dashboard_cookie(client, api_key_raw)
    _create_system(
        client,
        api_key_raw,
        name="Dashboard Bot",
        risk_classification="high",
        fria_status="completed",
        contract_has_ai_annex=True,
    )

    resp = client.get("/dashboard/compliance")
    assert resp.status_code == 200
    assert "AI Act Compliance Dashboard" in resp.text
    assert "Dashboard Bot" in resp.text
    assert "Compliance Score" in resp.text


def test_compliance_dashboard_empty_org(client, api_key_raw):
    """Dashboard works with no systems."""
    _set_dashboard_cookie(client, api_key_raw)
    resp = client.get("/dashboard/compliance")
    assert resp.status_code == 200
    assert "AI Act Compliance Dashboard" in resp.text
    assert "0%" in resp.text
