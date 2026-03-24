"""Slack alert service: evaluates alert rules and fires webhooks."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from agentaudit_api.services.risk_scorer import RISK_LEVELS

logger = logging.getLogger(__name__)

_RISK_ORDER: dict[str, int] = {level: i for i, level in enumerate(RISK_LEVELS)}


ALLOWED_WEBHOOK_HOSTS = {"hooks.slack.com"}


def _is_valid_webhook_url(url: str) -> bool:
    """Validate that a webhook URL points to an allowed host."""
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname is not None
            and parsed.hostname in ALLOWED_WEBHOOK_HOSTS
        )
    except Exception:
        return False


def _matches_rule(rule: dict[str, Any], event: dict[str, Any]) -> bool:
    """Check if an event matches all conditions in an alert rule (AND logic).

    Args:
        rule: Alert rule with ``condition`` and ``notify`` keys.
        event: Serialized audit event.
    """
    condition: dict[str, Any] = rule.get("condition", {})
    if not condition:
        return False

    if "risk_level_gte" in condition:
        threshold = condition["risk_level_gte"]
        event_risk = _RISK_ORDER.get(event.get("risk_level", "low"), 0)
        threshold_risk = _RISK_ORDER.get(threshold, 0)
        if event_risk < threshold_risk:
            return False

    if (
        "action_contains" in condition
        and condition["action_contains"].lower() not in event.get("action", "").lower()
    ):
        return False

    if "pii_detected" in condition and event.get("pii_detected") != condition["pii_detected"]:
        return False

    return not ("agent_id_eq" in condition and event.get("agent_id") != condition["agent_id_eq"])


def _build_slack_payload(rule: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Build the Slack webhook JSON payload.

    Args:
        rule: The matched alert rule.
        event: The audit event that triggered the alert.
    """
    rule_name = rule.get("name", "Unnamed rule")
    risk_level = event.get("risk_level", "unknown")
    agent_id = event.get("agent_id", "unknown")
    action = event.get("action", "unknown")
    pii = event.get("pii_detected", False)
    created_at = event.get("created_at", "unknown")

    return {
        "text": f"AgenticAudit Alert: {rule_name}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{risk_level} risk action detected*\n"
                        f"*Agent:* {agent_id}\n"
                        f"*Action:* {action}\n"
                        f"*Risk:* {risk_level}\n"
                        f"*PII:* {pii}\n"
                        f"*Time:* {created_at}"
                    ),
                },
            }
        ],
    }


def evaluate_and_send(alert_rules: list[dict[str, Any]], event: dict[str, Any]) -> None:
    """Evaluate alert rules against an event and send matching Slack webhooks.

    This is meant to be called from FastAPI BackgroundTasks (fire-and-forget).

    Args:
        alert_rules: List of alert rule dicts from the org policy.
        event: Serialized audit event dict.
    """
    for rule in alert_rules:
        if not _matches_rule(rule, event):
            continue

        webhook_url: str | None = rule.get("notify", {}).get("slack_webhook_url")
        if not webhook_url:
            continue

        if not _is_valid_webhook_url(webhook_url):
            logger.warning("Blocked webhook to non-allowlisted URL: %s", webhook_url[:60])
            continue

        payload = _build_slack_payload(rule, event)
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(webhook_url, json=payload)
                resp.raise_for_status()
                logger.info("Slack alert sent for rule '%s'", rule.get("name"))
        except Exception:
            logger.exception("Failed to send Slack alert for rule '%s'", rule.get("name"))
