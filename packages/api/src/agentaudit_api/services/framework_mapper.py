"""Map audit events to compliance framework articles."""

from __future__ import annotations


def map_frameworks(
    action: str,
    risk_level: str,
    pii_detected: bool,
    reasoning: str | None,
    context: dict,
    agent_id: str,
    enabled_frameworks: dict,
) -> dict:
    """Map an event to relevant compliance framework articles.

    Args:
        enabled_frameworks: {"gdpr": True, "ai_act": True, "soc2": False}

    Returns:
        {"gdpr": ["art_30", ...], "ai_act": [...], "soc2": [...]}
    """
    result: dict[str, list[str]] = {}

    if enabled_frameworks.get("gdpr"):
        gdpr = _map_gdpr(action, pii_detected, reasoning, context)
        if gdpr:
            result["gdpr"] = gdpr

    if enabled_frameworks.get("ai_act"):
        ai_act = _map_ai_act(agent_id, risk_level, reasoning)
        if ai_act:
            result["ai_act"] = ai_act

    if enabled_frameworks.get("soc2"):
        soc2 = _map_soc2(action, risk_level, pii_detected)
        if soc2:
            result["soc2"] = soc2

    return result


def _map_gdpr(
    action: str,
    pii_detected: bool,
    reasoning: str | None,
    context: dict,
) -> list[str]:
    articles: list[str] = []

    if pii_detected:
        articles.append("art_30")  # Records of processing

    if "access" in action.lower() and pii_detected:
        articles.append("art_15")  # Right of access

    if "delete" in action.lower() and pii_detected:
        articles.append("art_17")  # Right to erasure

    if reasoning:
        articles.append("art_22")  # Automated decision-making

    if pii_detected and context.get("developer"):
        articles.append("art_13")  # Information to data subject

    return articles


def _map_ai_act(
    agent_id: str,
    risk_level: str,
    reasoning: str | None,
) -> list[str]:
    articles: list[str] = []

    if agent_id:
        articles.append("art_14")  # Human oversight

    if risk_level in ("high", "critical"):
        articles.append("art_9")  # Risk management

    if reasoning:
        articles.append("art_13")  # Transparency

    return articles


def _map_soc2(
    action: str,
    risk_level: str,
    pii_detected: bool,
) -> list[str]:
    controls: list[str] = []

    if action in ("shell_command", "file_write"):
        controls.append("CC6.1")  # Logical access

    if risk_level == "critical":
        controls.append("CC7.2")  # System incident management

    if pii_detected:
        controls.append("CC6.5")  # Data classification

    return controls
