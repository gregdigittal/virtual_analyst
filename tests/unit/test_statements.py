"""Unit tests for three-statement generator."""

from shared.fm_shared.model import generate_statements, run_engine
from shared.fm_shared.model.statements import Statements
from tests.conftest import minimal_model_config


def test_generate_statements_returns_three_lists() -> None:
    """generate_statements returns Statements with IS, BS, CF and periods."""
    config = minimal_model_config(
        horizon_months=3, tax_rate=0.25, initial_cash=50_000.0, initial_equity=100_000.0
    )
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    assert isinstance(st, Statements)
    assert len(st.income_statement) == 3
    assert len(st.balance_sheet) == 3
    assert len(st.cash_flow) == 3
    assert len(st.periods) == 3


def test_generate_statements_income_statement_keys() -> None:
    """Income statement rows have expected keys (revenue, cogs, gross_profit, ebitda, net_income, etc.)."""
    config = minimal_model_config(
        horizon_months=2, tax_rate=0.25, initial_cash=50_000.0, initial_equity=100_000.0
    )
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    row = st.income_statement[0]
    assert "revenue" in row
    assert "cogs" in row
    assert "gross_profit" in row
    assert "ebitda" in row
    assert "net_income" in row
    assert row["revenue"] == 1000.0
    assert row["cogs"] == 0.0
    assert row["gross_profit"] == 1000.0


def test_generate_statements_balance_sheet_keys() -> None:
    """Balance sheet rows have total_current_assets, total_equity, cash, etc."""
    config = minimal_model_config(
        horizon_months=2, tax_rate=0.25, initial_cash=50_000.0, initial_equity=100_000.0
    )
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    row = st.balance_sheet[0]
    assert "total_current_assets" in row
    assert "total_liabilities" in row
    assert "total_equity" in row
    assert "cash" in row
    assert "accounts_receivable" in row
    assert "inventory" in row
    assert "accounts_payable" in row


def test_generate_statements_cash_flow_keys() -> None:
    """Cash flow rows have operating, investing, financing, net_cf, closing_cash."""
    config = minimal_model_config(
        horizon_months=2, tax_rate=0.25, initial_cash=50_000.0, initial_equity=100_000.0
    )
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    row = st.cash_flow[0]
    assert "operating" in row
    assert "investing" in row
    assert "financing" in row
    assert "net_cf" in row
    assert "closing_cash" in row


def test_generate_statements_periods() -> None:
    """periods list has one string per horizon (e.g. period labels)."""
    config = minimal_model_config(
        horizon_months=4, tax_rate=0.25, initial_cash=50_000.0, initial_equity=100_000.0
    )
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    assert len(st.periods) == 4
