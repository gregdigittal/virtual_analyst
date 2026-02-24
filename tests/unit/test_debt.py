"""Unit tests for debt schedule calculation."""

from __future__ import annotations

import pytest

from shared.fm_shared.model.debt import (
    DebtScheduleResult,
    calculate_debt_schedule,
    empty_debt_result,
)
from shared.fm_shared.model.schemas import DebtFacility, DrawRepayPoint


def _make_facility(
    facility_id: str = "term_1",
    limit: float = 1_000_000.0,
    interest_rate: float = 0.08,
    draw_schedule: list[tuple[int, float]] | None = None,
    repayment_schedule: list[tuple[int, float]] | None = None,
    is_cash_plug: bool = False,
) -> DebtFacility:
    draws = (
        [DrawRepayPoint(month=m, amount=a) for m, a in draw_schedule]
        if draw_schedule
        else None
    )
    repays = (
        [DrawRepayPoint(month=m, amount=a) for m, a in repayment_schedule]
        if repayment_schedule
        else None
    )
    return DebtFacility(
        facility_id=facility_id,
        label="Term Loan",
        type="term_loan",
        limit=limit,
        interest_rate=interest_rate,
        draw_schedule=draws,
        repayment_schedule=repays,
        is_cash_plug=is_cash_plug,
    )


def test_empty_facilities_returns_zero_filled_result() -> None:
    """Empty facilities list returns same shape as empty_debt_result."""
    result = calculate_debt_schedule([], horizon=12)
    expected = empty_debt_result(12)
    assert result.interest_per_period == expected.interest_per_period
    assert result.draws_per_period == expected.draws_per_period
    assert result.repayments_per_period == expected.repayments_per_period
    assert result.current_debt_per_period == expected.current_debt_per_period
    assert result.non_current_debt_per_period == expected.non_current_debt_per_period
    assert result.balance_per_period == {}


def test_empty_debt_result_shape() -> None:
    """empty_debt_result has correct horizon length."""
    r = empty_debt_result(24)
    assert len(r.interest_per_period) == 24
    assert len(r.draws_per_period) == 24
    assert len(r.repayments_per_period) == 24
    assert len(r.current_debt_per_period) == 24
    assert len(r.non_current_debt_per_period) == 24


def test_single_term_loan_balance_trajectory() -> None:
    """Single term loan: $500K draw at month 0, $50K repay from month 3; balance trajectory."""
    fac = _make_facility(
        limit=1_000_000.0,
        interest_rate=0.08,
        draw_schedule=[(0, 500_000.0)],
        repayment_schedule=[(m, 50_000.0) for m in range(3, 15)],
    )
    result = calculate_debt_schedule([fac], horizon=12)
    balances = result.balance_per_period[fac.facility_id]
    assert balances[0] == 500_000.0
    assert balances[1] == 500_000.0
    assert balances[2] == 500_000.0
    assert balances[3] == 450_000.0
    assert balances[4] == 400_000.0
    assert balances[5] == 350_000.0


def test_single_term_loan_interest() -> None:
    """Interest = balance * rate / 12; months 0-2 have balance 500K, 8% -> 3333.33/month."""
    fac = _make_facility(
        limit=1_000_000.0,
        interest_rate=0.08,
        draw_schedule=[(0, 500_000.0)],
        repayment_schedule=[(m, 50_000.0) for m in range(3, 15)],
    )
    result = calculate_debt_schedule([fac], horizon=12)
    # 500_000 * 0.08 / 12 = 3333.33...
    expected_interest_months_0_2 = 500_000.0 * 0.08 / 12
    assert result.interest_per_period[0] == pytest.approx(expected_interest_months_0_2, abs=0.01)
    assert result.interest_per_period[1] == pytest.approx(expected_interest_months_0_2, abs=0.01)
    assert result.interest_per_period[2] == pytest.approx(expected_interest_months_0_2, abs=0.01)
    assert result.interest_per_period[3] == pytest.approx(450_000.0 * 0.08 / 12, abs=0.01)


def test_multiple_facilities_totals_sum() -> None:
    """Two facilities: totals for interest, draws, repayments sum correctly."""
    f1 = _make_facility(
        facility_id="f1",
        limit=500_000.0,
        interest_rate=0.06,
        draw_schedule=[(0, 100_000.0)],
        repayment_schedule=[],
    )
    f2 = _make_facility(
        facility_id="f2",
        limit=300_000.0,
        interest_rate=0.10,
        draw_schedule=[(1, 50_000.0)],
        repayment_schedule=[],
    )
    result = calculate_debt_schedule([f1, f2], horizon=6)
    assert result.balance_per_period["f1"][0] == 100_000.0
    assert result.balance_per_period["f2"][0] == 0.0
    assert result.balance_per_period["f2"][1] == 50_000.0
    assert result.draws_per_period[0] == 100_000.0
    assert result.draws_per_period[1] == 50_000.0
    assert result.interest_per_period[0] == pytest.approx(100_000.0 * 0.06 / 12, abs=0.01)
    assert result.interest_per_period[1] == pytest.approx(
        100_000.0 * 0.06 / 12 + 50_000.0 * 0.10 / 12, abs=0.01
    )


def test_balance_clamped_at_zero() -> None:
    """Repayment exceeding balance -> balance 0, not negative."""
    fac = _make_facility(
        limit=100_000.0,
        draw_schedule=[(0, 30_000.0)],
        repayment_schedule=[(1, 50_000.0)],  # repay more than balance
    )
    result = calculate_debt_schedule([fac], horizon=6)
    balances = result.balance_per_period[fac.facility_id]
    assert balances[0] == 30_000.0
    assert balances[1] == 0.0
    assert balances[2] == 0.0


def test_balance_clamped_at_limit() -> None:
    """Draws exceeding limit are capped; balance never exceeds limit."""
    fac = _make_facility(
        limit=100_000.0,
        draw_schedule=[(0, 80_000.0), (1, 50_000.0)],  # 130K total, cap 100K
        repayment_schedule=[],
    )
    result = calculate_debt_schedule([fac], horizon=6)
    balances = result.balance_per_period[fac.facility_id]
    assert balances[0] == 80_000.0
    assert balances[1] == 100_000.0  # 80+50 capped at 100
    assert balances[2] == 100_000.0


def test_cash_plug_facility_skipped() -> None:
    """Facility with is_cash_plug=True is excluded from schedule."""
    fac = _make_facility(
        facility_id="plug",
        draw_schedule=[(0, 1_000_000.0)],
        is_cash_plug=True,
    )
    result = calculate_debt_schedule([fac], horizon=12)
    assert result.balance_per_period == {}
    assert result.interest_per_period == [0.0] * 12
    assert result.draws_per_period == [0.0] * 12


def test_current_vs_non_current_split() -> None:
    """Current = next 12 months repayments (capped at balance); non_current = remainder."""
    fac = _make_facility(
        limit=1_000_000.0,
        draw_schedule=[(0, 600_000.0)],
        repayment_schedule=[(1, 50_000.0), (2, 50_000.0), (3, 50_000.0)],  # 150K in next 12m
    )
    result = calculate_debt_schedule([fac], horizon=24)
    # At t=0: balance=600K, repayments due in 1..12 = 150K -> current=150K, non_current=450K
    assert result.current_debt_per_period[0] == pytest.approx(150_000.0, abs=0.01)
    assert result.non_current_debt_per_period[0] == pytest.approx(450_000.0, abs=0.01)
    # At t=1: balance=550K, repayments in 2..13 = 100K
    assert result.current_debt_per_period[1] == pytest.approx(100_000.0, abs=0.01)
    assert result.non_current_debt_per_period[1] == pytest.approx(450_000.0, abs=0.01)


def test_interest_calculation_accuracy() -> None:
    """Monthly interest = balance * rate / 12."""
    fac = _make_facility(
        limit=200_000.0,
        interest_rate=0.12,  # 12% annual
        draw_schedule=[(0, 200_000.0)],
        repayment_schedule=[],
    )
    result = calculate_debt_schedule([fac], horizon=3)
    # 200_000 * 0.12 / 12 = 2000
    for t in range(3):
        assert result.interest_per_period[t] == pytest.approx(2000.0, abs=0.01)
