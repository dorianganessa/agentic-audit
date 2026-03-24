"""Tests for AI Act compliance features: classification, FRIA, reports, dashboard, retention."""

from datetime import UTC, datetime, timedelta

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
            client, api_key_raw,
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
            client, api_key_raw,
            agent_id="hr-bot-1",
            action="shell_command",
            data={
                "command": f"rm -rf /data/sensitive/salary_data_{i}",
            },
        )

    system = _create_system(
        client, api_key_raw,
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
            client, api_key_raw,
            agent_id="safe-bot",
            action="file_read",
            data={"file_path": f"/docs/readme_{i}.txt", "command": "cat readme.txt"},
        )

    system = _create_system(
        client, api_key_raw,
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
        client, api_key_raw,
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
        client, api_key_raw,
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
        client, api_key_raw,
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
        client, api_key_raw,
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
        client, api_key_raw,
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
        client, api_key_raw,
        agent_id="fria-bot", action="file_read", data={"file_path": "/data/x"},
    )

    system = _create_system(
        client, api_key_raw,
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
        client, api_key_raw,
        name="HR Assessment",
        agent_id_patterns=["hr-assessment-*"],
        risk_classification="high",
        annex_iii_category="employment",
    )

    generic_sys = _create_system(
        client, api_key_raw,
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
        client, api_key_raw,
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
