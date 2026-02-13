"""Unit tests for Monte Carlo runner: determinism with seed, result shape."""

from __future__ import annotations

import numpy as np

from shared.fm_shared.analysis.monte_carlo import MCResult, run_monte_carlo
from shared.fm_shared.model import ModelConfig
from tests.conftest import minimal_model_config


def _config_with_distributions() -> ModelConfig:
    """Minimal config with one stochastic driver (units) for MC."""
    d = minimal_model_config(horizon_months=3).model_dump()
    d["distributions"] = [
        {
            "ref": "drv:units",
            "family": "uniform",
            "params": {"min": 98.0, "max": 102.0},
        }
    ]
    return ModelConfig.model_validate(d)


def test_run_monte_carlo_deterministic() -> None:
    """Same seed produces identical percentile results."""
    config = _config_with_distributions()
    r1 = run_monte_carlo(config, num_simulations=20, seed=99)
    r2 = run_monte_carlo(config, num_simulations=20, seed=99)
    assert r1.num_simulations == r2.num_simulations == 20
    assert r1.seed == r2.seed == 99
    for metric in ("revenue", "ebitda", "net_income", "fcf"):
        for q in ("p5", "p50", "p95"):
            np.testing.assert_array_almost_equal(
                r1.percentiles[metric][q],
                r2.percentiles[metric][q],
                err_msg=f"{metric} {q}",
            )


def test_run_monte_carlo_returns_percentiles() -> None:
    """Result has percentiles for revenue, ebitda, net_income, fcf; lengths match horizon."""
    config = _config_with_distributions()
    horizon = config.metadata.horizon_months
    result = run_monte_carlo(config, num_simulations=10, seed=1)
    assert isinstance(result, MCResult)
    for metric in ("revenue", "ebitda", "net_income", "fcf"):
        assert metric in result.percentiles
        for q in ("p5", "p10", "p25", "p50", "p75", "p90", "p95"):
            assert q in result.percentiles[metric]
            assert len(result.percentiles[metric][q]) == horizon
    assert "terminal_revenue" in result.summary
    assert "terminal_fcf" in result.summary


def test_run_monte_carlo_no_distributions_all_sims_identical() -> None:
    """With no distributions, all sims are the same so p5 == p50 == p95."""
    config = minimal_model_config(horizon_months=2)
    result = run_monte_carlo(config, num_simulations=5, seed=42)
    for metric in ("revenue", "ebitda", "net_income", "fcf"):
        p5 = result.percentiles[metric]["p5"]
        p50 = result.percentiles[metric]["p50"]
        p95 = result.percentiles[metric]["p95"]
        np.testing.assert_array_almost_equal(p5, p50, err_msg=f"{metric} p5 vs p50")
        np.testing.assert_array_almost_equal(p50, p95, err_msg=f"{metric} p50 vs p95")
