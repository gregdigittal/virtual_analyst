"""
Distribution sampling for Monte Carlo. Seeded RNG for reproducibility.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from shared.fm_shared.model.schemas import DistributionConfig


def sample(
    config: "DistributionConfig",
    n: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Sample n values from the given distribution using the provided RNG.
    Returns shape (n,) float array.
    """
    p = config.params
    family = config.family

    if family == "triangular":
        lo, mode, hi = p["min"], p["mode"], p["max"]
        return rng.triangular(lo, mode, hi, size=n)

    if family == "normal":
        return rng.normal(loc=p["mean"], scale=p["std"], size=n)

    if family == "lognormal":
        # mean, sigma are params of the underlying normal (log-scale)
        mean = p.get("mean", 0.0)
        sigma = p.get("sigma", p.get("std", 1.0))
        return rng.lognormal(mean=mean, sigma=sigma, size=n)

    if family == "uniform":
        return rng.uniform(low=p["min"], high=p["max"], size=n)

    if family == "pert":
        # PERT: beta with alpha/beta from min, mode, max
        lo, mode, hi = p["min"], p["mode"], p["max"]
        r = hi - lo
        if r <= 0:
            return np.full(n, mode)
        alpha = 1.0 + 4.0 * (mode - lo) / r
        beta = 1.0 + 4.0 * (hi - mode) / r
        return lo + r * rng.beta(alpha, beta, size=n)

    raise ValueError(f"Unsupported distribution family: {family}")
