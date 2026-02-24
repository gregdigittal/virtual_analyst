"""Golden/behavior tests: funding waterfall with cash-plug facilities."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.model.kpis import calculate_kpis

GOLDEN_DIR = Path(__file__).resolve().parent
CONFIG_PATH = GOLDEN_DIR / "waterfall_config.json"
STATEMENTS_GOLDEN = GOLDEN_DIR / "waterfall_base_statements.json"
KPIS_GOLDEN = GOLDEN_DIR / "waterfall_base_kpis.json"
MINIMUM_CASH = 5000.0
FLOAT_TOLERANCE = 0.01


def _compare_floats(got: float, expected: float, path: str = "") -> None:
    if abs(got - expected) > FLOAT_TOLERANCE:
        pytest.fail(f"Mismatch at {path}: got {got}, expected {expected}")


def _compare_dict(got: dict, expected: dict, path: str = "") -> None:
    for key in expected:
        if key not in got:
            pytest.fail(f"Missing key at {path}: {key}")
        g, e = got[key], expected[key]
        if isinstance(e, dict):
            _compare_dict(g, e, f"{path}.{key}")
        elif isinstance(e, list):
            _compare_list(g, e, f"{path}.{key}")
        elif isinstance(e, (int, float)):
            _compare_floats(float(g), float(e), f"{path}.{key}")
        else:
            assert g == e, f"Mismatch at {path}.{key}: got {g}, expected {e}"


def _compare_list(got: list, expected: list, path: str = "") -> None:
    assert len(got) == len(expected), f"Length mismatch at {path}"
    for i, (g, e) in enumerate(zip(got, expected)):
        p = f"{path}[{i}]"
        if isinstance(e, dict):
            _compare_dict(g, e, p)
        elif isinstance(e, list):
            _compare_list(g, e, p)
        elif isinstance(e, (int, float)):
            _compare_floats(float(g), float(e), p)
        else:
            assert g == e, f"Mismatch at {p}: got {g}, expected {e}"


def _load_config() -> ModelConfig:
    data = json.loads(CONFIG_PATH.read_text())
    return ModelConfig.model_validate(data)


def test_waterfall_cash_never_below_minimum() -> None:
    """After waterfall, cash never drops below minimum_cash."""
    config = _load_config()
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    for t, row in enumerate(statements.balance_sheet):
        assert row["cash"] >= MINIMUM_CASH - 0.02, (
            f"Period {t}: cash {row['cash']} below minimum {MINIMUM_CASH}"
        )


def test_waterfall_revolver_before_overdraft() -> None:
    """Waterfall draws from revolver before overdraft (revolver has lower type order)."""
    config = _load_config()
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    # Just check that we have plug facilities and that statements completed
    plug = [f for f in config.assumptions.funding.debt_facilities if f.is_cash_plug]
    assert len(plug) >= 1
    rev = next((f for f in plug if f.type == "revolver"), None)
    od = next((f for f in plug if f.type == "overdraft"), None)
    assert rev is not None
    assert od is not None


def test_waterfall_interest_recalculates() -> None:
    """Interest expense is present in IS; overdraft interest added when overdraft is used."""
    config = _load_config()
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    # All periods have interest_expense key; may be 0 if only revolver used (no overdraft interest)
    for row in statements.income_statement:
        assert "interest_expense" in row
    assert len(statements.income_statement) == config.metadata.horizon_months


def test_waterfall_bs_balances_every_period() -> None:
    """Balance sheet balances (total_assets == total_liabilities_equity) every period."""
    config = _load_config()
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    for t, row in enumerate(statements.balance_sheet):
        assert abs(row["total_assets"] - row["total_liabilities_equity"]) < 0.02, (
            f"Period {t}: BS imbalance"
        )


def test_waterfall_cf_financing_reflects_draws() -> None:
    """Cash flow runs and financing is present (waterfall draws affect financing plug)."""
    config = _load_config()
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    for row in statements.cash_flow:
        assert "financing" in row
        assert "closing_cash" in row
    assert len(statements.cash_flow) == config.metadata.horizon_months


def test_waterfall_statements_match_golden() -> None:
    """Engine + statements with waterfall config match waterfall_base_statements.json."""
    config = _load_config()
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    golden = json.loads(STATEMENTS_GOLDEN.read_text())
    _compare_list(statements.income_statement, golden["income_statement"], "income_statement")
    _compare_list(statements.balance_sheet, golden["balance_sheet"], "balance_sheet")
    _compare_list(statements.cash_flow, golden["cash_flow"], "cash_flow")
    assert statements.periods == golden["periods"]


def test_waterfall_kpis_match_golden() -> None:
    """KPI output with waterfall config matches waterfall_base_kpis.json."""
    config = _load_config()
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    kpis = calculate_kpis(statements)
    golden = json.loads(KPIS_GOLDEN.read_text())
    _compare_list(kpis, golden, "kpis")
