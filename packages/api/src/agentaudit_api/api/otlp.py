"""OTLP-compatible endpoint for receiving OpenTelemetry log events from Cowork."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from agentaudit_api.auth.api_key import get_current_api_key
from agentaudit_api.database import get_session
from agentaudit_api.models.api_key import ApiKey
from agentaudit_api.models.event import AuditEventCreate
from agentaudit_api.services.alerter import evaluate_and_send
from agentaudit_api.services.event_service import create_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/otlp", tags=["otlp"])

# Mapping from Cowork event names to AgentAudit action types.
_EVENT_ACTION_MAP: dict[str, str] = {
    "cowork.tool_result": "connector_access",
    "cowork.tool_decision": "tool_decision",
    "cowork.user_prompt": "user_prompt",
    "cowork.api_request": "api_request",
    "cowork.api_error": "api_error",
}

# Tool names that map to specific AgentAudit actions instead of connector_access.
_TOOL_ACTION_MAP: dict[str, str] = {
    "Read": "file_read",
    "Write": "file_write",
    "Edit": "file_write",
    "Bash": "shell_command",
    "Glob": "file_read",
    "Grep": "file_read",
    "WebFetch": "web_browse",
    "WebSearch": "web_search",
    "Agent": "sub_agent_spawn",
}


def _extract_attributes(attrs: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert OTLP key-value attribute list to a flat dict.

    OTLP attributes are encoded as:
      [{"key": "k", "value": {"stringValue": "v"}}, ...]
    """
    result: dict[str, Any] = {}
    for attr in attrs:
        key = attr.get("key", "")
        value_obj = attr.get("value", {})
        if "stringValue" in value_obj:
            result[key] = value_obj["stringValue"]
        elif "intValue" in value_obj:
            result[key] = int(value_obj["intValue"])
        elif "doubleValue" in value_obj:
            result[key] = value_obj["doubleValue"]
        elif "boolValue" in value_obj:
            result[key] = value_obj["boolValue"]
        elif "arrayValue" in value_obj:
            result[key] = [
                v.get("stringValue", v) for v in value_obj["arrayValue"].get("values", [])
            ]
        elif "kvlistValue" in value_obj:
            result[key] = _extract_attributes(
                value_obj["kvlistValue"].get("values", [])
            )
    return result


def _parse_tool_parameters(raw: str | dict[str, Any] | None) -> dict[str, Any]:
    """Parse tool_parameters which may be a JSON string or already a dict."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)  # type: ignore[no-any-return]
    except (json.JSONDecodeError, TypeError):
        return {"raw": raw}


def _map_log_record(
    record_attrs: dict[str, Any],
    resource_attrs: dict[str, Any],
) -> AuditEventCreate | None:
    """Map a single OTLP log record to an AuditEventCreate.

    Returns None if the record should be skipped.
    """
    event_name = record_attrs.get("event.name", "")
    if not event_name:
        return None

    # Determine AgentAudit action
    tool_name = record_attrs.get("tool_name", "")
    if event_name == "cowork.tool_result" and tool_name in _TOOL_ACTION_MAP:
        action = _TOOL_ACTION_MAP[tool_name]
    else:
        action = _EVENT_ACTION_MAP.get(event_name, "unknown")

    # Build agent_id from resource/record attributes
    agent_id = resource_attrs.get("service.name", "cowork")

    # Build data payload
    data: dict[str, Any] = {}
    if tool_name:
        data["tool_name"] = tool_name
    if record_attrs.get("tool_parameters"):
        data["tool_parameters"] = _parse_tool_parameters(record_attrs["tool_parameters"])
    if record_attrs.get("success") is not None:
        data["success"] = record_attrs["success"]
    if record_attrs.get("duration_ms") is not None:
        data["duration_ms"] = record_attrs["duration_ms"]
    if record_attrs.get("mcp_server_scope"):
        data["mcp_server_scope"] = record_attrs["mcp_server_scope"]
        # For MCP tools, extract connector name from tool_name (mcp__connector__operation)
        if tool_name.startswith("mcp__"):
            parts = tool_name.split("__", 2)
            if len(parts) >= 3:
                data["connector"] = parts[1]
                data["operation"] = parts[2]

    # Build context
    context: dict[str, Any] = {}
    if record_attrs.get("session.id"):
        context["session_id"] = record_attrs["session.id"]
    if record_attrs.get("organization.id"):
        context["organization_id"] = record_attrs["organization.id"]
    if record_attrs.get("user.email"):
        context["user_email"] = record_attrs["user.email"]
    if record_attrs.get("user.id"):
        context["user_id"] = record_attrs["user.id"]
    if record_attrs.get("user.account_uuid"):
        context["user_account_uuid"] = record_attrs["user.account_uuid"]
    if record_attrs.get("prompt.id"):
        context["prompt_id"] = record_attrs["prompt.id"]
    if record_attrs.get("event.sequence") is not None:
        context["event_sequence"] = record_attrs["event.sequence"]
    context["source"] = "otlp"
    context["otlp_event_name"] = event_name

    return AuditEventCreate(
        agent_id=agent_id,
        action=action,
        data=data,
        context=context,
    )


def _get_alert_rules(session: Session, api_key: ApiKey) -> list[dict[str, Any]]:
    """Get alert_rules from the org policy."""
    if not api_key.org_id:
        return []
    from agentaudit_api.models.organization import Organization

    org = session.query(Organization).filter(Organization.id == api_key.org_id).first()  # type: ignore[arg-type]
    if org is None:
        return []
    return org.policy.get("alert_rules", [])  # type: ignore[no-any-return]


@router.post(
    "/v1/logs",
    summary="Receive OTLP logs",
    description=(
        "OTLP-compatible endpoint that receives OpenTelemetry log records "
        "(ExportLogsServiceRequest JSON format). Used by Cowork for event ingestion."
    ),
    responses={
        200: {"description": "Events accepted"},
        401: {"description": "Invalid or missing API key"},
        422: {"description": "Invalid OTLP payload"},
    },
)
async def receive_otlp_logs(
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: ApiKey = Depends(get_current_api_key),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Receive OTLP ExportLogsServiceRequest and map to AgentAudit events."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid JSON payload",
        )

    resource_logs = body.get("resourceLogs", [])
    results: list[dict[str, Any]] = []
    errors = 0

    alert_rules = _get_alert_rules(session, api_key)

    for rl in resource_logs:
        resource_attrs = _extract_attributes(
            rl.get("resource", {}).get("attributes", [])
        )
        for scope_log in rl.get("scopeLogs", []):
            for log_record in scope_log.get("logRecords", []):
                record_attrs = _extract_attributes(
                    log_record.get("attributes", [])
                )

                event_create = _map_log_record(record_attrs, resource_attrs)
                if event_create is None:
                    continue

                try:
                    result = create_event(
                        session,
                        event_create,
                        api_key_id=api_key.id,
                        org_id=api_key.org_id,
                    )
                    results.append({
                        "id": result.id,
                        "action": result.action,
                        "risk_level": result.risk_level,
                        "stored": result.stored,
                    })

                    if alert_rules:
                        event_dict = result.model_dump(mode="json")
                        background_tasks.add_task(evaluate_and_send, alert_rules, event_dict)

                except Exception:
                    logger.exception("Failed to process OTLP log record")
                    errors += 1

    logger.info(
        "OTLP ingest: %d events processed, %d errors",
        len(results),
        errors,
    )

    return {
        "partialSuccess": {
            "rejectedLogRecords": errors,
        } if errors else None,
        "accepted": len(results),
        "events": results,
    }
