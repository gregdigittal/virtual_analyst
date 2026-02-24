"""Unit tests for three-statement generator."""

from __future__ import annotations

import pytest

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
    """No funding config: statements still generate; debt/dividends/equity lines present and zero."""
    config = minimal_model_config(horizon_months=3)
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    for row in st.balance_sheet:
        assert row.get("debt_current", 0.0) == 0.0
        assert row.get("debt_non_current", 0.0) == 0.0
    for row in st.cash_flow:
        assert row.get("debt_draws", 0.0) == 0.0
        assert row.get("debt_repayments", 0.0) == 0.0
        assert row.get("dividends_paid", 0.0) == 0.0
        assert row.get("equity_raised", 0.0) == 0.0
    for row in st.income_statement:
        assert row.get("dividends", 0.0) == 0.0


def test_generate_statements_fixed_amount_dividends() -> None:
    """Fixed amount dividends $10K/month: IS dividends, RE reduced, CF dividends_paid."""
    config_dict = minimal_model_config_dict(horizon_months=4, initial_equity=100_000.0)
    config_dict["assumptions"]["funding"] = {
        "equity_raises": [],
        "debt_facilities": [],
        "dividends": {"policy": "fixed_amount", "value": 10_000.0},
    }
    config = ModelConfig.model_validate(config_dict)
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    for t in range(4):
        assert st.income_statement[t]["dividends"] == 10_000.0
        assert st.cash_flow[t]["dividends_paid"] == 10_000.0
    # RE: 100k + (1000*4 - 10k*4) = 100k - 36k = 64k at end of P3
    assert st.balance_sheet[3]["total_equity"] == pytest.approx(100_000.0 + 4 * 1000.0 - 4 * 10_000.0, abs=0.02)


def test_generate_statements_payout_ratio_dividends() -> None:
    """Payout ratio 30% of NI; no dividend when NI < 0."""
    config_dict = minimal_model_config_dict(horizon_months=3, initial_equity=50_000.0)
    config_dict["assumptions"]["funding"] = {
        "equity_raises": [],
        "debt_facilities": [],
        "dividends": {"policy": "payout_ratio", "value": 0.30},
    }
    config = ModelConfig.model_validate(config_dict)
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    for t in range(3):
        ni = st.income_statement[t]["net_income"]
        expected_div = max(0.0, ni * 0.30)
        assert st.income_statement[t]["dividends"] == pytest.approx(expected_div, abs=0.01)
        assert st.cash_flow[t]["dividends_paid"] == pytest.approx(expected_div, abs=0.01)


def test_generate_statements_equity_raise() -> None:
    """Equity raise $200K at month 3: RE increases, CF equity_raised."""
    config_dict = minimal_model_config_dict(horizon_months=6, initial_equity=100_000.0)
    config_dict["assumptions"]["funding"] = {
        "equity_raises": [{"amount": 200_000.0, "month": 3, "label": "Series A"}],
        "debt_facilities": [],
        "dividends": None,
    }
    config = ModelConfig.model_validate(config_dict)
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    assert st.cash_flow[3]["equity_raised"] == 200_000.0
    for t in [0, 1, 2, 4, 5]:
        assert st.cash_flow[t]["equity_raised"] == 0.0
    # Equity at end of P2 = 100k + 3*1000; at end of P3 = that + 1000 + 200k
    assert st.balance_sheet[3]["total_equity"] > st.balance_sheet[2]["total_equity"] + 199_000.0


def test_generate_statements_combined_dividends_and_debt() -> None:
    """Dividends + debt: both applied, BS balances."""
    config_dict = minimal_model_config_dict(horizon_months=6, initial_equity=200_000.0)
    config_dict["assumptions"]["funding"] = {
        "equity_raises": [],
        "debt_facilities": [
            {
                "facility_id": "term_1",
                "label": "Term",
                "type": "term_loan",
                "limit": 100_000.0,
                "interest_rate": 0.08,
                "draw_schedule": [{"month": 0, "amount": 50_000.0}],
                "repayment_schedule": [],
                "is_cash_plug": False,
            }
        ],
        "dividends": {"policy": "fixed_amount", "value": 1_000.0},
    }
    config = ModelConfig.model_validate(config_dict)
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    for t in range(6):
        assert st.income_statement[t]["dividends"] == 1_000.0
        assert st.cash_flow[t]["dividends_paid"] == 1_000.0
    assert st.income_statement[0]["interest_expense"] > 0
    for t in range(6):
        assert abs(st.balance_sheet[t]["total_assets"] - st.balance_sheet[t]["total_liabilities_equity"]) < 0.02
