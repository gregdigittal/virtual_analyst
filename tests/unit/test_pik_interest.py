"""Test PIK (Payment-in-Kind) interest: capitalizes instead of cash payment."""

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


def test_pik_interest_capitalizes() -> None:
    """PIK facility: interest added to balance, not to IS interest_expense."""
    config = _load_config()
    config.assumptions.funding.debt_facilities = [
        DebtFacility(
            facility_id="pik_1",
            label="Mezzanine PIK",
            type="term_loan",
            limit=2000000,
            interest_rate=0.10,
            pik_rate=1.0,
            draw_schedule=[DrawRepayPoint(month=0, amount=500000)],
            repayment_schedule=[],
        )
    ]
    config.metadata.horizon_months = 24

    result = calculate_debt_schedule(config.assumptions.funding.debt_facilities, 24)

    # Cash interest should be zero every period (all PIK)
    for t in range(24):
        assert result.interest_per_period[t] == pytest.approx(0.0, abs=0.01), (
            f"Period {t}: expected zero cash interest, got {result.interest_per_period[t]}"
        )

    # Balance should compound: 500000 * (1 + 0.10/12)^24
    expected_balance = 500000.0
    for _ in range(24):
        expected_balance += expected_balance * 0.10 / 12
    final_balance = result.balance_per_period["pik_1"][-1]
    assert final_balance == pytest.approx(expected_balance, rel=0.001)


def test_pik_partial() -> None:
    """PIK rate of 0.5 means 50% capitalizes, 50% is cash interest."""
    config = _load_config()
    config.assumptions.funding.debt_facilities = [
        DebtFacility(
            facility_id="pik_partial",
            label="Partial PIK",
            type="term_loan",
            limit=500000,
            interest_rate=0.12,
            pik_rate=0.5,
            draw_schedule=[DrawRepayPoint(month=0, amount=100000)],
            repayment_schedule=[],
        )
    ]

    result = calculate_debt_schedule(config.assumptions.funding.debt_facilities, 12)

    # Period 0: balance = 100000, total interest = 100000 * 0.12 / 12 = 1000
    # Cash interest = 1000 * (1 - 0.5) = 500
    # PIK capitalized = 1000 * 0.5 = 500 -> new balance = 100500
    assert result.interest_per_period[0] == pytest.approx(500.0, abs=1.0)
    assert result.balance_per_period["pik_partial"][0] == pytest.approx(100500.0, abs=1.0)
