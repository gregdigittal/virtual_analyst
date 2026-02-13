"""Unit tests for distribution sampling (seeded RNG, families)."""

from __future__ import annotations

import numpy as np

from shared.fm_shared.analysis.distributions import sample
from shared.fm_shared.model.schemas import DistributionConfig


def test_sample_triangular_same_seed_same_output() -> None:
    """Same seed produces identical samples."""
    config = DistributionConfig(
        ref="drv:units",
        family="triangular",
        params={"min": 80.0, "mode": 100.0, "max": 120.0},
    )
    rng1 = np.random.default_rng(42)
    rng2 = np.random.default_rng(42)
    a = sample(config, 50, rng1)
    b = sample(config, 50, rng2)
    np.testing.assert_array_almost_equal(a, b)


def test_sample_normal_deterministic() -> None:
    """Normal samples with same seed are deterministic."""
    config = DistributionConfig(
        ref="x",
        family="normal",
        params={"mean": 10.0, "std": 2.0},
    )
    rng = np.random.default_rng(123)
    out = sample(config, 100, rng)
    assert out.shape == (100,)
    assert np.all(np.isfinite(out))
    # Same seed again
    rng2 = np.random.default_rng(123)
    out2 = sample(config, 100, rng2)
    np.testing.assert_array_almost_equal(out, out2)


def test_sample_uniform_bounds() -> None:
    """Uniform samples lie within [min, max]."""
    config = DistributionConfig(
        ref="u",
        family="uniform",
        params={"min": 1.0, "max": 5.0},
    )
    rng = np.random.default_rng(0)
    out = sample(config, 200, rng)
    assert np.all(out >= 1.0) and np.all(out <= 5.0)


def test_sample_pert_bounds() -> None:
    """PERT samples lie within [min, max]."""
    config = DistributionConfig(
        ref="p",
        family="pert",
        params={"min": 0.0, "mode": 0.5, "max": 1.0},
    )
    rng = np.random.default_rng(7)
    out = sample(config, 100, rng)
    assert np.all(out >= 0.0) and np.all(out <= 1.0)


def test_sample_lognormal_positive() -> None:
    """Lognormal samples are positive."""
    config = DistributionConfig(
        ref="ln",
        family="lognormal",
        params={"mean": 0.0, "sigma": 1.0},
    )
    rng = np.random.default_rng(11)
    out = sample(config, 50, rng)
    assert np.all(out > 0.0)


