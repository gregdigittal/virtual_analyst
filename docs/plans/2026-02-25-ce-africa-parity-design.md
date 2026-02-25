# CE-Africa Parity — Design Document

> Goal: Close the feature gaps between Virtual Analyst and CE-Africa so that
> VA can produce a structurally equivalent forecast and valuation for any
> scenario that CE-Africa can model.
>
> CE-Africa is a domain-specific mining equipment services model. VA is a
> general-purpose engine. "Structural equivalence" means VA can express the
> same financial logic (IS/BS/CF/DCF/MC) with equivalent accuracy, even if
> the revenue drivers use VA's generic stream types instead of CE-Africa's
> fleet wear profiles.

## Capability Mapping

### Already Covered (no work needed)

| Capability | CE-Africa | VA Equivalent |
|-----------|-----------|---------------|
| Revenue (fleet wear) | Installed-base × wear rate × utilization × inflation | `consumable_sale` streams with volume/pricing drivers + `ramp` inflation |
| Revenue (pipeline) | Prospect close date × confidence × annual value | Streams with `launch_month` + volume multiplier |
| Revenue (refurbishment) | Periodic major service revenue | Separate stream with interval-based volume driver |
| Income Statement | Revenue, COGS, Gross Profit, OpEx, EBIT, Interest, Tax, NI, Dividends | All line items present |
| Balance Sheet | Cash (plug), AR/Inv/AP (DSO/DIO/DPO), PPE, Debt, Equity | All line items present |
| Cash Flow | Operating (NI + D&A + ΔWC), Investing (CapEx), Financing (Debt/Equity) | All sections present |
| Working Capital | DSO, DIO, DPO — days-based calculation | Time-varying DriverValue for each |
| CapEx & Depreciation | Straight-line, % of revenue | Individual CapEx items with useful_life |
| Term Loans | Amortizing, bullet, interest-only | Draw/repayment schedules |
| Revolver | Cash-plug facility | `is_cash_plug=True` + waterfall |
| Overdraft | Auto-triggered on cash < 0 | Waterfall with overdraft facility type |
| Equity Raises | Lump-sum injection at month | `equity_raises` with amount + month |
| Dividends | Fixed amount or payout ratio | `DividendsPolicy` (none/fixed_amount/payout_ratio) |
| DCF Valuation | UFCF + WACC + terminal value (perpetuity or exit multiple) | `dcf_valuation` — identical methodology |
| Multiples | EV/EBITDA, EV/Revenue, P/E | `multiples_valuation` — EV/EBITDA, EV/Revenue, P/E |
| Monte Carlo | Log-normal, 1000 iterations, percentile bands | 5 families, 10K max, Cholesky correlation (VA ahead) |
| Scenarios | Clone + compare, independent assumptions | Scenario overrides with ref/field/value |

### VA Advantages Over CE-Africa

- **Correlated Monte Carlo** — Gaussian copula via Cholesky decomposition
- **Multi-entity consolidation** — FX translation, NCI, IC elimination
- **Business line segmentation** — launch timing, ramp curves (linear/S/step)
- **Driver blueprint DAG** — safe expression evaluation, topological sort
- **5 distribution families** — triangular, normal, lognormal, uniform, PERT
- **Evidence tracking** — assumption provenance with confidence levels

---

## Gaps to Close

### Gap 1 — Sensitivity Analysis

**CE-Africa feature:** Single-variable tornado charts (parameter range → metric
impact) and two-variable heat maps (e.g. WACC vs. terminal growth → EV matrix).
Located in `api/advanced_analysis.py`.

**VA today:** No built-in sensitivity analysis. Monte Carlo provides probabilistic
ranges but not structured "what-if" parameter sweeps.

**Design:**

New file `shared/fm_shared/analysis/sensitivity.py`:

```python
@dataclass
class SensitivityResult:
    parameter: str
    base_value: float
    values: list[float]           # parameter values tested
    metric_values: list[float]    # resulting metric for each value

@dataclass
class HeatMapResult:
    param_a: str
    param_b: str
    values_a: list[float]
    values_b: list[float]
    matrix: list[list[float]]     # metric[i][j] for param_a=values_a[i], param_b=values_b[j]

def run_sensitivity(
    config: ModelConfig,
    parameter_path: str,        # dot-path into config (e.g. "metadata.tax_rate")
    low: float,
    high: float,
    steps: int,
    metric: str,                # "revenue", "ebitda", "net_income", "ev", "fcf"
) -> SensitivityResult:
    """Sweep one parameter and record metric output at each step."""

def run_heatmap(
    config: ModelConfig,
    param_a_path: str,
    param_a_range: tuple[float, float, int],  # (low, high, steps)
    param_b_path: str,
    param_b_range: tuple[float, float, int],
    metric: str,
) -> HeatMapResult:
    """Sweep two parameters and build a metric matrix."""
```

Algorithm:
1. Deep-copy config
2. For each value in range: set parameter → run engine → extract metric
3. Collect results

For the heat map, iterate the Cartesian product of both ranges.

**Changes:**
- New file: `shared/fm_shared/analysis/sensitivity.py`
- New API endpoint: `POST /api/v1/runs/{run_id}/sensitivity`
- New frontend component: tornado chart + heat map on run detail page
- Schema: add `SensitivityConfig` to support saved sensitivity presets

**Tests:** Golden test with tax_rate sweep (0.15–0.35, 5 steps) verifying
monotonic decrease in net income. Heat map test with WACC × terminal_growth.

**Effort:** Medium (engine + API + frontend)

---

### Gap 2 — PIK (Payment-in-Kind) Interest

**CE-Africa feature:** Mezzanine debt with PIK interest that capitalizes
(compounds) instead of being paid monthly. Interest accrues on the balance
and is paid at maturity along with principal.

**VA today:** All debt interest is expensed monthly. No mechanism to capitalize
interest onto the principal balance.

**Design:**

Extend `DebtFacility` schema in `schemas.py`:

```python
class DebtFacility(BaseModel):
    # ... existing fields ...
    pik_rate: float = Field(0.0, ge=0, le=1)  # if > 0, interest capitalizes
```

Changes to `debt.py:calculate_debt_schedule`:
- When `pik_rate > 0`: instead of adding interest to `interest_per_period`,
  add it to the facility balance (compounding)
- At maturity (final repayment period): include accrued PIK in repayment amount
- Track PIK accrual separately for reporting

**Changes:**
- Modify: `shared/fm_shared/model/schemas.py` (1 field)
- Modify: `shared/fm_shared/model/debt.py` (PIK branch in loop)
- Modify: `shared/fm_shared/model/statements.py` (PIK interest reporting)

**Tests:** Golden test with PIK facility: $500K @ 10% PIK over 24 months.
Verify zero cash interest, compounding balance, lump-sum repayment at maturity.

**Effort:** Small

---

### Gap 3 — Convertible Debt

**CE-Africa feature:** Debt that converts to equity at a trigger date.
Pre-conversion: treated as debt (interest paid). Post-conversion: debt
removed, equity increased by conversion amount.

**VA today:** No debt-to-equity conversion mechanism.

**Design:**

Extend `DebtFacility` schema:

```python
class DebtFacility(BaseModel):
    # ... existing fields ...
    converts_to_equity_month: int | None = None  # month when conversion triggers
```

Changes to `statements.py`:
- At the conversion month: remove facility balance from debt, add to equity
- Stop interest accrual post-conversion
- Record conversion event in cash flow (non-cash: net zero CF impact)

**Changes:**
- Modify: `shared/fm_shared/model/schemas.py` (1 field)
- Modify: `shared/fm_shared/model/debt.py` (zero-out post-conversion)
- Modify: `shared/fm_shared/model/statements.py` (equity injection at conversion)

**Tests:** Golden test with $1M convertible @ 6%, converting at month 12.
Verify interest stops, debt removed from BS, equity increases.

**Effort:** Small

---

### Gap 4 — Debt Grace Periods

**CE-Africa feature:** Principal repayment deferred during grace period.
Interest still accrues and is paid monthly during grace.

**VA today:** Draw/repayment schedules are explicit (user sets exact months),
so grace can be approximated by starting repayments later. But there's no
`grace_period_months` parameter that automatically defers scheduled repayments.

**Design:**

Extend `DebtFacility` schema:

```python
class DebtFacility(BaseModel):
    # ... existing fields ...
    grace_period_months: int = Field(0, ge=0)
```

Changes to `debt.py`:
- During grace period: apply interest but skip any repayment_schedule entries
- After grace: resume repayment schedule (shifted by grace_period_months)

**Changes:**
- Modify: `shared/fm_shared/model/schemas.py` (1 field)
- Modify: `shared/fm_shared/model/debt.py` (skip repayments during grace)

**Tests:** Golden test with term loan, 6-month grace. Verify zero principal
repayment during grace, interest still accruing, repayments resume month 7.

**Effort:** Small

---

### Gap 5 — Trade Finance Instruments

**CE-Africa feature:** Short-term working capital facilities — Letters of
Credit, Import Finance, Stock Finance, Debtor Finance. These are drawn
against specific assets (inventory, receivables) with short tenors.

**VA today:** Only term_loan, revolver, overdraft facility types.

**Design:**

This is lower priority because VA's existing revolver/overdraft can
approximate most trade finance behavior (short-term, drawn against need,
repaid when cash available). The primary difference is that trade finance
limits are tied to asset values (e.g. debtor finance limit = 80% of AR).

Extend `DebtFacility` schema:

```python
class DebtFacility(BaseModel):
    # ... existing fields ...
    facility_type: Literal["term_loan", "revolver", "overdraft",
                           "trade_finance"] = "term_loan"
    asset_linked: Literal["ar", "inventory", None] = None
    advance_rate: float = Field(1.0, ge=0, le=1)  # % of linked asset available
```

Changes to `funding_waterfall.py`:
- For `trade_finance` with `asset_linked`: cap draw at `advance_rate × asset_value`
- Asset values come from the BS (AR or inventory at period t)

**Changes:**
- Modify: `shared/fm_shared/model/schemas.py` (2 fields + Literal extension)
- Modify: `shared/fm_shared/model/funding_waterfall.py` (asset-linked cap)

**Tests:** Golden test with debtor finance (80% advance on AR). Verify draw
capped at 80% of AR balance, repaid as AR collected.

**Effort:** Medium (requires waterfall to read BS values)

---

### Gap 6 — Granular OpEx Categories

**CE-Africa feature:** 31+ OpEx categories (Personnel, Facilities, Admin,
Sales, Other — each with subcategories like Salaries, Rent, Legal, Marketing,
Insurance, etc.) allocated by historical share percentages with per-category
growth rates.

**VA today:** 4 broad cost categories (`cogs`, `sga`, `rnd`, `other_opex`)
with individual cost items. Users can create many items but there's no
automatic "allocate total OpEx by historical category shares" mechanism.

**Design:**

This gap is more about convenience than capability. VA users can already
create 31 individual `FixedCostItem` entries with category labels. What's
missing is the automatic historical-share allocation pattern.

Two approaches:

**A. Driver blueprint approach (recommended):** Model OpEx categories as
formula nodes in the driver blueprint DAG. Define a "total_opex" driver,
then each category as `total_opex × share_pct × (1 + growth_rate)^t`.
This requires no engine changes — it uses existing DAG capabilities.

**B. Schema approach:** Add an `opex_categories` field to Assumptions with
explicit category names, historical shares, and growth rates. The engine
would allocate total OpEx across categories automatically.

Recommend approach A because it requires zero engine changes and exercises
existing DAG functionality. The frontend can provide a "category allocation"
template that generates the appropriate blueprint nodes.

**Changes (Approach A):**
- Frontend template/wizard that generates blueprint nodes for OpEx categories
- No engine changes needed

**Changes (Approach B, if preferred):**
- Modify: `shared/fm_shared/model/schemas.py` (OpExCategory model)
- Modify: `shared/fm_shared/model/statements.py` (allocation logic)

**Effort:** Small (approach A) or Medium (approach B)

---

## Implementation Backlog

Prioritized by user value and dependency order:

| Priority | Phase | Gap | Effort | Engine Files | New Files |
|----------|-------|-----|--------|-------------|-----------|
| **P0** | 7 | Sensitivity analysis | Medium | — | `sensitivity.py`, API endpoint, frontend |
| **P1** | 8a | PIK interest | Small | `schemas.py`, `debt.py`, `statements.py` | — |
| **P1** | 8b | Grace periods | Small | `schemas.py`, `debt.py` | — |
| **P1** | 8c | Convertible debt | Small | `schemas.py`, `debt.py`, `statements.py` | — |
| **P2** | 9 | Trade finance | Medium | `schemas.py`, `funding_waterfall.py` | — |
| **P3** | 10 | Granular OpEx (frontend template) | Small | — | Frontend wizard |

### Phase 7 — Sensitivity Analysis (P0)

Highest value: every financial model user expects tornado charts and what-if
tables. This is the most visible gap.

**Scope:**
1. `shared/fm_shared/analysis/sensitivity.py` — core sweep + heatmap functions
2. `apps/api/app/routers/runs.py` — `POST /sensitivity` endpoint
3. `apps/web/app/runs/[id]/sensitivity/page.tsx` — tornado + heatmap UI
4. Golden tests: monotonic sweep, 2D matrix

### Phase 8 — Advanced Debt Instruments (P1)

Three small, independent additions to the debt model. Can be done in one
phase since they share the same files.

**Scope:**
1. PIK interest (schemas + debt.py + statements.py)
2. Grace periods (schemas + debt.py)
3. Convertible debt (schemas + debt.py + statements.py)
4. Golden tests for each: PIK compounding, grace deferral, conversion event

### Phase 9 — Trade Finance (P2)

Asset-linked facilities. Depends on Phase 8 being stable (shared debt schema).

**Scope:**
1. Schema: new facility_type + asset_linked + advance_rate fields
2. Waterfall: asset-linked draw cap logic
3. Golden test: debtor finance capped at AR %

### Phase 10 — Granular OpEx Template (P3)

Frontend-only. Uses existing DAG blueprint — no engine changes.

**Scope:**
1. Frontend wizard: "OpEx Category Allocation" template
2. Generates blueprint nodes: total_opex driver + N category formula nodes
3. User inputs: category names, share %, growth rate per category

---

## Sequencing Summary

| Phase | Scope | Files Changed | New Files | Tests |
|-------|-------|--------------|-----------|-------|
| 7 | Sensitivity analysis | runs.py | sensitivity.py, frontend page | 4-6 |
| 8 | Advanced debt (PIK + grace + convertible) | schemas.py, debt.py, statements.py | — | 6-8 |
| 9 | Trade finance | schemas.py, funding_waterfall.py | — | 2-3 |
| 10 | Granular OpEx template | — | Frontend wizard | 0 (UI only) |

Each phase is independently committable and testable. Phases 8a/8b/8c are
independent within Phase 8 and can be parallelized. Phase 9 should follow
Phase 8 (shared schema). Phase 10 has no engine dependencies.

---

## Out of Scope

These CE-Africa features are NOT needed for structural equivalence:

- **Domain-specific fleet/wear modeling** — VA's generic streams cover this
- **NLP forecast config parsing** — VA has its own LLM integration
- **Historical share auto-calculation** — Phase 10 provides a manual template
- **Materialized views** — VA uses different persistence architecture
- **Legacy Streamlit UI** — VA has its own React frontend
- **AI assumptions generation** — Separate feature, not a parity gap
