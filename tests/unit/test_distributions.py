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


def test_sample_correlated_high_positive() -> None:
    """rho=0.9 between two drivers produces Pearson > 0.7 over 500 samples."""
    from shared.fm_shared.analysis.distributions import sample_correlated
    from shared.fm_shared.model.schemas import CorrelationEntry

    configs = [
        DistributionConfig(ref="drv:a", family="normal", params={"mean": 100, "std": 10}),
        DistributionConfig(ref="drv:b", family="normal", params={"mean": 50, "std": 5}),
    ]
    corr = [CorrelationEntry(ref_a="drv:a", ref_b="drv:b", rho=0.9)]
    rng = np.random.default_rng(42)
    samples_a, samples_b = [], []
    for _ in range(500):
        s = sample_correlated(configs, corr, rng)
        samples_a.append(s["drv:a"])
        samples_b.append(s["drv:b"])
    r = np.corrcoef(samples_a, samples_b)[0, 1]
    assert r > 0.7, f"Expected Pearson > 0.7, got {r}"


def test_sample_correlated_zero_correlation() -> None:
    """rho=0 produces near-zero correlation (|r| < 0.15)."""
    from shared.fm_shared.analysis.distributions import sample_correlated
    from shared.fm_shared.model.schemas import CorrelationEntry

    configs = [
        DistributionConfig(ref="drv:x", family="uniform", params={"min": 0, "max": 100}),
        DistributionConfig(ref="drv:y", family="uniform", params={"min": 0, "max": 100}),
    ]
    corr = [CorrelationEntry(ref_a="drv:x", ref_b="drv:y", rho=0.0)]
    rng = np.random.default_rng(99)
    sx, sy = [], []
    for _ in range(500):
        s = sample_correlated(configs, corr, rng)
        sx.append(s["drv:x"])
        sy.append(s["drv:y"])
    r = np.corrcoef(sx, sy)[0, 1]
    assert abs(r) < 0.15, f"Expected |r| < 0.15, got {r}"


def test_sample_correlated_deterministic() -> None:
    """Same seed produces identical correlated samples."""
    from shared.fm_shared.analysis.distributions import sample_correlated
    from shared.fm_shared.model.schemas import CorrelationEntry

    configs = [
        DistributionConfig(ref="drv:a", family="normal", params={"mean": 10, "std": 2}),
        DistributionConfig(
            ref="drv:b",
            family="triangular",
            params={"min": 5, "mode": 10, "max": 15},
        ),
    ]
    corr = [CorrelationEntry(ref_a="drv:a", ref_b="drv:b", rho=0.6)]
    s1 = sample_correlated(configs, corr, np.random.default_rng(7))
    s2 = sample_correlated(configs, corr, np.random.default_rng(7))
    assert s1 == s2


def test_sample_correlated_fallback_independent() -> None:
    """Single distribution with no correlations returns valid sample."""
    from shared.fm_shared.analysis.distributions import sample_correlated

    configs = [
        DistributionConfig(
            ref="drv:solo",
            family="normal",
            params={"mean": 50, "std": 5},
        ),
    ]
    rng = np.random.default_rng(1)
    s = sample_correlated(configs, [], rng)
    assert "drv:solo" in s
    assert isinstance(s["drv:solo"], float)


def test_sample_correlated_fallback_non_positive_definite() -> None:
    """Non-positive-definite correlation matrix falls back to independent sampling."""
    from shared.fm_shared.analysis.distributions import sample_correlated
    from shared.fm_shared.model.schemas import CorrelationEntry

    configs = [
        DistributionConfig(ref="a", family="normal", params={"mean": 10, "std": 1}),
        DistributionConfig(ref="b", family="normal", params={"mean": 20, "std": 2}),
        DistributionConfig(ref="c", family="normal", params={"mean": 30, "std": 3}),
    ]
    # Contradictory correlations -> not positive definite
    corr = [
        CorrelationEntry(ref_a="a", ref_b="b", rho=0.9),
        CorrelationEntry(ref_a="a", ref_b="c", rho=0.9),
        CorrelationEntry(ref_a="b", ref_b="c", rho=-0.9),
    ]
    rng = np.random.default_rng(42)
    result = sample_correlated(configs, corr, rng)
    assert set(result.keys()) == {"a", "b", "c"}
    assert all(isinstance(v, float) for v in result.values())
