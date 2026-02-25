"""Unit tests for sensitivity sweep and heat map."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.fm_shared.analysis import sensitivity as sens_mod
from shared.fm_shared.analysis.sensitivity import (
    HeatMapResult,
    SensitivityResult,
    run_heatmap,
    run_sensitivity,
)
from shared.fm_shared.model import ModelConfig

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "golden"
CONFIG_PATH = GOLDEN_DIR / "debt_config.json"


def _load_config() -> ModelConfig:
    data = json.loads(CONFIG_PATH.read_text())
    return ModelConfig.model_validate(data)


def test_sensitivity_tax_rate_sweep_monotonic() -> None:
    """Sweeping tax_rate 0.15->0.35 should monotonically decrease net_income."""
    config = _load_config()
    result = run_sensitivity(
        config=config,
        parameter_path="metadata.tax_rate",
        low=0.15,
        high=0.35,
        steps=5,
        metric="net_income",
    )
    assert isinstance(result, SensitivityResult)
    assert result.parameter == "metadata.tax_rate"
    assert len(result.values) == 5
    assert len(result.metric_values) == 5
    # Higher tax -> lower net income: monotonic decrease
    for i in range(1, len(result.metric_values)):
        assert result.metric_values[i] <= result.metric_values[i - 1], (
            f"Expected monotonic decrease at step {i}: "
            f"{result.metric_values[i]} > {result.metric_values[i - 1]}"
        )


def test_sensitivity_returns_base_value() -> None:
    """base_value should reflect the config's current value of the parameter."""
    config = _load_config()
    result = run_sensitivity(
        config=config,
        parameter_path="metadata.tax_rate",
        low=0.0,
        high=0.3,
        steps=3,
        metric="ebitda",
    )
    assert result.base_value == config.metadata.tax_rate


def test_heatmap_tax_rate_vs_initial_cash() -> None:
    """2D sweep: tax_rate x initial_cash -> net_income matrix."""
    config = _load_config()
    result = run_heatmap(
        config=config,
        param_a_path="metadata.tax_rate",
        param_a_range=(0.10, 0.30, 3),
        param_b_path="metadata.initial_cash",
        param_b_range=(50000, 150000, 3),
        metric="net_income",
    )
    assert isinstance(result, HeatMapResult)
    assert len(result.values_a) == 3
    assert len(result.values_b) == 3
    assert len(result.matrix) == 3
    assert all(len(row) == 3 for row in result.matrix)
    # Higher tax -> lower net income (rows correspond to increasing tax_rate)
    for i in range(1, len(result.matrix)):
        assert result.matrix[i][0] <= result.matrix[i - 1][0], (
            f"Expected row {i} (tax={result.values_a[i]}) <= row {i-1} (tax={result.values_a[i-1]})"
        )


def test_parallel_and_sequential_produce_same_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the parallel code path matches the sequential fallback."""
    config = _load_config()

    # Run with parallel enabled (threshold=4, steps=5 triggers it)
    result_parallel = run_sensitivity(
        config=config,
        parameter_path="metadata.tax_rate",
        low=0.15,
        high=0.35,
        steps=5,
        metric="net_income",
    )

    # Force sequential by raising the threshold above our step count
    monkeypatch.setattr(sens_mod, "_PARALLEL_THRESHOLD", 999)
    result_sequential = run_sensitivity(
        config=config,
        parameter_path="metadata.tax_rate",
        low=0.15,
        high=0.35,
        steps=5,
        metric="net_income",
    )

    assert result_parallel.values == result_sequential.values
    assert result_parallel.metric_values == result_sequential.metric_values
    assert result_parallel.base_value == result_sequential.base_value
