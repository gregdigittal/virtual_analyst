"""Unit tests for budget reforecast agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.app.services.agent.reforecast_agent import run_reforecast_agent


@pytest.mark.asyncio
async def test_run_reforecast_agent_returns_revisions() -> None:
    """run_reforecast_agent returns content with revisions from agent."""
    fake_content = {
        "revisions": [
            {
                "account_ref": "acct_1",
                "amounts": [{"period_ordinal": 4, "amount": 12000.0}],
                "confidence": 0.85,
                "variance_note": "Run-rate slightly above budget.",
            },
        ],
    }
    agent = MagicMock()
    agent.run_task = AsyncMock(return_value=MagicMock(content=fake_content))

    ytd_actuals = [{"period_ordinal": 1, "account_ref": "acct_1", "amount": 10000.0}]
    remaining_by_account = {"acct_1": [{"period_ordinal": 4, "amount": 10000.0}]}

    result = await run_reforecast_agent("t1", agent, "bud_1", ytd_actuals, remaining_by_account)

    assert result["revisions"][0]["account_ref"] == "acct_1"
    assert result["revisions"][0]["amounts"][0]["amount"] == 12000.0
    agent.run_task.assert_called_once()
    call_kw = agent.run_task.call_args[1]
    assert call_kw["task_label"] == "budget_reforecast_agent"
    assert "YTD Actuals" in call_kw["prompt"]
    assert "Remaining Periods by Account" in call_kw["prompt"]


@pytest.mark.asyncio
async def test_run_reforecast_agent_includes_variance_context() -> None:
    """Variance data from calculate_variance is included in the prompt."""
    agent = MagicMock()
    agent.run_task = AsyncMock(return_value=MagicMock(content={"revisions": []}))

    with patch("apps.api.app.services.agent.reforecast_agent.agent_tools") as mock_tools:
        mock_tools.calculate_variance = AsyncMock(
            return_value={"variances": [{"account_ref": "A1", "budget": 100, "actual": 95, "variance": -5}]}
        )

        await run_reforecast_agent("t1", agent, "bud_1", [], {})

    call_kw = agent.run_task.call_args[1]
    assert "Current Variance Analysis" in call_kw["prompt"]
    assert "A1" in call_kw["prompt"]


@pytest.mark.asyncio
async def test_run_reforecast_agent_handles_variance_tool_failure() -> None:
    """When calculate_variance raises, prompt still includes empty variance section."""
    agent = MagicMock()
    agent.run_task = AsyncMock(return_value=MagicMock(content={"revisions": []}))

    with patch("apps.api.app.services.agent.reforecast_agent.agent_tools") as mock_tools:
        mock_tools.calculate_variance = AsyncMock(side_effect=RuntimeError("DB error"))

        result = await run_reforecast_agent("t1", agent, "bud_1", [], {})

    assert result["revisions"] == []
    call_kw = agent.run_task.call_args[1]
    assert "Current Variance Analysis" in call_kw["prompt"]


@pytest.mark.asyncio
async def test_reforecast_budget_fallback_when_agent_disabled() -> None:
    """When agent is disabled, reforecast uses legacy llm.complete_with_routing path."""
    from contextlib import asynccontextmanager

    from apps.api.app.routers import budgets as router_module

    conn = MagicMock()
    conn.fetch = AsyncMock(side_effect=[
        [{"period_ordinal": 1}],
        [{"line_item_id": "li1", "account_ref": "acct1", "notes": "", "is_revenue": False}],
        [{"line_item_id": "li1", "account_ref": "acct1", "period_ordinal": 1, "amount": 1000.0}, {"line_item_id": "li1", "account_ref": "acct1", "period_ordinal": 2, "amount": 2000.0}],
        [{"period_ordinal": 1, "account_ref": "acct1", "total": 1000.0}],
        [{"line_item_id": "li1", "account_ref": "acct1", "period_ordinal": 2, "amount": 2000.0}],
    ])
    conn.fetchval = AsyncMock(return_value=2)
    conn.execute = AsyncMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction.return_value = tx

    @asynccontextmanager
    async def mock_tenant_conn(_tid: str):
        yield conn

    mock_get_budget = AsyncMock(return_value={"budget_id": "b1", "current_version_id": "v1"})

    with patch.object(router_module, "get_agent_service", return_value=None):
        with patch.object(router_module, "tenant_conn", side_effect=mock_tenant_conn):
            with patch.object(router_module, "get_budget", mock_get_budget):
                with patch.object(router_module, "ensure_budget_version", new_callable=AsyncMock):
                    llm = MagicMock()
                    llm.complete_with_routing = AsyncMock(
                        return_value=MagicMock(content={"revisions": [{"account_ref": "acct1", "amounts": []}]})
                    )

                    response = await router_module.reforecast_budget(
                        "bud_1",
                        x_tenant_id="t1",
                        x_user_id="u1",
                        llm=llm,
                    )

    assert response["budget_id"] == "bud_1"
    llm.complete_with_routing.assert_called_once()
