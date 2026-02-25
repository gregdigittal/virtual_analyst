"""Test trade finance: asset-linked facility capped at advance_rate * asset value."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.model.funding_waterfall import apply_funding_waterfall
from shared.fm_shared.model.schemas import DebtFacility, DrawRepayPoint

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "golden"
CONFIG_PATH = GOLDEN_DIR / "debt_config.json"


def _load_config() -> ModelConfig:
    data = json.loads(CONFIG_PATH.read_text())
    return ModelConfig.model_validate(data)


def test_trade_finance_facility_type_accepted() -> None:
    """A trade_finance facility type should be accepted by the schema."""
    tf = DebtFacility(
        facility_id="tf_test",
        label="Debtor Finance",
        type="trade_finance",
        limit=5000000,
        interest_rate=0.09,
        is_cash_plug=True,
        asset_linked="ar",
        advance_rate=0.80,
    )
    assert tf.type == "trade_finance"
    assert tf.asset_linked == "ar"
    assert tf.advance_rate == 0.80


def test_debtor_finance_capped_at_ar_advance() -> None:
    """Trade finance with is_cash_plug: waterfall draw capped at 80% of AR."""
    config = _load_config()
    # Keep existing non-plug term loan, add trade finance as cash plug
    tf = DebtFacility(
        facility_id="tf_1",
        label="Debtor Finance",
        type="trade_finance",
        limit=5000000,
        interest_rate=0.09,
        is_cash_plug=True,
        asset_linked="ar",
        advance_rate=0.80,
    )
    config.assumptions.funding.debt_facilities.append(tf)
    config.assumptions.working_capital.minimum_cash = 50000.0

    ts = run_engine(config)
    stmts = generate_statements(config, ts)

    horizon = config.metadata.horizon_months

    # Basic statement length checks
    assert len(stmts.income_statement) == horizon
    assert len(stmts.balance_sheet) == horizon
    assert len(stmts.cash_flow) == horizon

    # BS should balance every period
    for t in range(horizon):
        bs = stmts.balance_sheet[t]
        assert bs["total_assets"] == pytest.approx(
            bs["total_liabilities_equity"], abs=1.0
        ), f"BS imbalance at period {t}"

    # Direct AR cap assertion: run waterfall with ONLY the trade finance
    # facility to isolate its balance from other plug facilities.
    closing_cash = [stmts.balance_sheet[t]["cash"] for t in range(horizon)]
    asset_values = {
        "ar": [stmts.balance_sheet[t]["accounts_receivable"] for t in range(horizon)],
        "inventory": [stmts.balance_sheet[t]["inventory"] for t in range(horizon)],
    }
    minimum_cash = config.assumptions.working_capital.minimum_cash or 0.0

    waterfall = apply_funding_waterfall(
        closing_cash, [tf], minimum_cash, horizon, asset_values
    )

    advance_rate = tf.advance_rate
    for t in range(horizon):
        ar_balance = stmts.balance_sheet[t]["accounts_receivable"]
        cap = advance_rate * ar_balance
        tf_debt = waterfall.waterfall_debt_per_period[t]
        assert tf_debt <= cap + 0.01, (
            f"Period {t}: trade finance debt {tf_debt:.2f} exceeds "
            f"AR cap ({advance_rate} * {ar_balance:.2f} = {cap:.2f})"
        )
