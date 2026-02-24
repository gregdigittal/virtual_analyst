# DG Parity — Design Document

> Goal: Close the 6 feature gaps between Virtual Analyst and Digital Genius
> so that VA can produce equivalent financial model outputs for any DG scenario.
>
> Approach: Bottom-up engine-first (Phase 1-4 engine, Phase 5 validation,
> Phase 6 frontend). Each phase ships with TDD golden tests.

## Phase 1 — Debt & Interest Calculation

**Problem:** `statements.py:112-113` hardcodes `interest = [0.0] * horizon`.
The `DebtFacility` schema exists in `schemas.py:130-138` with draw/repay
schedules and interest_rate, but is never read.

**Design:**

New file `shared/fm_shared/model/debt.py`:

```python
@dataclass
class DebtScheduleResult:
    balance_per_period: dict[str, list[float]]   # facility_id -> [balance_t0..tn]
    interest_per_period: list[float]              # total interest per period
    draws_per_period: list[float]                 # total draws per period
    repayments_per_period: list[float]            # total repayments per period
    current_debt_per_period: list[float]          # maturing within 12 months
    non_current_debt_per_period: list[float]      # long-term portion

def calculate_debt_schedule(
    facilities: list[DebtFacility],
    horizon: int,
) -> DebtScheduleResult:
```

For each facility, per period t:
- `draws[t]` = sum of draw_schedule points at month t
- `repays[t]` = sum of repayment_schedule points at month t
- `balance[t]` = balance[t-1] + draws[t] - repays[t] (clamped to 0..limit)
- `interest[t]` = balance[t] * interest_rate / 12

Revolver with `is_cash_plug=True` is ignored in Phase 1 (wired in Phase 2
funding waterfall).

**Changes to statements.py:**

```python
# Line 112-113: replace hardcoded interest
from shared.fm_shared.model.debt import calculate_debt_schedule

debt_result = DebtScheduleResult(...)  # empty default
if config.assumptions.funding and config.assumptions.funding.debt_facilities:
    non_plug = [f for f in config.assumptions.funding.debt_facilities if not f.is_cash_plug]
    debt_result = calculate_debt_schedule(non_plug, horizon)

interest = debt_result.interest_per_period
```

Balance sheet additions:
- `debt_current` and `debt_non_current` lines
- `total_liabilities` = AP + debt_current + debt_non_current

Cash flow financing additions:
- `debt_draws` and `debt_repayments` lines
- `financing` = draws - repayments (replaces the plug)

**KPI updates (kpis.py:40-48):**
- `total_debt` = debt_current + debt_non_current from BS
- `debt_equity` = total_debt / total_equity
- `dscr` = ebitda / (interest + principal_repayment)

**Tests:** Golden test with 2 facilities (term loan $1M @ 8% with quarterly
repayments, revolver $500K @ 6% drawn month 3-12). Verify IS interest,
BS debt balances, CF financing, KPI debt_equity & DSCR.

---

## Phase 2 — Dividends & Funding Waterfall

**Problem:** `DividendsPolicy` and `EquityRaise` exist in schemas but are
never applied. DG has a cash shortfall detection → funding injection →
interest recalculation loop.

**Design:**

### 2a: Dividends

In `statements.py`, after net income calculation:

```python
dividend = 0.0
if config.assumptions.funding and config.assumptions.funding.dividends:
    policy = config.assumptions.funding.dividends
    if policy.policy == "fixed_amount":
        dividend = policy.value or 0.0
    elif policy.policy == "payout_ratio":
        dividend = max(0, ni * (policy.value or 0.0))
```

- Subtract from retained earnings: `re[t+1] = re[t] + ni - dividend`
- Add to CF financing: `dividends_paid`
- Add IS line: `dividends` (below net income, for transparency)

### 2b: Equity Raises

Apply `equity_raises` from funding config:
- For each raise, at raise.month: add to equity, add to CF financing

### 2c: Funding Waterfall

New file `shared/fm_shared/model/funding_waterfall.py`:

```python
@dataclass
class WaterfallResult:
    cash_after_funding: list[float]
    additional_draws: dict[str, list[float]]  # facility_id -> extra draws
    overdraft_interest: list[float]
    equity_injected: list[float]

def apply_funding_waterfall(
    closing_cash: list[float],          # from initial BS cash calc
    facilities: list[DebtFacility],     # only is_cash_plug=True facilities
    minimum_cash: float,                # from working_capital.minimum_cash
    horizon: int,
) -> WaterfallResult:
```

Algorithm per period t:
1. If `closing_cash[t] < minimum_cash`: shortfall detected
2. For each cash-plug facility (ordered: revolver first, overdraft last):
   - Draw `min(shortfall, facility.limit - current_balance)`
   - Reduce shortfall
3. If still negative and overdraft facility exists:
   - Record overdraft amount
   - `overdraft_interest[t] = |shortfall| * overdraft.interest_rate / 12`

### 2d: Three-Statement Feedback Loop

After initial statements generation:
1. Run funding waterfall on closing cash
2. Add waterfall draws to debt balances → recalculate interest
3. Add overdraft interest to IS interest_expense
4. Recalculate EBT, tax, NI, retained earnings
5. Recalculate BS cash plug
6. Validate balance (max 2 iterations to converge)

**Tests:** Golden test with a model that goes cash-negative in month 6.
Verify waterfall injects from revolver, interest recalculates, BS balances.

---

## Phase 3 — Monte Carlo Correlation

**Problem:** `monte_carlo.py:72-76` samples each distribution independently.
DG uses Cholesky decomposition for correlated sampling.

**Design:**

New schema field on `ModelConfig`:

```python
class CorrelationEntry(BaseModel):
    ref_a: str  # driver ref
    ref_b: str  # driver ref
    rho: float = Field(..., ge=-1, le=1)

# Add to ModelConfig:
correlation_matrix: list[CorrelationEntry] = Field(default_factory=list)
```

New function in `distributions.py`:

```python
def sample_correlated(
    configs: list[DistributionConfig],
    correlations: list[CorrelationEntry],
    rng: np.random.Generator,
) -> dict[str, float]:
    """Sample all distributions with Cholesky-based correlation."""
```

Algorithm:
1. Build correlation matrix from entries (default rho=0 for unspecified pairs)
2. Cholesky decomposition: `L = cholesky(Sigma)`
3. Sample independent standard normals: `z = rng.standard_normal(n)`
4. Transform: `correlated = L @ z`
5. Map correlated normals → each distribution via inverse CDF (for non-normal
   distributions: use Gaussian copula approach)

Update `monte_carlo.py` to call `sample_correlated()` when correlation
entries exist, falling back to independent sampling otherwise.

**Tests:** Verify that with rho=0.9 between two drivers, output samples
show strong positive correlation (Pearson > 0.8). Verify rho=0 produces
near-zero correlation.

---

## Phase 4 — Business Line Segmentation

**Problem:** VA has flat `RevenueStream` objects. DG has hierarchical
`BusinessLine` + `Market` segmentation with timing/ramp-up.

**Design:**

Extend `RevenueStream` in schemas.py:

```python
class RevenueStream(BaseModel):
    stream_id: str
    label: str
    stream_type: Literal[...]
    drivers: RevenueStreamDrivers
    # New fields:
    business_line: str | None = None       # grouping label
    market: str | None = None              # geographic/channel segment
    launch_month: int | None = None        # when this stream activates (0-indexed)
    ramp_up_months: int | None = None      # months to reach full volume
    ramp_curve: Literal["linear", "s_curve", "step"] = "linear"
```

Engine changes (`engine.py`):
- When `launch_month` is set, revenue for periods before launch_month = 0
- During ramp_up_months, apply ramp_curve factor (0→1) to volume driver

Statement changes:
- Track revenue by `business_line` label in engine output (metadata on
  time_series)
- Add optional `revenue_by_segment` dict to Statements output

No DB schema changes needed — these are model_config fields stored as JSON.

**Tests:** Golden test with 3 streams across 2 business lines, one launching
month 6 with 6-month S-curve ramp. Verify zero revenue pre-launch, ramp
profile, and segment totals.

---

## Phase 5 — Consolidation Integration Validation

**Problem:** The consolidation engine (`consolidation.py`) and org structure
tables exist but haven't been tested against a real multi-entity scenario
matching DG's structure.

**Design:**

Create an integration test fixture replicating DG's structure:
- Holding company (USD) owning 2 subsidiaries
- Sub A (GBP, 80% owned — full consolidation, 20% NCI)
- Sub B (KES, 100% owned — full consolidation)
- Intercompany: management fee from Sub A→Holding, loan from Holding→Sub B
- FX rates: GBP/USD = 1.27 avg / 1.25 closing, KES/USD = 0.0077

Test assertions:
1. Each entity's standalone statements match expected values
2. Consolidated IS eliminates IC revenue/expense
3. NCI = 20% of Sub A's net income
4. BS: IC receivable/payable eliminated, NCI equity shown
5. FX: IS at avg rate, BS at closing rate, CTA calculated
6. Waterfall: Sub B goes cash-negative, waterfall injects from revolver

File: `tests/golden/test_consolidation_dg_parity.py`

---

## Phase 6 — Frontend (deferred to separate plan)

UI components needed:
- Funding configuration panel (debt facilities, equity raises, dividends)
- Business line segmentation in baseline editor
- Consolidated run results view (entity breakdown, NCI, eliminations)
- MC correlation matrix editor

These are frontend-only changes building on existing page patterns.
Deferred to a separate Cursor prompt after engine phases are complete.

---

## Sequencing Summary

| Phase | Scope | Files Changed | New Files | Estimated Tests |
|-------|-------|---------------|-----------|-----------------|
| 1 | Debt & interest | statements.py, kpis.py | debt.py | 8-10 |
| 2 | Dividends, equity, waterfall | statements.py | funding_waterfall.py | 10-12 |
| 3 | MC correlation | monte_carlo.py, distributions.py, schemas.py | — | 4-6 |
| 4 | Business line segmentation | schemas.py, engine.py, statements.py | — | 6-8 |
| 5 | Consolidation validation | — | test_consolidation_dg_parity.py | 8-10 |
| 6 | Frontend | apps/web/ pages | — | — |

Each phase is independently committable and testable. Phase 5 exercises
all prior phases together. Phase 6 is a separate frontend effort.
