from __future__ import annotations

import math

import pytest

from shared.fm_shared.analysis.valuation import dcf_valuation, multiples_valuation


def test_dcf_basic() -> None:
    fcf = [100.0] * 12
    wacc = 0.10
    result = dcf_valuation(fcf, wacc)

    expected_pv = sum(
        cf / ((1.0 + wacc) ** ((t + 1) / 12.0)) for t, cf in enumerate(fcf)
    )
    assert result.enterprise_value == pytest.approx(expected_pv, abs=0.01)
    assert result.pv_terminal == pytest.approx(0.0, abs=0.01)


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


def test_dcf_terminal_multiple() -> None:
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
