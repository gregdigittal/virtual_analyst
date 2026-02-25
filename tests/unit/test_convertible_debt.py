"""Test convertible debt: converts to equity at trigger month."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.model.debt import calculate_debt_schedule
from shared.fm_shared.model.schemas import DebtFacility, DrawRepayPoint

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "golden"
CONFIG_PATH = GOLDEN_DIR / "debt_config.json"


def _load_config() -> ModelConfig:
    data = json.loads(CONFIG_PATH.read_text())
    return ModelConfig.model_validate(data)


def test_convertible_debt_zeroes_at_conversion() -> None:
    """Debt balance drops to zero at conversion month, interest stops."""
    config = _load_config()
    config.assumptions.funding.debt_facilities = [
        DebtFacility(
            facility_id="conv_1",
            label="Convertible Note",
            type="term_loan",
            limit=1000000,
            interest_rate=0.06,
            converts_to_equity_month=6,
            draw_schedule=[DrawRepayPoint(month=0, amount=1000000)],
            repayment_schedule=[],
        )
    ]
    config.metadata.horizon_months = 12

    result = calculate_debt_schedule(config.assumptions.funding.debt_facilities, 12)

    # Pre-conversion (months 0-5): balance = 1M, interest accrues
    for t in range(6):
        assert result.balance_per_period["conv_1"][t] == pytest.approx(1000000.0, abs=1.0)
        expected_interest = 1000000.0 * 0.06 / 12
        assert result.interest_per_period[t] == pytest.approx(expected_interest, abs=1.0)

    # Post-conversion (months 6-11): balance = 0, interest = 0
    for t in range(6, 12):
        assert result.balance_per_period["conv_1"][t] == pytest.approx(0.0, abs=0.01)
        assert result.interest_per_period[t] == pytest.approx(0.0, abs=0.01)


def test_convertible_debt_equity_increase() -> None:
    """At conversion month, equity increases by the converted amount."""
    config = _load_config()
    config.assumptions.funding.debt_facilities = [
        DebtFacility(
            facility_id="conv_2",
            label="Convertible",
            type="term_loan",
            limit=500000,
            interest_rate=0.06,
            converts_to_equity_month=3,
            draw_schedule=[DrawRepayPoint(month=0, amount=500000)],
            repayment_schedule=[],
        )
    ]
    config.metadata.horizon_months = 12

    ts = run_engine(config)
    stmts = generate_statements(config, ts)

    # After conversion at month 3, debt should be gone from BS
    for t in range(3, 12):
        assert stmts.balance_sheet[t]["debt_current"] == pytest.approx(0.0, abs=1.0)
        assert stmts.balance_sheet[t]["debt_non_current"] == pytest.approx(0.0, abs=1.0)

    # Equity should jump at conversion month by roughly the conversion amount
    equity_pre = stmts.balance_sheet[2]["total_equity"]
    equity_post = stmts.balance_sheet[3]["total_equity"]
    ni_m3 = stmts.income_statement[3]["net_income"]
    equity_increase = equity_post - equity_pre - ni_m3
    assert equity_increase == pytest.approx(500000.0, rel=0.05)
