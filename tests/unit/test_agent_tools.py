"""Unit tests for agent tools (tenant-scoped budget/model/run tools)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.app.services.agent import tools as agent_tools


@pytest.mark.asyncio
async def test_query_budget_summary_list() -> None:
    """query_budget_summary without budget_id returns list of budgets."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {
                "budget_id": "b1",
                "label": "FY25",
                "fiscal_year": "2025",
                "status": "draft",
                "created_at": None,
            }
        ]
    )

    @asynccontextmanager
    async def mock_tenant_conn(_tid: str):
        yield conn

    with patch("apps.api.app.services.agent.tools.tenant_conn", side_effect=mock_tenant_conn):
        out = await agent_tools.query_budget_summary("t1")
    assert "budgets" in out
    assert len(out["budgets"]) == 1
    assert out["budgets"][0]["budget_id"] == "b1"


@pytest.mark.asyncio
async def test_query_budget_summary_single_not_found() -> None:
    """query_budget_summary with budget_id returns error when not found."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)

    @asynccontextmanager
    async def mock_tenant_conn(_tid: str):
        yield conn

    with patch("apps.api.app.services.agent.tools.tenant_conn", side_effect=mock_tenant_conn):
        out = await agent_tools.query_budget_summary("t1", budget_id="missing")
    assert out.get("error") == "Budget missing not found"


@pytest.mark.asyncio
async def test_query_budget_line_items_budget_not_found() -> None:
    """query_budget_line_items returns error when budget not found."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)

    @asynccontextmanager
    async def mock_tenant_conn(_tid: str):
        yield conn

    with patch("apps.api.app.services.agent.tools.tenant_conn", side_effect=mock_tenant_conn):
        out = await agent_tools.query_budget_line_items("t1", "b1")
    assert out.get("error") == "Budget b1 not found"


@pytest.mark.asyncio
async def test_query_budget_actuals_returns_structure() -> None:
    """query_budget_actuals returns actuals list."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    @asynccontextmanager
    async def mock_tenant_conn(_tid: str):
        yield conn

    with patch("apps.api.app.services.agent.tools.tenant_conn", side_effect=mock_tenant_conn):
        out = await agent_tools.query_budget_actuals("t1", "b1")
    assert "actuals" in out
    assert out["actuals"] == []


@pytest.mark.asyncio
async def test_calculate_variance_budget_not_found() -> None:
    """calculate_variance returns error when budget not found."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)

    @asynccontextmanager
    async def mock_tenant_conn(_tid: str):
        yield conn

    with patch("apps.api.app.services.agent.tools.tenant_conn", side_effect=mock_tenant_conn):
        out = await agent_tools.calculate_variance("t1", "b1")
    assert out.get("error") == "Budget b1 not found"


@pytest.mark.asyncio
async def test_query_model_state_no_baselines() -> None:
    """query_model_state with no baseline_id returns baselines list from DB."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    @asynccontextmanager
    async def mock_tenant_conn(_tid: str):
        yield conn

    with patch("apps.api.app.services.agent.tools.tenant_conn", side_effect=mock_tenant_conn):
        out = await agent_tools.query_model_state("t1")
    assert "baselines" in out
    assert out["baselines"] == []


def test_compute_kpis_from_statements_valid() -> None:
    """compute_kpis_from_statements returns KPIs for valid statements dict."""
    from tests.conftest import minimal_model_config_dict
    from shared.fm_shared.model import ModelConfig, generate_statements
    from shared.fm_shared.model.engine import run_engine

    config_dict = minimal_model_config_dict()
    config = ModelConfig.model_validate(config_dict)
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    stmt_dict = {
        "income_statement": statements.income_statement,
        "balance_sheet": statements.balance_sheet,
        "cash_flow": statements.cash_flow,
        "periods": statements.periods,
    }
    kpis = agent_tools.compute_kpis_from_statements(stmt_dict)
    assert isinstance(kpis, list)
    assert len(kpis) == len(statements.periods)
    assert "gross_margin_pct" in kpis[0] or "period_index" in kpis[0]


def test_compute_kpis_from_statements_invalid() -> None:
    """compute_kpis_from_statements returns error dict on invalid input."""
    kpis = agent_tools.compute_kpis_from_statements({"invalid": "data"})
    assert len(kpis) == 1
    assert "error" in kpis[0]
