"""Generate a Fundamental Rights Impact Assessment (FRIA) PDF for an AI system."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fpdf import FPDF

from agentaudit_api.models.ai_system import AISystem
from agentaudit_api.services.report_pdf import _kv, _section_header

_HUMAN_REVIEW = "[HUMAN REVIEW REQUIRED]"


def generate_fria_pdf(
    *,
    system: AISystem,
    stats: dict[str, Any],
    policy: dict[str, Any],
) -> bytes:
    """Generate a FRIA PDF pre-filled from audit data.

    Args:
        system: The AI system being assessed.
        stats: Event statistics from get_system_event_stats.
        policy: The org policy dict.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(
        0, 12, "Fundamental Rights Impact Assessment (FRIA)",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0, 6, "EU AI Act - Article 27 - Deployer Obligation",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(6)

    # Section 1: System Identification
    _section_header(pdf, "1. System Identification")
    _kv(pdf, "System Name", system.name)
    _kv(pdf, "Vendor", system.vendor or "N/A")
    _kv(pdf, "Use Case", system.use_case or "N/A")
    _kv(pdf, "Description", system.description or "N/A")
    _kv(pdf, "Risk Classification", system.risk_classification)
    _kv(pdf, "Annex III Category", system.annex_iii_category or "N/A")
    _kv(pdf, "Role", system.role)
    _kv(pdf, "Agent ID Patterns", ", ".join(system.agent_id_patterns) or "None")
    pdf.ln(4)

    # Section 2: Data Processing Overview
    _section_header(pdf, "2. Data Processing Overview")
    total = stats.get("total_events", 0)
    pii = stats.get("pii_events", 0)
    _kv(pdf, "Total Events Observed", str(total))
    _kv(pdf, "Events with PII", str(pii))
    if total > 0:
        _kv(pdf, "PII Ratio", f"{pii / total:.1%}")
    pdf.ln(2)

    by_action: dict[str, int] = stats.get("by_action", {})
    if by_action:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Actions performed:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for action, count in sorted(by_action.items(), key=lambda x: -x[1]):
            pdf.cell(
                0, 5, f"  {action}: {count} events",
                new_x="LMARGIN", new_y="NEXT",
            )
    pdf.ln(2)

    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(
        0, 5,
        f"{_HUMAN_REVIEW} Describe the categories of personal data processed, "
        "the data subjects affected, and the legal basis for processing.",
    )
    pdf.ln(4)

    # Section 3: Risk Assessment
    _section_header(pdf, "3. Risk Assessment")
    by_risk: dict[str, int] = stats.get("by_risk_level", {})
    for level in ("critical", "high", "medium", "low"):
        count = by_risk.get(level, 0)
        _kv(pdf, f"  {level.capitalize()} Risk", str(count))
    pdf.ln(2)

    if by_risk.get("critical", 0) + by_risk.get("high", 0) > 0:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(200, 50, 50)
        pdf.cell(
            0, 6,
            "WARNING: High/critical risk events detected. Review required.",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # Section 4: Fundamental Rights Impact
    _section_header(pdf, "4. Fundamental Rights Impact")
    _rights_section(pdf, "Right to non-discrimination (Art 21 EU Charter)")
    _rights_section(pdf, "Right to privacy (Art 7 EU Charter)")
    _rights_section(pdf, "Protection of personal data (Art 8 EU Charter)")
    _rights_section(pdf, "Freedom of expression (Art 11 EU Charter)")
    _rights_section(pdf, "Right to an effective remedy (Art 47 EU Charter)")
    if system.annex_iii_category == "employment":
        _rights_section(pdf, "Right to fair working conditions (Art 31 EU Charter)")
        _rights_section(pdf, "Right to collective bargaining (Art 28 EU Charter)")
    pdf.ln(4)

    # Section 5: Mitigation Measures
    _section_header(pdf, "5. Mitigation Measures")
    logging_level = policy.get("logging_level", "standard")
    blocking = policy.get("blocking_rules", {})
    _kv(pdf, "Logging Level", logging_level)
    _kv(pdf, "Blocking Enabled", str(blocking.get("enabled", False)))
    if blocking.get("enabled"):
        _kv(pdf, "Block On", blocking.get("block_on", "critical"))
    pdf.ln(2)

    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(
        0, 5,
        f"{_HUMAN_REVIEW} Describe additional technical and organisational "
        "measures implemented to mitigate identified risks: access controls, "
        "human oversight procedures, data minimisation steps, bias testing.",
    )
    pdf.ln(4)

    # Section 6: Monitoring & Review
    _section_header(pdf, "6. Monitoring & Review")
    _kv(pdf, "FRIA Status", system.fria_status)
    if system.fria_completed_at:
        _kv(pdf, "Last Completed", system.fria_completed_at.strftime("%Y-%m-%d"))
    if system.fria_next_review:
        _kv(pdf, "Next Review", system.fria_next_review.strftime("%Y-%m-%d"))
    pdf.ln(2)

    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(
        0, 5,
        f"{_HUMAN_REVIEW} Define the review schedule, responsible person, "
        "and escalation procedures for this AI system.",
    )

    # Footer
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    pdf.cell(
        0, 5,
        f"Generated by AgenticAudit | {ts} | "
        "This document requires human review before submission.",
        new_x="LMARGIN", new_y="NEXT",
    )

    return bytes(pdf.output())


def _rights_section(pdf: FPDF, right_name: str) -> None:
    """Add a fundamental right assessment sub-section."""
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, right_name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(
        0, 5,
        f"  {_HUMAN_REVIEW} Assess whether this system impacts this right, "
        "describe the nature and severity of potential impact, "
        "and identify mitigation measures.",
    )
    pdf.ln(2)
