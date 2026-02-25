"""
Distribution sampling for Monte Carlo. Seeded RNG for reproducibility.
Correlated sampling via Cholesky decomposition (Gaussian copula).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import structlog
from scipy.stats import beta as beta_dist, norm, triang as triang_dist

logger = structlog.get_logger()

if TYPE_CHECKING:
    from shared.fm_shared.model.schemas import CorrelationEntry, DistributionConfig


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


def _inverse_cdf_one(config: "DistributionConfig", u: float) -> float:
    """Map uniform u in (0,1) to one sample from the distribution (inverse CDF)."""
    p = config.params
    family = config.family
    u = max(1e-10, min(1 - 1e-10, u))  # avoid 0/1 for numerical stability

    if family == "normal":
        return float(norm.ppf(u, loc=p["mean"], scale=p["std"]))
    if family == "lognormal":
        mean = p.get("mean", 0.0)
        sigma = p.get("sigma", p.get("std", 1.0))
        return float(np.exp(norm.ppf(u, loc=mean, scale=sigma)))
    if family == "uniform":
        return p["min"] + (p["max"] - p["min"]) * u
    if family == "triangular":
        lo, mode, hi = p["min"], p["mode"], p["max"]
        c = (mode - lo) / (hi - lo) if hi > lo else 0.5
        return float(triang_dist.ppf(u, c=c, loc=lo, scale=hi - lo))
    if family == "pert":
        lo, mode, hi = p["min"], p["mode"], p["max"]
        r = hi - lo
        if r <= 0:
            return mode
        alpha = 1.0 + 4.0 * (mode - lo) / r
        beta = 1.0 + 4.0 * (hi - mode) / r
        return float(lo + r * beta_dist.ppf(u, alpha, beta))
    raise ValueError(f"Unsupported distribution family: {family}")


def sample_correlated(
    configs: list["DistributionConfig"],
    correlations: list,  # list[CorrelationEntry]
    rng: np.random.Generator,
) -> dict[str, float]:
    """
    Sample all distributions with Cholesky-based Gaussian copula correlation.

    Algorithm:
    1. Build NxN correlation matrix from CorrelationEntry list
       (default rho=0 for unspecified pairs, rho=1 on diagonal)
    2. Cholesky decomposition: L = cholesky(Sigma)
    3. Sample independent standard normals: z = rng.standard_normal(N)
    4. Transform: correlated = L @ z
    5. Map correlated normals to uniform via Phi(correlated_i), then inverse CDF
       of each target distribution. For normal/lognormal use direct transform.
    """
    n = len(configs)
    if n == 0:
        return {}
    ref_to_idx: dict[str, int] = {c.ref: i for i, c in enumerate(configs)}

    # Single distribution or no correlations: fall back to independent
    if n == 1 or not correlations:
        out: dict[str, float] = {}
        for c in configs:
            out[c.ref] = float(sample(c, 1, rng)[0])
        return out

    # Build correlation matrix Sigma (symmetric, diagonal 1)
    Sigma = np.eye(n)
    for entry in correlations:
        i = ref_to_idx.get(entry.ref_a)
        j = ref_to_idx.get(entry.ref_b)
        if i is not None and j is not None:
            Sigma[i, j] = entry.rho
            Sigma[j, i] = entry.rho

    try:
        L = np.linalg.cholesky(Sigma)
    except np.linalg.LinAlgError:
        logger.warning(
            "correlation_matrix_not_positive_definite",
            msg="Cholesky decomposition failed; falling back to independent sampling",
            n_distributions=n,
            n_correlations=len(correlations),
        )
        out = {}
        for c in configs:
            out[c.ref] = float(sample(c, 1, rng)[0])
        return out

    z = rng.standard_normal(n)
    y = L @ z  # correlated standard normals

    out = {}
    for i, c in enumerate(configs):
        if c.family == "normal":
            out[c.ref] = float(c.params["mean"] + c.params["std"] * y[i])
        elif c.family == "lognormal":
            mean = c.params.get("mean", 0.0)
            sigma = c.params.get("sigma", c.params.get("std", 1.0))
            out[c.ref] = float(np.exp(mean + sigma * y[i]))
        else:
            u = float(norm.cdf(y[i]))
            out[c.ref] = _inverse_cdf_one(c, u)
    return out
