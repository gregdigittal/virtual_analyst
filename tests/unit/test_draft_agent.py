"""Unit tests for draft assumptions agent."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.app.services.agent.draft_agent import run_draft_chat_agent


@pytest.mark.asyncio
async def test_run_draft_chat_agent_returns_proposals() -> None:
    """run_draft_chat_agent returns content with proposals from agent."""
    fake_content = {
        "proposals": [
            {"path": "assumptions.revenue_streams[0].drivers.unit_price", "value": 10.0, "evidence": "User said $10", "confidence": "high"},
        ],
        "clarification": None,
        "commentary": "Updated unit price per your input.",
    }
    agent = MagicMock()
    agent.run_task = AsyncMock(return_value=MagicMock(content=fake_content))

    workspace = {
        "assumptions": {"revenue_streams": [{"label": "Revenue", "drivers": {}}]},
        "driver_blueprint": {},
        "evidence": [],
        "chat_history": [],
    }

    result = await run_draft_chat_agent("t1", agent, workspace, "Set unit price to $10")

    assert result == fake_content
    assert result["proposals"][0]["path"] == "assumptions.revenue_streams[0].drivers.unit_price"
    agent.run_task.assert_called_once()
    call_kw = agent.run_task.call_args[1]
    assert call_kw["task_label"] == "draft_assumptions_agent"
    assert "Current Assumptions" in call_kw["prompt"]
    assert "New User Message" in call_kw["prompt"]
    assert "Set unit price to $10" in call_kw["prompt"]


@pytest.mark.asyncio
async def test_run_draft_chat_agent_includes_full_chat_history() -> None:
    """run_draft_chat_agent includes full chat history (not windowed)."""
    agent = MagicMock()
    agent.run_task = AsyncMock(return_value=MagicMock(content={"proposals": [], "clarification": None, "commentary": ""}))

    chat_history = [{"role": "user", "content": f"Message {i}"} for i in range(15)]
    workspace = {
        "assumptions": {},
        "driver_blueprint": {},
        "evidence": [],
        "chat_history": chat_history,
    }

    await run_draft_chat_agent("t1", agent, workspace, "New message")

    call_kw = agent.run_task.call_args[1]
    assert "Chat History (15 messages)" in call_kw["prompt"]
    assert "Message 0" in call_kw["prompt"]
    assert "Message 14" in call_kw["prompt"]


@pytest.mark.asyncio
async def test_run_draft_chat_agent_builds_context_from_workspace() -> None:
    """run_draft_chat_agent includes assumptions, blueprint, evidence in prompt."""
    agent = MagicMock()
    agent.run_task = AsyncMock(return_value=MagicMock(content={"proposals": [], "clarification": None, "commentary": ""}))

    workspace = {
        "assumptions": {"revenue_streams": [{"label": "Sales"}]},
        "driver_blueprint": {"nodes": [{"node_id": "n1"}]},
        "evidence": [{"source": "doc1", "excerpt": "Revenue was 100"}],
        "chat_history": [],
    }

    await run_draft_chat_agent("t1", agent, workspace, "What is the revenue assumption?")

    call_kw = agent.run_task.call_args[1]
    assert "Current Assumptions" in call_kw["prompt"]
    assert "Driver Blueprint" in call_kw["prompt"]
    assert "Evidence" in call_kw["prompt"]
    assert "Sales" in call_kw["prompt"]
    assert "doc1" in call_kw["prompt"]


@pytest.mark.asyncio
async def test_draft_chat_fallback_when_agent_disabled() -> None:
    """When agent is disabled, draft_chat uses legacy llm.complete_with_routing path."""
    from apps.api.app.routers import drafts as router_module

    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"draft_session_id": "ds1", "status": "active"})
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction.return_value = tx

    @asynccontextmanager
    async def mock_tenant_conn(_tid: str):
        yield conn

    store = MagicMock()
    store.load.return_value = {
        "assumptions": {},
        "chat_history": [],
        "driver_blueprint": {},
        "evidence": [],
        "pending_proposals": [],
    }
    store.save = MagicMock()

    llm = MagicMock()
    llm.complete_with_routing = AsyncMock(
        return_value=MagicMock(content={"proposals": [], "clarification": None, "commentary": ""})
    )

    with patch.object(router_module, "get_agent_service", return_value=None):
        with patch.object(router_module, "tenant_conn", side_effect=mock_tenant_conn):
            response = await router_module.draft_chat(
                "ds_abc123",
                router_module.ChatBody(message="Hello"),
                x_tenant_id="t1",
                x_user_id="u1",
                store=store,
                llm=llm,
            )

    assert "proposals" in response
    llm.complete_with_routing.assert_called_once()
