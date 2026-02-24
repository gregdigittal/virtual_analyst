# DG Parity — Phase 3: Monte Carlo Correlation (Cholesky Decomposition)

> **CRITICAL**: Work in the MAIN repository directory. Do NOT create a git
> worktree. Do NOT modify files outside the scope listed below.

## Context Update

Phase 2 is complete. The three-statement model now supports:
- Scheduled debt with interest, draws, repayments (Phase 1)
- Fixed/payout-ratio dividends, equity raises, funding waterfall with
  iterative interest feedback (Phase 2)

**Current Monte Carlo limitation:** `monte_carlo.py:72-76` samples each
distribution independently. Digital Genius uses Cholesky decomposition for
correlated sampling (e.g., volume and price move together).

**Dependency note:** `scipy>=1.12.0` has already been added to `pyproject.toml`
and is installed. You can `from scipy.stats import norm` directly.

## In-Scope Files (ONLY modify these)

| # | File | Action |
|---|------|--------|
| 1 | `shared/fm_shared/model/schemas.py` | Add `CorrelationEntry` model, add `correlation_matrix` field to `ModelConfig` |
| 2 | `shared/fm_shared/analysis/distributions.py` | Add `sample_correlated()` function |
| 3 | `shared/fm_shared/analysis/monte_carlo.py` | Use `sample_correlated()` when correlations exist |
| 4 | `tests/unit/test_distributions.py` | Add correlation tests |
| 5 | `tests/unit/test_monte_carlo.py` | Add correlated MC test |

## Implementation Steps

### Step 1 — Schema: `CorrelationEntry` + `ModelConfig.correlation_matrix`

In `shared/fm_shared/model/schemas.py`:

Add a new model **before** the `ModelConfig` class (around line 237):

```python
class CorrelationEntry(BaseModel):
    ref_a: str = Field(..., description="First driver ref (e.g. 'drv:units')")
    ref_b: str = Field(..., description="Second driver ref (e.g. 'drv:price')")
    rho: float = Field(..., ge=-1, le=1, description="Pearson correlation coefficient")
```

Add to `ModelConfig` (after `distributions` on line 252):

```python
    correlation_matrix: list[CorrelationEntry] = Field(default_factory=list)
```

### Step 2 — `sample_correlated()` in distributions.py

Add to `shared/fm_shared/analysis/distributions.py`:

```python
from scipy.stats import norm  # add to imports

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
    5. Map correlated normals to each distribution via Gaussian copula:
       u = Phi(correlated_i)  ->  uniform(0,1)
       Then use inverse CDF of each target distribution.
    """
```

**Key implementation details:**

- Build a `dict[str, int]` mapping each `config.ref` to its index
- For each `CorrelationEntry`, set `Sigma[i,j] = Sigma[j,i] = rho`
- Diagonal = 1.0
- Use `np.linalg.cholesky(Sigma)` — if it fails (not positive definite),
  fall back to independent sampling
- Convert correlated normals to uniform via `norm.cdf(correlated_i)`
- For each distribution, use inverse CDF sampling:
  - **normal**: `mean + std * correlated_i` (direct, skip copula)
  - **uniform**: `min + (max - min) * u`
  - **triangular**: `np.interp` or scipy `triang.ppf(u, ...)`
  - **lognormal**: `np.exp(mean + sigma * correlated_i)` (direct)
  - **pert**: use the beta PPF with PERT alpha/beta params
- Return `{ref: sampled_value}` for each distribution

### Step 3 — Update `monte_carlo.py`

In `shared/fm_shared/analysis/monte_carlo.py`, modify the sampling loop
(lines 71-76):

```python
# Add import at top:
from shared.fm_shared.analysis.distributions import sample, sample_correlated

# In the simulation loop, replace independent sampling:
for sim_i in range(num_simulations):
    ...
    if config.correlation_matrix and len(config.distributions) > 1:
        sampled = sample_correlated(
            config.distributions, config.correlation_matrix, rng
        )
        overrides = [
            ScenarioOverride(ref=ref, field="value", value=val)
            for ref, val in sampled.items()
        ]
    else:
        # Fall back to independent sampling (existing code)
        overrides = []
        for dist in config.distributions:
            val = sample(dist, 1, rng)[0]
            overrides.append(
                ScenarioOverride(ref=dist.ref, field="value", value=float(val))
            )
    overrides.extend(scenario_overrides)
    ...
```

### Step 4 — Tests

#### In `tests/unit/test_distributions.py`, add:

```python
def test_sample_correlated_high_positive() -> None:
    """rho=0.9 between two drivers produces Pearson > 0.7 over 500 samples."""
    from shared.fm_shared.analysis.distributions import sample_correlated
    from shared.fm_shared.model.schemas import CorrelationEntry, DistributionConfig

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
    from shared.fm_shared.model.schemas import CorrelationEntry, DistributionConfig

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
    from shared.fm_shared.model.schemas import CorrelationEntry, DistributionConfig

    configs = [
        DistributionConfig(ref="drv:a", family="normal", params={"mean": 10, "std": 2}),
        DistributionConfig(ref="drv:b", family="triangular", params={"min": 5, "mode": 10, "max": 15}),
    ]
    corr = [CorrelationEntry(ref_a="drv:a", ref_b="drv:b", rho=0.6)]
    s1 = sample_correlated(configs, corr, np.random.default_rng(7))
    s2 = sample_correlated(configs, corr, np.random.default_rng(7))
    assert s1 == s2


def test_sample_correlated_fallback_independent() -> None:
    """Single distribution with no correlations returns valid sample."""
    from shared.fm_shared.analysis.distributions import sample_correlated
    from shared.fm_shared.model.schemas import DistributionConfig

    configs = [
        DistributionConfig(ref="drv:solo", family="normal", params={"mean": 50, "std": 5}),
    ]
    rng = np.random.default_rng(1)
    s = sample_correlated(configs, [], rng)
    assert "drv:solo" in s
    assert isinstance(s["drv:solo"], float)
```

#### In `tests/unit/test_monte_carlo.py`, add:

```python
def test_run_monte_carlo_with_correlation() -> None:
    """MC with correlated distributions runs without error and respects seed."""
    from shared.fm_shared.model.schemas import CorrelationEntry

    d = minimal_model_config(horizon_months=3).model_dump()
    d["distributions"] = [
        {"ref": "drv:units", "family": "normal", "params": {"mean": 100, "std": 10}},
        {"ref": "drv:price", "family": "normal", "params": {"mean": 10, "std": 1}},
    ]
    d["correlation_matrix"] = [
        {"ref_a": "drv:units", "ref_b": "drv:price", "rho": 0.8}
    ]
    config = ModelConfig.model_validate(d)
    r1 = run_monte_carlo(config, num_simulations=20, seed=42)
    r2 = run_monte_carlo(config, num_simulations=20, seed=42)
    for metric in ("revenue", "ebitda"):
        np.testing.assert_array_almost_equal(
            r1.percentiles[metric]["p50"],
            r2.percentiles[metric]["p50"],
        )
```

## Constraints

1. **Do NOT modify any file not listed in the scope table.**
2. **Do NOT create a git worktree.**
3. **Do NOT refactor existing tests** — only add new test functions.
4. **Use `scipy.stats.norm` for CDF/PPF** — scipy is installed (`pyproject.toml`).
5. **Backward compatibility**: when `correlation_matrix` is empty (default),
   the MC runner must behave identically to the current implementation.
6. **All existing tests must still pass** (`python -m pytest tests/ -x`).
7. Run `python -m pytest tests/ -x --tb=short` at the end and report results.

## Verification Checklist

- [ ] `CorrelationEntry` model validates `rho` in [-1, 1]
- [ ] `ModelConfig.correlation_matrix` defaults to `[]`
- [ ] `sample_correlated()` uses Cholesky decomposition
- [ ] Graceful fallback if Cholesky fails (non-positive-definite)
- [ ] MC runner uses `sample_correlated()` when correlations present
- [ ] MC runner falls back to independent sampling when no correlations
- [ ] Test: high rho → high observed Pearson
- [ ] Test: zero rho → near-zero observed Pearson
- [ ] Test: deterministic with same seed
- [ ] All 385+ existing tests still pass
