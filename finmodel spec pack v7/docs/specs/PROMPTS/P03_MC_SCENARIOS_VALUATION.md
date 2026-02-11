# Phase 3 Prompt — Monte Carlo + Scenarios + Valuation

## Pre-requisites
- Phase 2 gate passed
- Read: `RUNTIME_ENGINE_SPEC.md` (MC wrapper, valuation module)
- Schema: `model_config_v1` (distributions, scenarios sections)

## Tasks

### 1. Distribution Engine
```
File: shared/fm_shared/analysis/distributions.py

class DistributionSampler:
    def sample(config: DistributionConfig, n: int, rng: np.random.Generator) -> np.ndarray

Supported families:
  triangular: np.random.triangular(min, mode, max)
  normal: np.random.normal(mean, std)
  lognormal: np.random.lognormal(mean, sigma)
  uniform: np.random.uniform(min, max)
  pert: beta distribution with PERT parameterization
    alpha = 1 + 4*(mode-min)/(max-min), beta = 1 + 4*(max-mode)/(max-min)
    sample = min + (max-min) * np.random.beta(alpha, beta)

All sampling uses the provided rng (seeded Generator) for reproducibility.
```

### 2. Monte Carlo Runner
```
File: shared/fm_shared/analysis/monte_carlo.py

def run_monte_carlo(
    config: ModelConfig,
    num_simulations: int,
    seed: int,
    scenario_id: str | None = None
) -> MCResult:

Implementation per RUNTIME_ENGINE_SPEC.md:
  1. Create seeded RNG: rng = np.random.default_rng(seed)
  2. For each sim in range(num_simulations):
     a. Deep copy assumptions
     b. For each distribution in config.distributions:
        Sample value from distribution using rng
        Set at path in assumptions copy
     c. Apply scenario overrides if scenario_id provided
     d. run_engine(config_with_sampled_assumptions)
     e. generate_statements()
     f. Collect key outputs: revenue, ebitda, fcf, net_income per period
  3. Compute percentiles: P5, P10, P25, P50, P75, P90, P95

MCResult:
  num_simulations: int
  seed: int
  percentiles: dict[str, dict[str, list[float]]]
    # { "revenue": { "p5": [...], "p50": [...], "p95": [...] }, ... }
  summary: dict  # terminal period stats

Performance: use numpy vectorization. Target: 1000 sims / 12 months < 10 seconds.
```

### 3. Scenario Management
```
File: apps/api/app/routers/scenarios.py

POST /api/v1/scenarios — { baseline_id, label, overrides: [...] }
GET /api/v1/scenarios — list for baseline
GET /api/v1/scenarios/{id}
DELETE /api/v1/scenarios/{id}

Scenarios stored in model_config.scenarios array (for committed baselines) or
as standalone artifacts for ad-hoc analysis.

Comparison endpoint:
POST /api/v1/scenarios/compare — { baseline_id, scenario_ids: [...] }
Returns side-by-side KPIs for each scenario.
```

### 4. Valuation Module
```
File: shared/fm_shared/analysis/valuation.py

def dcf_valuation(
    fcf_series: list[float],
    wacc: float,
    terminal_growth_rate: float | None = None,
    terminal_multiple: float | None = None,
    projection_years: int = 5
) -> DCFResult:
    # Discount FCFs: PV = FCF[t] / (1 + wacc)^t
    # Terminal value (one of):
    #   Perpetuity growth: TV = FCF[last] * (1 + g) / (wacc - g)
    #   Exit multiple: TV = EBITDA[last] * multiple
    # Discount TV to present
    # Enterprise value = sum of discounted FCFs + discounted TV

def multiples_valuation(
    metrics: dict,  # { "ebitda": float, "revenue": float, "net_income": float }
    comparables: list[dict]  # [{ "name": str, "ev_ebitda": float, ... }]
) -> MultiplesResult:
    # Apply median/mean of comparable multiples to entity metrics
    # Return implied EV range

If MC results available: compute valuation at each percentile → EV range.
```

### 5. Extended Run API
```
Extend POST /api/v1/runs:
  Body now accepts: mc_enabled, num_simulations, seed, scenario_id, valuation_config
  
New endpoints:
  GET /api/v1/runs/{id}/mc — MC percentile results
  GET /api/v1/runs/{id}/valuation — DCF + multiples results

Run flow (updated):
  1. Load baseline
  2. If scenario_id: apply overrides
  3. Run deterministic engine → statements → KPIs
  4. If mc_enabled: run_monte_carlo → store mc_results artifact
  5. If valuation_config: run valuation → store valuation artifact
```

### 6. MC + Valuation UI
```
apps/web/app/runs/[id]/mc/page.tsx:
  - Fan chart: Recharts AreaChart with P10/P50/P90 bands (shaded)
  - Tornado chart: horizontal bar chart showing sensitivity per driver
  - Histogram: distribution of terminal FCF or EV
  - Percentile table

apps/web/app/runs/[id]/valuation/page.tsx:
  - DCF waterfall or summary card
  - Implied multiples table
  - EV range (if MC enabled): bar showing P10-P90 range with P50 marker

apps/web/app/scenarios/page.tsx:
  - Scenario list with create button
  - Comparison table: scenarios as columns, KPIs as rows
```

### 7. Tests
Per TESTING_STRATEGY.md Phase 3 section.

## Verification
Verify Phase 3 gate criteria from BUILD_PLAN.md.
