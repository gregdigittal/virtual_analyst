"""Unit tests for three-statement generator."""

from __future__ import annotations

from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.model.statements import Statements
from tests.conftest import minimal_model_config, minimal_model_config_dict


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


def test_generate_statements_with_debt_facilities() -> None:
    """With funding.debt_facilities: IS has interest_expense > 0, BS has debt lines, CF has debt_draws/repayments, BS balances."""
    config_dict = minimal_model_config_dict(horizon_months=12, initial_equity=500_000.0)
    config_dict["assumptions"]["funding"] = {
        "equity_raises": [],
        "debt_facilities": [
            {
                "facility_id": "term_1",
                "label": "Term Loan",
                "type": "term_loan",
                "limit": 1_000_000.0,
                "interest_rate": 0.08,
                "draw_schedule": [{"month": 0, "amount": 400_000.0}],
                "repayment_schedule": [{"month": m, "amount": 33_333.0} for m in range(1, 13)],
                "is_cash_plug": False,
            }
        ],
        "dividends": None,
    }
    config = ModelConfig.model_validate(config_dict)
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    assert st.income_statement[0]["interest_expense"] > 0
    row_bs = st.balance_sheet[0]
    assert "debt_current" in row_bs
    assert "debt_non_current" in row_bs
    assert "total_current_liabilities" in row_bs
    row_cf = st.cash_flow[0]
    assert "debt_draws" in row_cf
    assert "debt_repayments" in row_cf
    for t in range(len(st.balance_sheet)):
        tot_assets = st.balance_sheet[t]["total_assets"]
        tot_liab_equity = st.balance_sheet[t]["total_liabilities_equity"]
        assert abs(tot_assets - tot_liab_equity) < 0.02, f"BS balance at period {t}"


def test_generate_statements_no_funding_backward_compat() -> None:
    """No funding config: statements still generate; debt lines present and zero."""
    config = minimal_model_config(horizon_months=3)
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    for row in st.balance_sheet:
        assert row.get("debt_current", 0.0) == 0.0
        assert row.get("debt_non_current", 0.0) == 0.0
    for row in st.cash_flow:
        assert row.get("debt_draws", 0.0) == 0.0
        assert row.get("debt_repayments", 0.0) == 0.0
