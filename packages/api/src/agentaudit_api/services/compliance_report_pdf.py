"""Generate an org-wide AI Act compliance report PDF."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fpdf import FPDF

from agentaudit_api.models.ai_system import AISystem
from agentaudit_api.services.report_pdf import _kv, _section_header


def generate_compliance_report(
    *,
    systems: list[AISystem],
    system_stats: dict[str, dict[str, Any]],
    policy: dict[str, Any],
    retention_days: int,
    oldest_event_date: datetime | None,
    total_events: int,
) -> bytes:
    """Generate an AI Act compliance report PDF.

    Args:
        systems: All active AI systems for the org.
        system_stats: Per-system event stats keyed by system ID.
        policy: The org policy dict.
        retention_days: Configured retention period.
        oldest_event_date: Earliest event timestamp.
        total_events: Total events across all systems.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(
        0, 12, "AI Act Compliance Report",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0, 6,
        f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(8)

    # Section 1: Executive Summary
    _section_header(pdf, "1. Executive Summary")
    _kv(pdf, "Registered AI Systems", str(len(systems)))
    _kv(pdf, "Total Audit Events", str(total_events))

    classified = sum(1 for s in systems if s.risk_classification != "unclassified")
    _kv(pdf, "Systems Classified", f"{classified}/{len(systems)}")

    fria_done = sum(1 for s in systems if s.fria_status == "completed")
    high_risk = [s for s in systems if s.risk_classification == "high"]
    fria_required = len(high_risk)
    _kv(pdf, "FRIA Completed", f"{fria_done}/{max(fria_required, fria_done)}")

    contracts_ok = sum(1 for s in systems if s.contract_has_ai_annex)
    _kv(pdf, "AI Annexes in Contracts", f"{contracts_ok}/{len(systems)}")

    # Compliance score
    score = _compute_score(systems, retention_days)
    pdf.ln(2)
    _kv(pdf, "Compliance Score", f"{score}%")
    pdf.ln(6)

    # Section 2: Systems Inventory
    _section_header(pdf, "2. AI Systems Inventory (Art 26.5)")
    if systems:
        _systems_table(pdf, systems)
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(
            0, 6, "No AI systems registered.",
            new_x="LMARGIN", new_y="NEXT",
        )
    pdf.ln(6)

    # Section 3: Risk Distribution
    _section_header(pdf, "3. Risk Classification")
    counts: dict[str, int] = {}
    for s in systems:
        counts[s.risk_classification] = counts.get(s.risk_classification, 0) + 1
    for cls in ("prohibited", "high", "limited", "minimal", "unclassified"):
        _kv(pdf, f"  {cls.capitalize()}", str(counts.get(cls, 0)))
    pdf.ln(4)

    if any(s.risk_classification == "prohibited" for s in systems):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(200, 50, 50)
        pdf.cell(
            0, 6,
            "ALERT: Prohibited AI systems detected. "
            "Immediate action required (Art 5).",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # Section 4: FRIA Status
    _section_header(pdf, "4. Fundamental Rights Impact Assessments (Art 27)")
    fria_counts: dict[str, int] = {}
    for s in high_risk:
        fria_counts[s.fria_status] = fria_counts.get(s.fria_status, 0) + 1

    if high_risk:
        for fria_status in ("completed", "in_progress", "not_started", "due_for_review"):
            label = fria_status.replace("_", " ").title()
            _kv(pdf, f"  {label}", str(fria_counts.get(fria_status, 0)))
        pdf.ln(2)
        for s in high_risk:
            pdf.set_font("Helvetica", "", 9)
            review = s.fria_next_review.strftime("%Y-%m-%d") if s.fria_next_review else "Not set"
            pdf.cell(
                0, 5,
                f"  {s.name}: {s.fria_status} (next review: {review})",
                new_x="LMARGIN", new_y="NEXT",
            )
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(
            0, 6, "No high-risk systems requiring FRIA.",
            new_x="LMARGIN", new_y="NEXT",
        )
    pdf.ln(6)

    # Section 5: Vendor Contracts
    _section_header(pdf, "5. Vendor Contract Compliance (Art 26)")
    for s in systems:
        annex = "Yes" if s.contract_has_ai_annex else "NO"
        oblig = "Yes" if s.provider_obligations_documented else "NO"
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(
            0, 5,
            f"  {s.name} ({s.vendor or 'N/A'}): "
            f"AI Annex={annex}, Obligations Documented={oblig}",
            new_x="LMARGIN", new_y="NEXT",
        )
    pdf.ln(6)

    # Section 6: Activity Logging & Retention (Art 12)
    _section_header(pdf, "6. Activity Logging & Retention (Art 12)")
    _kv(pdf, "Logging Level", policy.get("logging_level", "standard"))
    _kv(pdf, "Retention Period", f"{retention_days} days")
    meets_requirement = retention_days >= 180
    _kv(
        pdf, "Meets 6-month Requirement",
        "Yes" if meets_requirement else "NO - must be >= 180 days",
    )
    if oldest_event_date:
        _kv(pdf, "Oldest Event", oldest_event_date.strftime("%Y-%m-%d %H:%M UTC"))
    pdf.ln(6)

    # Section 7: Governance
    _section_header(pdf, "7. AI Governance")
    preset = policy.get("compliance_preset")
    _kv(pdf, "Compliance Preset", preset or "None")
    blocking = policy.get("blocking_rules", {})
    _kv(pdf, "Blocking Enabled", str(blocking.get("enabled", False)))
    frameworks = policy.get("frameworks", {})
    enabled_fw = [k for k, v in frameworks.items() if v]
    _kv(pdf, "Active Frameworks", ", ".join(enabled_fw) or "None")

    # Footer
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    pdf.cell(
        0, 5,
        f"Generated by AgenticAudit | {ts} | "
        "Regulation (EU) 2024/1689 (AI Act)",
        new_x="LMARGIN", new_y="NEXT",
    )

    return bytes(pdf.output())


def _compute_score(systems: list[AISystem], retention_days: int) -> int:
    """Compute a simple compliance percentage (0-100)."""
    if not systems:
        return 0

    checks: list[bool] = []

    # All systems classified
    checks.append(all(s.risk_classification != "unclassified" for s in systems))
    # No prohibited systems
    checks.append(not any(s.risk_classification == "prohibited" for s in systems))
    # All high-risk systems have FRIA completed
    high = [s for s in systems if s.risk_classification == "high"]
    if high:
        checks.append(all(s.fria_status == "completed" for s in high))
    else:
        checks.append(True)
    # All systems have AI annex
    checks.append(all(s.contract_has_ai_annex for s in systems))
    # Retention >= 180 days
    checks.append(retention_days >= 180)

    return int(sum(checks) / len(checks) * 100)


def _systems_table(pdf: FPDF, systems: list[AISystem]) -> None:
    """Render a systems inventory table."""
    pdf.set_font("Helvetica", "B", 8)
    col_w = [50, 35, 25, 30, 25, 25]
    headers = ["Name", "Vendor", "Risk", "Category", "FRIA", "Contract"]
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 6, h, border=1)
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for s in systems:
        pdf.cell(col_w[0], 5, s.name[:25], border=1)
        pdf.cell(col_w[1], 5, (s.vendor or "")[:18], border=1)
        pdf.cell(col_w[2], 5, s.risk_classification[:12], border=1)
        pdf.cell(col_w[3], 5, (s.annex_iii_category or "-")[:15], border=1)
        pdf.cell(col_w[4], 5, s.fria_status[:12], border=1)
        annex = "Yes" if s.contract_has_ai_annex else "No"
        pdf.cell(col_w[5], 5, annex, border=1)
        pdf.ln()
