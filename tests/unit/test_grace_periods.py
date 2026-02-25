"""Test debt grace periods: principal deferred, interest still accrues."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.fm_shared.model import ModelConfig
from shared.fm_shared.model.debt import calculate_debt_schedule
from shared.fm_shared.model.schemas import DebtFacility, DrawRepayPoint

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "golden"
CONFIG_PATH = GOLDEN_DIR / "debt_config.json"


def _load_config() -> ModelConfig:
    data = json.loads(CONFIG_PATH.read_text())
    return ModelConfig.model_validate(data)


def test_grace_period_defers_repayments() -> None:
    """6-month grace: zero principal repayment during grace, interest still accrues."""
    config = _load_config()
    config.assumptions.funding.debt_facilities = [
        DebtFacility(
            facility_id="grace_1",
            label="Term w/ Grace",
            type="term_loan",
            limit=1000000,
            interest_rate=0.08,
            grace_period_months=6,
            draw_schedule=[DrawRepayPoint(month=0, amount=600000)],
            repayment_schedule=[
                DrawRepayPoint(month=i, amount=100000) for i in range(12)
            ],
        )
    ]

    result = calculate_debt_schedule(config.assumptions.funding.debt_facilities, 12)

    # During grace (months 0-5): no principal repayments
    for t in range(6):
        assert result.repayments_per_period[t] == pytest.approx(0.0, abs=0.01), (
            f"Month {t}: expected zero repayment during grace, got {result.repayments_per_period[t]}"
        )

    # Interest should still accrue during grace
    for t in range(6):
        expected_interest = 600000 * 0.08 / 12  # balance constant during grace
        assert result.interest_per_period[t] == pytest.approx(expected_interest, abs=1.0), (
            f"Month {t}: expected interest {expected_interest}, got {result.interest_per_period[t]}"
        )

    # After grace (months 6-11): repayments resume (shifted: month 6 looks up schedule month 0)
    for t in range(6, 12):
        assert result.repayments_per_period[t] == pytest.approx(100000.0, abs=0.01), (
            f"Month {t}: expected repayment 100000, got {result.repayments_per_period[t]}"
        )


def test_grace_period_shifts_schedule() -> None:
    """Repayment at month 3 with 6-month grace should appear at month 9."""
    config = _load_config()
    config.assumptions.funding.debt_facilities = [
        DebtFacility(
            facility_id="grace_shift",
            label="Term w/ Grace + Shift",
            type="term_loan",
            limit=1000000,
            interest_rate=0.06,
            grace_period_months=6,
            draw_schedule=[DrawRepayPoint(month=0, amount=300000)],
            repayment_schedule=[
                DrawRepayPoint(month=3, amount=100000),
                DrawRepayPoint(month=6, amount=200000),
            ],
        )
    ]

    result = calculate_debt_schedule(config.assumptions.funding.debt_facilities, 12)

    # Months 0-5: grace, zero repayment
    for t in range(6):
        assert result.repayments_per_period[t] == pytest.approx(0.0, abs=0.01)

    # Month 9 = schedule month 3 (shifted by 6): repayment of 100K
    assert result.repayments_per_period[9] == pytest.approx(100000.0, abs=0.01)
