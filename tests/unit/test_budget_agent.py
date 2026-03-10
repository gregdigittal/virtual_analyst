"""Unit tests for budget NL query agent."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.app.services.agent.budget_agent import run_budget_nl_query_agent


@pytest.mark.asyncio
async def test_run_budget_nl_query_agent_produces_answer() -> None:
    """run_budget_nl_query_agent returns answer and citations from plan + execute + answer steps."""
    plan_content = {"queries": [{"tool": "query_budget_summary", "args": {"budget_id": "bud_1"}}]}
    answer_content = {"answer": "Total budget is 100k.", "citations": [{"source": "query_budget_summary", "budget_id": "bud_1"}]}

    agent = MagicMock()
    agent.run_task = AsyncMock(side_effect=[
        MagicMock(content=plan_content),
        MagicMock(content=answer_content),
    ])

    with patch("apps.api.app.services.agent.budget_agent.agent_tools") as mock_tools:
        mock_tools.query_budget_summary = AsyncMock(return_value={"budget_id": "bud_1", "total_budget": 100000})

        result = await run_budget_nl_query_agent("t1", agent, "What is the total budget?")

    assert result["answer"] == "Total budget is 100k."
    assert len(result["citations"]) == 1
    assert agent.run_task.call_count == 2
    mock_tools.query_budget_summary.assert_called_once_with(tenant_id="t1", budget_id="bud_1")


@pytest.mark.asyncio
async def test_run_budget_nl_query_agent_caps_at_five_queries() -> None:
    """Query plan is capped at 5 tool executions."""
    plan_content = {
        "queries": [
            {"tool": "query_budget_summary", "args": {}},
            {"tool": "query_budget_summary", "args": {"budget_id": "b1"}},
            {"tool": "query_budget_summary", "args": {"budget_id": "b2"}},
            {"tool": "query_budget_summary", "args": {"budget_id": "b3"}},
            {"tool": "query_budget_summary", "args": {"budget_id": "b4"}},
            {"tool": "query_budget_summary", "args": {"budget_id": "b5"}},
        ],
    }
    answer_content = {"answer": "Done.", "citations": []}

    agent = MagicMock()
    agent.run_task = AsyncMock(side_effect=[
        MagicMock(content=plan_content),
        MagicMock(content=answer_content),
    ])

    with patch("apps.api.app.services.agent.budget_agent.agent_tools") as mock_tools:
        mock_tools.query_budget_summary = AsyncMock(return_value={})

        await run_budget_nl_query_agent("t1", agent, "Summarise all")

    assert mock_tools.query_budget_summary.call_count == 5


@pytest.mark.asyncio
async def test_run_budget_nl_query_agent_handles_tool_error() -> None:
    """When a tool raises, result includes error and answer step still runs."""
    plan_content = {"queries": [{"tool": "calculate_variance", "args": {"budget_id": "bud_1"}}]}
    answer_content = {"answer": "Data was unavailable.", "citations": []}

    agent = MagicMock()
    agent.run_task = AsyncMock(side_effect=[
        MagicMock(content=plan_content),
        MagicMock(content=answer_content),
    ])

    with patch("apps.api.app.services.agent.budget_agent.agent_tools") as mock_tools:
        mock_tools.calculate_variance = AsyncMock(side_effect=ValueError("Budget not found"))

        result = await run_budget_nl_query_agent("t1", agent, "What is the variance?")

    assert result["answer"] == "Data was unavailable."
    assert agent.run_task.call_count == 2


@pytest.mark.asyncio
async def test_natural_language_budget_query_fallback_when_agent_disabled() -> None:
    """When agent is disabled, nl-query uses legacy llm.complete_with_routing path."""
    from apps.api.app.routers.budgets import analytics as analytics_module

    conn = MagicMock()
    conn.fetch = AsyncMock(side_effect=[
        # 1) budget list
        [{"budget_id": "bud_1", "label": "FY24", "status": "active", "current_version_id": "v1"}],
        # 2) Q1: total budget per budget_id (batched)
        [{"budget_id": "bud_1", "total": 100000.0}],
        # 3) Q2: total actuals per budget_id (batched)
        [{"budget_id": "bud_1", "total": 5000.0}],
        # 4) Q3: department ranking per budget_id (batched)
        [{"budget_id": "bud_1", "department_ref": "Sales", "total": 5000.0}],
    ])

    @asynccontextmanager
    async def mock_tenant_conn(_tid: str):
        yield conn

    with patch.object(analytics_module, "get_agent_service", return_value=None):
        with patch.object(analytics_module, "tenant_conn", side_effect=mock_tenant_conn):
            llm = MagicMock()
            llm.complete_with_routing = AsyncMock(
                return_value=MagicMock(content={"answer": "Legacy answer.", "citations": []})
            )

            from apps.api.app.routers.budgets._common import NLQueryBody

            response = await analytics_module.natural_language_budget_query(
                NLQueryBody(question="What is the total?"),
                x_tenant_id="t1",
                llm=llm,
            )

    assert response["answer"] == "Legacy answer."
    llm.complete_with_routing.assert_called_once()
