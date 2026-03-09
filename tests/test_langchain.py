"""Tests for LangChain callback handler integration."""

from uuid import uuid4

import httpx
from agentaudit.integrations.langchain import AgentAuditCallbackHandler
from starlette.testclient import TestClient


def _make_handler(app, api_key_raw: str) -> AgentAuditCallbackHandler:
    """Create a handler wired to the test app."""
    tc = TestClient(app)
    handler = AgentAuditCallbackHandler(api_key=api_key_raw, agent_id="test-lc-agent")
    # Patch the internal SDK client to use test transport
    handler.audit._client = httpx.Client(
        transport=tc._transport,
        base_url=str(tc.base_url).rstrip("/"),
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    return handler


def test_langchain_on_tool_start(app, api_key_raw):
    """on_tool_start logs a tool_start event."""
    handler = _make_handler(app, api_key_raw)

    # Set full policy
    tc = TestClient(app)
    tc.put(
        "/v1/org/policy",
        json={"logging_level": "full"},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )

    run_id = uuid4()
    handler.on_tool_start(
        serialized={"name": "search_tool"},
        input_str="what is the weather",
        run_id=run_id,
    )

    # Verify event was created
    resp = tc.get("/v1/events", headers={"Authorization": f"Bearer {api_key_raw}"})
    events = resp.json()["events"]
    tool_events = [e for e in events if e["action"] == "tool_start"]
    assert len(tool_events) >= 1
    assert tool_events[0]["data"]["tool_name"] == "search_tool"
    assert tool_events[0]["agent_id"] == "test-lc-agent"


def test_langchain_on_tool_end(app, api_key_raw):
    """on_tool_end logs a tool_end event."""
    handler = _make_handler(app, api_key_raw)

    tc = TestClient(app)
    tc.put(
        "/v1/org/policy",
        json={"logging_level": "full"},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )

    run_id = uuid4()
    # First start, then end
    handler.on_tool_start(
        serialized={"name": "calculator"},
        input_str="2+2",
        run_id=run_id,
    )
    handler.on_tool_end(
        output="4",
        run_id=run_id,
    )

    resp = tc.get("/v1/events", headers={"Authorization": f"Bearer {api_key_raw}"})
    events = resp.json()["events"]
    end_events = [e for e in events if e["action"] == "tool_end"]
    assert len(end_events) >= 1
    assert end_events[0]["data"]["tool_name"] == "calculator"
    assert end_events[0]["data"]["output"] == "4"


def test_langchain_on_chain_start(app, api_key_raw):
    """on_chain_start logs a chain_start event."""
    handler = _make_handler(app, api_key_raw)

    tc = TestClient(app)
    tc.put(
        "/v1/org/policy",
        json={"logging_level": "full"},
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )

    run_id = uuid4()
    handler.on_chain_start(
        serialized={"name": "RetrievalQA", "id": ["langchain", "chains", "RetrievalQA"]},
        inputs={"query": "what is agentaudit?"},
        run_id=run_id,
    )

    resp = tc.get("/v1/events", headers={"Authorization": f"Bearer {api_key_raw}"})
    events = resp.json()["events"]
    chain_events = [e for e in events if e["action"] == "chain_start"]
    assert len(chain_events) >= 1
    assert chain_events[0]["data"]["chain_name"] == "RetrievalQA"
