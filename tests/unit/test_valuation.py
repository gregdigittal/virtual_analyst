from __future__ import annotations

import math

import pytest

from shared.fm_shared.analysis.valuation import dcf_valuation, multiples_valuation


def test_dcf_basic() -> None:
    fcf = [100.0] * 12
    wacc = 0.10
    result = dcf_valuation(fcf, wacc)

    # Mid-year convention: discount at (t+0.5)/12
    expected_pv = sum(
        cf / ((1.0 + wacc) ** ((t + 0.5) / 12.0)) for t, cf in enumerate(fcf)
    )
    assert result.enterprise_value == pytest.approx(expected_pv, abs=0.01)
    assert result.pv_terminal == pytest.approx(0.0, abs=0.01)
    # Equity bridge defaults
    assert result.net_debt == 0.0
    assert result.cash == 0.0
    assert result.equity_value == result.enterprise_value


def test_dcf_zero_wacc() -> None:
    result = dcf_valuation([100.0, 100.0], 0.0)
    assert result.enterprise_value == 0.0


def test_dcf_terminal_growth() -> None:
    fcf = [10.0] * 12
    wacc = 0.10
    g = 0.02
    result = dcf_valuation(fcf, wacc, terminal_growth_rate=g)

    fcf_annual = sum(fcf)
    terminal_value = fcf_annual * (1.0 + g) / (wacc - g)
    pv_terminal = terminal_value / ((1.0 + wacc) ** (len(fcf) / 12.0))
    expected_total = result.pv_explicit + pv_terminal

    assert math.isclose(result.terminal_value, round(terminal_value, 2), abs_tol=0.01)
    assert result.pv_terminal == pytest.approx(pv_terminal, abs=0.01)
    assert result.enterprise_value == pytest.approx(expected_total, abs=0.01)


def test_dcf_mid_year_convention() -> None:
    """REM-04: Verify mid-year convention uses (t+0.5)/12 not (t+1)/12."""
    fcf = [120.0] * 12
    wacc = 0.12
    result = dcf_valuation(fcf, wacc)
    # First period should be discounted at 0.5/12, not 1/12
    expected_first_pv = 120.0 / ((1.0 + 0.12) ** (0.5 / 12.0))
    assert result.breakdown[0]["pv"] == pytest.approx(expected_first_pv, abs=0.01)


def test_dcf_terminal_multiple_fcf_fallback() -> None:
    """When no ebitda_series, terminal multiple falls back to FCF."""
    fcf = [10.0] * 12
    wacc = 0.10
    multiple = 5.0
    result = dcf_valuation(fcf, wacc, terminal_multiple=multiple)

    fcf_annual = sum(fcf)
    terminal_value = fcf_annual * multiple
    pv_terminal = terminal_value / ((1.0 + wacc) ** (len(fcf) / 12.0))
    expected_total = result.pv_explicit + pv_terminal

    assert result.terminal_value == pytest.approx(terminal_value, abs=0.01)
    assert result.pv_terminal == pytest.approx(pv_terminal, abs=0.01)
    assert result.enterprise_value == pytest.approx(expected_total, abs=0.01)


def test_dcf_terminal_multiple_ebitda() -> None:
    """REM-06: Terminal value uses EBITDA exit multiple when ebitda_series provided."""
    fcf = [10.0] * 12
    ebitda = [15.0] * 12
    wacc = 0.10
    multiple = 8.0
    result = dcf_valuation(fcf, wacc, terminal_multiple=multiple, ebitda_series=ebitda)

    ebitda_annual = sum(ebitda)
    terminal_value = ebitda_annual * multiple
    assert result.terminal_value == pytest.approx(terminal_value, abs=0.01)


def test_dcf_equity_bridge() -> None:
    """REM-05: Equity value = enterprise_value - net_debt + cash."""
    fcf = [100.0] * 12
    wacc = 0.10
    net_debt = 500.0
    cash = 200.0
    result = dcf_valuation(fcf, wacc, net_debt=net_debt, cash=cash)

    assert result.net_debt == 500.0
    assert result.cash == 200.0
    assert result.equity_value == pytest.approx(
        result.enterprise_value - 500.0 + 200.0, abs=0.01
    )


def test_multiples_basic() -> None:
    metrics = {"ebitda": 10.0, "revenue": 100.0, "net_income": 8.0}
    comparables = [
        {"name": "A", "ev_ebitda": 5.0},
        {"name": "B", "ev_ebitda": 7.0, "ev_revenue": 2.0},
        {"name": "C", "p_e": 10.0},
    ]
    result = multiples_valuation(metrics, comparables)
    assert result.implied_ev_range == (50.0, 200.0)


def test_multiples_empty_comparables() -> None:
    metrics = {"ebitda": 10.0}
    result = multiples_valuation(metrics, [])
    assert result.implied_ev_range == (0.0, 0.0)
