"""Golden file tests: manufacturing template outputs match hand-verified golden files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.model.kpis import calculate_kpis

GOLDEN_DIR = Path(__file__).resolve().parent
CONFIG_PATH = GOLDEN_DIR / "manufacturing_config.json"
STATEMENTS_GOLDEN = GOLDEN_DIR / "manufacturing_base_statements.json"
KPIS_GOLDEN = GOLDEN_DIR / "manufacturing_base_kpis.json"

# Allow small float differences (rounding, order of ops)
FLOAT_TOLERANCE = 0.01


def _load_config() -> ModelConfig:
    data = json.loads(CONFIG_PATH.read_text())
    return ModelConfig.model_validate(data)


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
    assert len(got) == len(
        expected
    ), f"Length mismatch at {path}: got {len(got)}, expected {len(expected)}"
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


def test_manufacturing_statements_match_golden() -> None:
    """Engine + statements output matches manufacturing_base_statements.json within tolerance."""
    config = _load_config()
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    golden = json.loads(STATEMENTS_GOLDEN.read_text())

    _compare_list(statements.income_statement, golden["income_statement"], "income_statement")
    _compare_list(statements.balance_sheet, golden["balance_sheet"], "balance_sheet")
    _compare_list(statements.cash_flow, golden["cash_flow"], "cash_flow")
    assert statements.periods == golden["periods"]


def test_manufacturing_kpis_match_golden() -> None:
    """KPI output matches manufacturing_base_kpis.json within tolerance."""
    config = _load_config()
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    kpis = calculate_kpis(statements)
    golden = json.loads(KPIS_GOLDEN.read_text())

    _compare_list(kpis, golden, "kpis")


def test_manufacturing_revenue_and_cogs_sanity() -> None:
    """Sanity check: P0 revenue and COGS match expected formula (units * price, units * material)."""
    config = _load_config()
    time_series = run_engine(config)
    # units_produced = 1000 * 0.7 * 0.92 = 644
    # revenue = 644 * 4500 = 2,898,000; material_cogs = 644 * 1800 = 1,159,200
    assert "n_units_produced" in time_series
    assert "n_revenue" in time_series
    assert "n_material_cogs" in time_series
    assert time_series["n_units_produced"][0] == pytest.approx(644.0, abs=0.01)
    assert time_series["n_revenue"][0] == pytest.approx(2_898_000.0, abs=0.01)
    assert time_series["n_material_cogs"][0] == pytest.approx(1_159_200.0, abs=0.01)
