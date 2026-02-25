# CE-Africa Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close 6 feature gaps between Virtual Analyst and CE-Africa so VA can produce structurally equivalent forecasts and valuations.

**Architecture:** Four phases extending the existing engine (`shared/fm_shared/model/`), analysis layer (`shared/fm_shared/analysis/`), API (`apps/api/app/routers/`), and frontend (`apps/web/`). Each phase is independently committable and testable. TDD throughout — golden tests with hand-verified fixtures.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, NumPy, Next.js 14 (App Router), Tailwind CSS, pytest (asyncio_mode=auto)

**Design doc:** `docs/plans/2026-02-25-ce-africa-parity-design.md`

---

## Phase 7 — Sensitivity Analysis (P0)

> The existing `GET /runs/{run_id}/sensitivity` endpoint (runs.py:460-530) does
> one-at-a-time tornado on terminal FCF only, using `±pct` multipliers on
> distribution refs. CE-Africa has: (a) custom parameter sweeps with explicit
> low/high/steps, (b) multiple target metrics, and (c) two-variable heat maps.
>
> We extract the sweep logic into a reusable `analysis/sensitivity.py` module,
> add heat-map support, and extend the existing endpoint + frontend page.

### Task 7.1: Core sensitivity sweep function — test

**Files:**
- Create: `tests/unit/test_sensitivity.py`
- Will create in 7.2: `shared/fm_shared/analysis/sensitivity.py`

**Step 1: Write the failing test**

```python
"""Unit tests for sensitivity sweep and heat map."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from shared.fm_shared.model import ModelConfig

# Will be created in task 7.2
from shared.fm_shared.analysis.sensitivity import (
    SensitivityResult,
    run_sensitivity,
)

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "golden"
CONFIG_PATH = GOLDEN_DIR / "debt_config.json"


def _load_config() -> ModelConfig:
    data = json.loads(CONFIG_PATH.read_text())
    return ModelConfig.model_validate(data)


def test_sensitivity_tax_rate_sweep_monotonic() -> None:
    """Sweeping tax_rate 0.15→0.35 should monotonically decrease net_income."""
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
    # Higher tax → lower net income: monotonic decrease
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_sensitivity.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'shared.fm_shared.analysis.sensitivity'`

---

### Task 7.2: Core sensitivity sweep function — implement

**Files:**
- Create: `shared/fm_shared/analysis/sensitivity.py`

**Step 3: Write minimal implementation**

```python
"""Sensitivity analysis — single-variable sweeps and two-variable heat maps."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.model.kpis import calculate_kpis


@dataclass
class SensitivityResult:
    parameter: str
    base_value: float
    values: list[float]
    metric_values: list[float]


@dataclass
class HeatMapResult:
    param_a: str
    param_b: str
    values_a: list[float]
    values_b: list[float]
    matrix: list[list[float]]  # matrix[i][j] = metric at (values_a[i], values_b[j])


def _get_nested(obj: object, path: str) -> float:
    """Resolve a dot-path like 'metadata.tax_rate' on a Pydantic model."""
    parts = path.split(".")
    cur: object = obj
    for p in parts:
        if isinstance(cur, dict):
            cur = cur[p]
        else:
            cur = getattr(cur, p)
    return float(cur)  # type: ignore[arg-type]


def _set_nested(obj: object, path: str, value: float) -> None:
    """Set a value at a dot-path on a Pydantic model (mutates in place)."""
    parts = path.split(".")
    cur: object = obj
    for p in parts[:-1]:
        if isinstance(cur, dict):
            cur = cur[p]
        else:
            cur = getattr(cur, p)
    if isinstance(cur, dict):
        cur[parts[-1]] = value
    else:
        setattr(cur, parts[-1], value)


_TERMINAL_METRICS = {
    "revenue": lambda is_list: sum(p["revenue"] for p in is_list),
    "ebitda": lambda is_list: sum(p["ebitda"] for p in is_list),
    "net_income": lambda is_list: sum(p["net_income"] for p in is_list),
    "fcf": lambda kpis: sum(p["fcf"] for p in kpis),
}


def _extract_metric(config: ModelConfig, metric: str) -> float:
    """Run engine + statements + kpis and extract the summed metric."""
    ts = run_engine(config)
    stmts = generate_statements(config, ts)
    if metric == "fcf":
        kpis = calculate_kpis(stmts)
        return _TERMINAL_METRICS[metric](kpis)
    return _TERMINAL_METRICS[metric](stmts.income_statement)


def run_sensitivity(
    config: ModelConfig,
    parameter_path: str,
    low: float,
    high: float,
    steps: int,
    metric: str,
) -> SensitivityResult:
    """Sweep one parameter from low to high and record metric output at each step."""
    if metric not in _TERMINAL_METRICS:
        raise ValueError(f"Unknown metric '{metric}'. Valid: {list(_TERMINAL_METRICS)}")
    if steps < 2:
        raise ValueError("steps must be >= 2")

    base_value = _get_nested(config, parameter_path)
    step_size = (high - low) / (steps - 1)
    values: list[float] = [low + i * step_size for i in range(steps)]
    metric_values: list[float] = []

    for v in values:
        cfg = config.model_copy(deep=True)
        _set_nested(cfg, parameter_path, v)
        metric_values.append(_extract_metric(cfg, metric))

    return SensitivityResult(
        parameter=parameter_path,
        base_value=base_value,
        values=[round(v, 10) for v in values],
        metric_values=[round(m, 2) for m in metric_values],
    )


def run_heatmap(
    config: ModelConfig,
    param_a_path: str,
    param_a_range: tuple[float, float, int],
    param_b_path: str,
    param_b_range: tuple[float, float, int],
    metric: str,
) -> HeatMapResult:
    """Sweep two parameters and build a metric matrix."""
    if metric not in _TERMINAL_METRICS:
        raise ValueError(f"Unknown metric '{metric}'. Valid: {list(_TERMINAL_METRICS)}")

    a_low, a_high, a_steps = param_a_range
    b_low, b_high, b_steps = param_b_range
    if a_steps < 2 or b_steps < 2:
        raise ValueError("steps must be >= 2 for both parameters")

    a_step = (a_high - a_low) / (a_steps - 1)
    b_step = (b_high - b_low) / (b_steps - 1)
    values_a = [a_low + i * a_step for i in range(a_steps)]
    values_b = [b_low + j * b_step for j in range(b_steps)]

    matrix: list[list[float]] = []
    for va in values_a:
        row: list[float] = []
        for vb in values_b:
            cfg = config.model_copy(deep=True)
            _set_nested(cfg, param_a_path, va)
            _set_nested(cfg, param_b_path, vb)
            row.append(round(_extract_metric(cfg, metric), 2))
        matrix.append(row)

    return HeatMapResult(
        param_a=param_a_path,
        param_b=param_b_path,
        values_a=[round(v, 10) for v in values_a],
        values_b=[round(v, 10) for v in values_b],
        matrix=matrix,
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_sensitivity.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add shared/fm_shared/analysis/sensitivity.py tests/unit/test_sensitivity.py
git commit -m "feat: sensitivity sweep and heat map analysis module (Phase 7.1-7.2)"
```

---

### Task 7.3: Heat map test

**Files:**
- Modify: `tests/unit/test_sensitivity.py`

**Step 1: Add heat map test**

Append to `tests/unit/test_sensitivity.py`:

```python
from shared.fm_shared.analysis.sensitivity import HeatMapResult, run_heatmap


def test_heatmap_tax_rate_vs_initial_cash() -> None:
    """2D sweep: tax_rate × initial_cash → net_income matrix."""
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
    # Higher tax → lower net income (each row should decrease left-to-right... actually
    # tax_rate is param_a so rows correspond to increasing tax_rate)
    for i in range(1, len(result.matrix)):
        # Higher tax_rate row should have lower net_income than previous row
        assert result.matrix[i][0] <= result.matrix[i - 1][0], (
            f"Expected row {i} (tax={result.values_a[i]}) <= row {i-1} (tax={result.values_a[i-1]})"
        )
```

**Step 2: Run test to verify it passes**

Run: `pytest tests/unit/test_sensitivity.py -v`
Expected: PASS (3 tests)

**Step 3: Commit**

```bash
git add tests/unit/test_sensitivity.py
git commit -m "test: heat map sensitivity test (Phase 7.3)"
```

---

### Task 7.4: API endpoint — enhanced sensitivity with heat map

**Files:**
- Modify: `apps/api/app/routers/runs.py:460-530`

**Step 1: Add POST endpoint for custom sensitivity sweeps**

Add after the existing `GET /{run_id}/sensitivity` endpoint (after line 530 in `runs.py`):

```python
class SensitivityBody(BaseModel):
    parameter_path: str = PydField(..., description="Dot-path into config, e.g. 'metadata.tax_rate'")
    low: float = PydField(...)
    high: float = PydField(...)
    steps: int = PydField(5, ge=2, le=20)
    metric: str = PydField("net_income", description="revenue, ebitda, net_income, fcf")


class HeatMapBody(BaseModel):
    param_a_path: str = PydField(...)
    param_a_range: tuple[float, float, int] = PydField(...)  # (low, high, steps)
    param_b_path: str = PydField(...)
    param_b_range: tuple[float, float, int] = PydField(...)
    metric: str = PydField("net_income")


@router.post("/{run_id}/sensitivity/sweep")
async def run_sensitivity_sweep(
    run_id: str,
    body: SensitivityBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    _: None = require_role(*ROLES_ANY),
) -> dict[str, Any]:
    """Custom parameter sweep: vary one parameter over a range, return metric values."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    config = await _load_run_config(run_id, x_tenant_id, store)
    from shared.fm_shared.analysis.sensitivity import run_sensitivity as _run_sens
    try:
        result = _run_sens(
            config=config,
            parameter_path=body.parameter_path,
            low=body.low,
            high=body.high,
            steps=body.steps,
            metric=body.metric,
        )
    except (ValueError, AttributeError, KeyError) as e:
        raise HTTPException(400, str(e)) from e
    return {
        "parameter": result.parameter,
        "base_value": result.base_value,
        "values": result.values,
        "metric_values": result.metric_values,
        "metric": body.metric,
    }


@router.post("/{run_id}/sensitivity/heatmap")
async def run_sensitivity_heatmap(
    run_id: str,
    body: HeatMapBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    _: None = require_role(*ROLES_ANY),
) -> dict[str, Any]:
    """Two-variable heat map: sweep two parameters, return metric matrix."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    config = await _load_run_config(run_id, x_tenant_id, store)
    from shared.fm_shared.analysis.sensitivity import run_heatmap as _run_hm
    try:
        result = _run_hm(
            config=config,
            param_a_path=body.param_a_path,
            param_a_range=body.param_a_range,
            param_b_path=body.param_b_path,
            param_b_range=body.param_b_range,
            metric=body.metric,
        )
    except (ValueError, AttributeError, KeyError) as e:
        raise HTTPException(400, str(e)) from e
    return {
        "param_a": result.param_a,
        "param_b": result.param_b,
        "values_a": result.values_a,
        "values_b": result.values_b,
        "matrix": result.matrix,
        "metric": body.metric,
    }
```

Also add a helper to deduplicate config loading (extract from the existing `get_run_sensitivity`). Add above the existing endpoint:

```python
async def _load_run_config(
    run_id: str, tenant_id: str, store: ArtifactStore
) -> ModelConfig:
    """Load the ModelConfig for a given run (shared by sensitivity endpoints)."""
    async with tenant_conn(tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT baseline_id, baseline_version FROM runs WHERE tenant_id = $1 AND run_id = $2",
            tenant_id,
            run_id,
        )
        if not row:
            raise HTTPException(404, "Run not found")
    baseline_id, baseline_version = row["baseline_id"], row["baseline_version"]
    try:
        config_dict = store.load(tenant_id, "model_config_v1", f"{baseline_id}_{baseline_version}")
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Baseline not found") from e
        raise
    return ModelConfig.model_validate(config_dict)
```

Add import at top of file:

```python
from shared.fm_shared.analysis.sensitivity import run_sensitivity as _run_sens, run_heatmap as _run_hm
```

**Step 2: Run tests**

Run: `pytest tests/ -v -k "sensitivity" --no-header`
Expected: PASS

**Step 3: Commit**

```bash
git add apps/api/app/routers/runs.py
git commit -m "feat: POST sensitivity/sweep and sensitivity/heatmap API endpoints (Phase 7.4)"
```

---

### Task 7.5: Frontend — heat map on sensitivity page

**Files:**
- Modify: `apps/web/app/runs/[id]/sensitivity/page.tsx`
- Modify: `apps/web/lib/api.ts` (add API method for heat map)

**Step 1: Add heat map API method to `apps/web/lib/api.ts`**

Find the `runs` object in the api module and add:

```typescript
async postSensitivitySweep(
  tenantId: string,
  runId: string,
  body: { parameter_path: string; low: number; high: number; steps: number; metric: string },
): Promise<Record<string, unknown>> {
  const res = await this.fetch(`/api/v1/runs/${runId}/sensitivity/sweep`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Tenant-ID": tenantId },
    body: JSON.stringify(body),
  });
  return res.json();
},

async postSensitivityHeatmap(
  tenantId: string,
  runId: string,
  body: {
    param_a_path: string;
    param_a_range: [number, number, number];
    param_b_path: string;
    param_b_range: [number, number, number];
    metric: string;
  },
): Promise<Record<string, unknown>> {
  const res = await this.fetch(`/api/v1/runs/${runId}/sensitivity/heatmap`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Tenant-ID": tenantId },
    body: JSON.stringify(body),
  });
  return res.json();
},
```

**Step 2: Add heat map section to sensitivity page**

In `apps/web/app/runs/[id]/sensitivity/page.tsx`, add a heat map section below the tornado chart. Add state for heat map data and a simple form to configure the two parameters. Display the matrix as a color-coded grid using Tailwind utility classes (bg-opacity scaled by value).

This is a UI enhancement — the exact styling follows VA's existing pattern of `VACard` containers with `font-mono` numeric display and `bg-va-blue` / `bg-va-danger` color theming.

**Step 3: Build and verify**

Run: `cd apps/web && npx next build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add apps/web/app/runs/\[id\]/sensitivity/page.tsx apps/web/lib/api.ts
git commit -m "feat: heat map UI on sensitivity page (Phase 7.5)"
```

---

## Phase 8 — Advanced Debt Instruments (P1)

> Three independent additions to the debt model. All modify `schemas.py` and
> `debt.py`; PIK and convertible also touch `statements.py`. They share the
> same files but each is independently testable.

### Task 8a.1: PIK interest — test

**Files:**
- Create: `tests/unit/test_pik_interest.py`

**Step 1: Write the failing test**

```python
"""Test PIK (Payment-in-Kind) interest: capitalizes instead of cash payment."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.model.debt import calculate_debt_schedule

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "golden"
CONFIG_PATH = GOLDEN_DIR / "debt_config.json"


def _load_config() -> ModelConfig:
    data = json.loads(CONFIG_PATH.read_text())
    return ModelConfig.model_validate(data)


def test_pik_interest_capitalizes() -> None:
    """PIK facility: interest added to balance, not to IS interest_expense."""
    config = _load_config()
    # Replace the existing term loan with a PIK facility
    config.assumptions.funding.debt_facilities = [
        config.assumptions.funding.debt_facilities[0].model_copy(
            update={
                "facility_id": "pik_1",
                "label": "Mezzanine PIK",
                "interest_rate": 0.10,
                "pik_rate": 1.0,  # 100% PIK — all interest capitalizes
                "draw_schedule": [{"month": 0, "amount": 500000}],
                "repayment_schedule": [{"month": 23, "amount": 0}],  # repay at maturity
                "limit": 2000000,
            }
        )
    ]
    config.metadata.horizon_months = 24

    result = calculate_debt_schedule(config.assumptions.funding.debt_facilities, 24)

    # Cash interest should be zero every period (all PIK)
    for t in range(24):
        assert result.interest_per_period[t] == pytest.approx(0.0, abs=0.01), (
            f"Period {t}: expected zero cash interest, got {result.interest_per_period[t]}"
        )

    # Balance should compound: 500000 * (1 + 0.10/12)^24
    expected_balance_m24 = 500000.0
    for _ in range(24):
        expected_balance_m24 += expected_balance_m24 * 0.10 / 12
    final_balance = result.balance_per_period["pik_1"][-1]
    assert final_balance == pytest.approx(expected_balance_m24, rel=0.001)


def test_pik_partial() -> None:
    """PIK rate of 0.5 means 50% capitalizes, 50% is cash interest."""
    config = _load_config()
    config.assumptions.funding.debt_facilities = [
        config.assumptions.funding.debt_facilities[0].model_copy(
            update={
                "facility_id": "pik_partial",
                "interest_rate": 0.12,
                "pik_rate": 0.5,
                "draw_schedule": [{"month": 0, "amount": 100000}],
                "repayment_schedule": [],
                "limit": 500000,
            }
        )
    ]

    result = calculate_debt_schedule(config.assumptions.funding.debt_facilities, 12)

    # Period 0: balance = 100000, total interest = 100000 * 0.12 / 12 = 1000
    # Cash interest = 1000 * (1 - 0.5) = 500
    # PIK capitalized = 1000 * 0.5 = 500 → new balance = 100500
    assert result.interest_per_period[0] == pytest.approx(500.0, abs=1.0)
    assert result.balance_per_period["pik_partial"][0] == pytest.approx(100500.0, abs=1.0)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_pik_interest.py -v`
Expected: FAIL — `pik_rate` not a valid field on `DebtFacility`

---

### Task 8a.2: PIK interest — implement

**Files:**
- Modify: `shared/fm_shared/model/schemas.py:127-135` (add `pik_rate` field)
- Modify: `shared/fm_shared/model/debt.py:80-88` (PIK branch in per-period loop)

**Step 1: Add `pik_rate` to DebtFacility schema**

In `schemas.py`, add field after `is_cash_plug` (line 135):

```python
class DebtFacility(BaseModel):
    facility_id: str = Field(...)
    label: str = Field(...)
    type: Literal["term_loan", "revolver", "overdraft"] = Field(...)
    limit: float = Field(..., ge=0)
    interest_rate: float = Field(..., ge=0, le=1)
    draw_schedule: list[DrawRepayPoint] | None = None
    repayment_schedule: list[DrawRepayPoint] | None = None
    is_cash_plug: bool = False
    pik_rate: float = Field(0.0, ge=0, le=1, description="Fraction of interest that capitalizes (0=all cash, 1=all PIK)")
```

**Step 2: Modify debt schedule calculation**

In `debt.py`, change the per-period loop (lines 80-88). Replace:

```python
            balances.append(balance)
            result.interest_per_period[t] += balance * fac.interest_rate / 12
```

With:

```python
            total_interest = balance * fac.interest_rate / 12
            pik_portion = total_interest * fac.pik_rate
            cash_interest = total_interest - pik_portion
            balance += pik_portion  # PIK capitalizes onto principal
            balance = max(0.0, min(fac.limit, balance))
            balances.append(balance)
            result.interest_per_period[t] += cash_interest
```

Note: the PIK capitalization must happen *before* clamping to limit and appending to balances, and *after* the draws/repays for the period.

**Step 3: Run test to verify it passes**

Run: `pytest tests/unit/test_pik_interest.py -v`
Expected: PASS (2 tests)

**Step 4: Run existing debt golden test to verify no regression**

Run: `pytest tests/golden/test_debt_golden.py -v`
Expected: PASS (existing facilities have `pik_rate=0.0` by default, so behavior unchanged)

**Step 5: Commit**

```bash
git add shared/fm_shared/model/schemas.py shared/fm_shared/model/debt.py tests/unit/test_pik_interest.py
git commit -m "feat: PIK interest — capitalizing interest on debt facilities (Phase 8a)"
```

---

### Task 8b.1: Grace periods — test

**Files:**
- Create: `tests/unit/test_grace_periods.py`

**Step 1: Write the failing test**

```python
"""Test debt grace periods: principal deferred, interest still accrues."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.fm_shared.model import ModelConfig
from shared.fm_shared.model.debt import calculate_debt_schedule

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "golden"
CONFIG_PATH = GOLDEN_DIR / "debt_config.json"


def _load_config() -> ModelConfig:
    data = json.loads(CONFIG_PATH.read_text())
    return ModelConfig.model_validate(data)


def test_grace_period_defers_repayments() -> None:
    """6-month grace: zero principal repayment during grace, interest still accrues."""
    config = _load_config()
    config.assumptions.funding.debt_facilities = [
        config.assumptions.funding.debt_facilities[0].model_copy(
            update={
                "facility_id": "grace_1",
                "interest_rate": 0.08,
                "grace_period_months": 6,
                "draw_schedule": [{"month": 0, "amount": 600000}],
                "repayment_schedule": [
                    {"month": i, "amount": 100000} for i in range(12)
                ],
                "limit": 1000000,
            }
        )
    ]

    result = calculate_debt_schedule(config.assumptions.funding.debt_facilities, 12)

    # During grace (months 0-5): no principal repayments
    for t in range(6):
        assert result.repayments_per_period[t] == pytest.approx(0.0, abs=0.01), (
            f"Month {t}: expected zero repayment during grace, got {result.repayments_per_period[t]}"
        )

    # Interest should still accrue during grace
    for t in range(6):
        expected_interest = 600000 * 0.08 / 12  # balance constant during grace
        assert result.interest_per_period[t] == pytest.approx(expected_interest, abs=1.0), (
            f"Month {t}: expected interest {expected_interest}, got {result.interest_per_period[t]}"
        )

    # After grace (months 6-11): repayments resume
    for t in range(6, 12):
        assert result.repayments_per_period[t] == pytest.approx(100000.0, abs=0.01), (
            f"Month {t}: expected repayment 100000, got {result.repayments_per_period[t]}"
        )
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_grace_periods.py -v`
Expected: FAIL — `grace_period_months` not a valid field on `DebtFacility`

---

### Task 8b.2: Grace periods — implement

**Files:**
- Modify: `shared/fm_shared/model/schemas.py:127-136` (add `grace_period_months`)
- Modify: `shared/fm_shared/model/debt.py:80-88` (skip repayments during grace)

**Step 1: Add `grace_period_months` to DebtFacility schema**

In `schemas.py`, add field after `pik_rate`:

```python
    grace_period_months: int = Field(0, ge=0, description="Months during which principal repayment is deferred")
```

**Step 2: Modify debt schedule to skip repayments during grace**

In `debt.py`, in the per-period loop, change how `repay_t` is calculated. Before the existing:

```python
            repay_t = _repays_at_month(fac.repayment_schedule, t)
```

Replace with:

```python
            if t < fac.grace_period_months:
                repay_t = 0.0  # Grace period: defer principal
            else:
                repay_t = _repays_at_month(fac.repayment_schedule, t)
```

**Step 3: Run test to verify it passes**

Run: `pytest tests/unit/test_grace_periods.py -v`
Expected: PASS

**Step 4: Run existing debt golden test to verify no regression**

Run: `pytest tests/golden/test_debt_golden.py -v`
Expected: PASS (existing facilities have `grace_period_months=0` by default)

**Step 5: Commit**

```bash
git add shared/fm_shared/model/schemas.py shared/fm_shared/model/debt.py tests/unit/test_grace_periods.py
git commit -m "feat: debt grace periods — deferred principal repayment (Phase 8b)"
```

---

### Task 8c.1: Convertible debt — test

**Files:**
- Create: `tests/unit/test_convertible_debt.py`

**Step 1: Write the failing test**

```python
"""Test convertible debt: converts to equity at trigger month."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.model.debt import calculate_debt_schedule

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "golden"
CONFIG_PATH = GOLDEN_DIR / "debt_config.json"


def _load_config() -> ModelConfig:
    data = json.loads(CONFIG_PATH.read_text())
    return ModelConfig.model_validate(data)


def test_convertible_debt_zeroes_at_conversion() -> None:
    """Debt balance drops to zero at conversion month, interest stops."""
    config = _load_config()
    config.assumptions.funding.debt_facilities = [
        config.assumptions.funding.debt_facilities[0].model_copy(
            update={
                "facility_id": "conv_1",
                "label": "Convertible Note",
                "interest_rate": 0.06,
                "converts_to_equity_month": 6,
                "draw_schedule": [{"month": 0, "amount": 1000000}],
                "repayment_schedule": [],
                "limit": 1000000,
            }
        )
    ]
    config.metadata.horizon_months = 12

    result = calculate_debt_schedule(config.assumptions.funding.debt_facilities, 12)

    # Pre-conversion (months 0-5): balance = 1M, interest accrues
    for t in range(6):
        assert result.balance_per_period["conv_1"][t] == pytest.approx(1000000.0, abs=1.0)
        expected_interest = 1000000.0 * 0.06 / 12
        assert result.interest_per_period[t] == pytest.approx(expected_interest, abs=1.0)

    # Post-conversion (months 6-11): balance = 0, interest = 0
    for t in range(6, 12):
        assert result.balance_per_period["conv_1"][t] == pytest.approx(0.0, abs=0.01)
        assert result.interest_per_period[t] == pytest.approx(0.0, abs=0.01)


def test_convertible_debt_equity_increase() -> None:
    """At conversion month, equity increases by the converted amount."""
    config = _load_config()
    config.assumptions.funding.debt_facilities = [
        config.assumptions.funding.debt_facilities[0].model_copy(
            update={
                "facility_id": "conv_2",
                "label": "Convertible",
                "interest_rate": 0.06,
                "converts_to_equity_month": 3,
                "draw_schedule": [{"month": 0, "amount": 500000}],
                "repayment_schedule": [],
                "limit": 500000,
            }
        )
    ]
    config.metadata.horizon_months = 12

    ts = run_engine(config)
    stmts = generate_statements(config, ts)

    # After conversion at month 3, debt should be gone from BS
    for t in range(3, 12):
        assert stmts.balance_sheet[t]["debt_current"] == pytest.approx(0.0, abs=1.0)
        assert stmts.balance_sheet[t]["debt_non_current"] == pytest.approx(0.0, abs=1.0)

    # Equity should be higher post-conversion (by ~500K minus any tax effects)
    equity_pre = stmts.balance_sheet[2]["total_equity"]
    equity_post = stmts.balance_sheet[3]["total_equity"]
    # Equity jumps by roughly the conversion amount (plus net income)
    ni_m3 = stmts.income_statement[3]["net_income"]
    equity_increase = equity_post - equity_pre - ni_m3
    assert equity_increase == pytest.approx(500000.0, rel=0.05)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_convertible_debt.py -v`
Expected: FAIL — `converts_to_equity_month` not a valid field on `DebtFacility`

---

### Task 8c.2: Convertible debt — implement

**Files:**
- Modify: `shared/fm_shared/model/schemas.py:127-136` (add `converts_to_equity_month`)
- Modify: `shared/fm_shared/model/debt.py:80-88` (zero-out post-conversion)
- Modify: `shared/fm_shared/model/statements.py:153-158` (equity injection at conversion)

**Step 1: Add `converts_to_equity_month` to DebtFacility schema**

In `schemas.py`, add field after `grace_period_months`:

```python
    converts_to_equity_month: int | None = Field(None, ge=0, description="Month when debt converts to equity (None=never)")
```

**Step 2: Modify debt schedule for conversion**

In `debt.py`, in the per-period loop, after the PIK logic and before appending balance, add conversion check:

```python
            # Convertible: zero-out at conversion month
            if fac.converts_to_equity_month is not None and t >= fac.converts_to_equity_month:
                if t == fac.converts_to_equity_month:
                    # Record the conversion amount for statements to pick up
                    result.repayments_per_period[t] += balance  # "repay" via conversion
                balance = 0.0
                balances.append(0.0)
                # No interest post-conversion
                continue
```

Note: place this check right after draws/repays/PIK but before the interest calculation. The `continue` skips interest and the normal balance append.

**Step 3: Wire equity injection in statements.py**

In `statements.py`, after the equity_raises_per_period loop (around line 158), add:

```python
    # Convertible debt → equity injections
    conversion_per_period = [0.0] * horizon
    if config.assumptions.funding and config.assumptions.funding.debt_facilities:
        for fac in config.assumptions.funding.debt_facilities:
            if fac.converts_to_equity_month is not None and 0 <= fac.converts_to_equity_month < horizon:
                # Amount = balance at conversion month (approximated as draw amount minus any prior repays)
                # More accurately: get from debt_result
                bal_at_conv = debt_result.balance_per_period.get(fac.facility_id, [0.0] * horizon)
                if fac.converts_to_equity_month > 0:
                    conversion_amount = bal_at_conv[fac.converts_to_equity_month - 1]
                else:
                    # Converting at month 0: use the draw amount
                    conversion_amount = sum(
                        d.amount for d in (fac.draw_schedule or []) if d.month == 0
                    )
                conversion_per_period[fac.converts_to_equity_month] += conversion_amount
                equity_raises_per_period[fac.converts_to_equity_month] += conversion_amount
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_convertible_debt.py -v`
Expected: PASS (2 tests)

**Step 5: Run full test suite to verify no regression**

Run: `pytest tests/golden/ tests/unit/ -v --no-header -q`
Expected: All passing

**Step 6: Commit**

```bash
git add shared/fm_shared/model/schemas.py shared/fm_shared/model/debt.py shared/fm_shared/model/statements.py tests/unit/test_convertible_debt.py
git commit -m "feat: convertible debt — debt-to-equity conversion at trigger month (Phase 8c)"
```

---

### Task 8.3: Phase 8 regression — run all golden tests

**Step 1: Run full golden + unit test suite**

Run: `pytest tests/golden/ tests/unit/ -v`
Expected: All PASS. The three new schema fields (`pik_rate`, `grace_period_months`, `converts_to_equity_month`) all have defaults, so existing fixtures and golden files are unaffected.

**Step 2: Commit (only if any fixup needed)**

---

## Phase 9 — Trade Finance (P2)

> Asset-linked facilities (debtor finance, stock finance). Draw capped at
> `advance_rate × asset_value` where asset comes from BS (AR or inventory).
> Depends on Phase 8 being stable since they share the debt schema.

### Task 9.1: Trade finance — test

**Files:**
- Create: `tests/unit/test_trade_finance.py`

**Step 1: Write the failing test**

```python
"""Test trade finance: asset-linked facility capped at advance_rate × asset value."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.model.kpis import calculate_kpis

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "golden"
CONFIG_PATH = GOLDEN_DIR / "debt_config.json"


def _load_config() -> ModelConfig:
    data = json.loads(CONFIG_PATH.read_text())
    return ModelConfig.model_validate(data)


def test_debtor_finance_capped_at_ar_advance() -> None:
    """Trade finance facility: draw capped at 80% of accounts receivable."""
    config = _load_config()
    # Add a trade_finance facility with 80% advance on AR
    from shared.fm_shared.model.schemas import DebtFacility
    tf = DebtFacility(
        facility_id="tf_1",
        label="Debtor Finance",
        type="trade_finance",
        limit=5000000,
        interest_rate=0.09,
        is_cash_plug=True,  # auto-draws to cover shortfalls
        asset_linked="ar",
        advance_rate=0.80,
    )
    config.assumptions.funding.debt_facilities.append(tf)
    # Set minimum_cash to trigger waterfall draws
    config.assumptions.working_capital.minimum_cash = 50000

    ts = run_engine(config)
    stmts = generate_statements(config, ts)

    # Verify the waterfall debt never exceeds 80% of AR
    for t in range(len(stmts.balance_sheet)):
        ar_val = stmts.balance_sheet[t]["accounts_receivable"]
        max_draw = ar_val * 0.80
        # Total waterfall debt includes trade finance draws
        waterfall_debt = stmts.balance_sheet[t].get("waterfall_debt", 0.0)
        # If waterfall_debt > 0, it should be <= max_draw
        if waterfall_debt > 0:
            assert waterfall_debt <= max_draw + 1.0, (
                f"Period {t}: waterfall_debt {waterfall_debt} exceeds "
                f"80% of AR {ar_val} = {max_draw}"
            )
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_trade_finance.py -v`
Expected: FAIL — `trade_finance` not a valid literal for `DebtFacility.type`, and `asset_linked`/`advance_rate` not valid fields

---

### Task 9.2: Trade finance — implement

**Files:**
- Modify: `shared/fm_shared/model/schemas.py:127-136` (extend type Literal, add fields)
- Modify: `shared/fm_shared/model/funding_waterfall.py:13,65-107` (asset-linked cap)

**Step 1: Extend DebtFacility schema**

In `schemas.py`, update `DebtFacility`:

```python
class DebtFacility(BaseModel):
    facility_id: str = Field(...)
    label: str = Field(...)
    type: Literal["term_loan", "revolver", "overdraft", "trade_finance"] = Field(...)
    limit: float = Field(..., ge=0)
    interest_rate: float = Field(..., ge=0, le=1)
    draw_schedule: list[DrawRepayPoint] | None = None
    repayment_schedule: list[DrawRepayPoint] | None = None
    is_cash_plug: bool = False
    pik_rate: float = Field(0.0, ge=0, le=1)
    grace_period_months: int = Field(0, ge=0)
    converts_to_equity_month: int | None = Field(None, ge=0)
    asset_linked: Literal["ar", "inventory"] | None = Field(None, description="Balance sheet asset to link draw limit to")
    advance_rate: float = Field(1.0, ge=0, le=1, description="Fraction of linked asset available as draw limit")
```

**Step 2: Update waterfall to respect asset-linked caps**

In `funding_waterfall.py`, the `apply_funding_waterfall` function needs to accept BS asset values and cap draws for trade_finance facilities.

Update the function signature:

```python
def apply_funding_waterfall(
    closing_cash: list[float],
    facilities: list[DebtFacility],
    minimum_cash: float,
    horizon: int,
    asset_values: dict[str, list[float]] | None = None,  # "ar" -> [...], "inventory" -> [...]
) -> WaterfallResult:
```

In the draw logic, when drawing from a facility with `asset_linked`:

```python
            effective_limit = fac.limit
            if fac.asset_linked and asset_values:
                asset_bal = asset_values.get(fac.asset_linked, [0.0] * horizon)
                effective_limit = min(fac.limit, asset_bal[t] * fac.advance_rate)
            available = max(0.0, effective_limit - bal)
```

Also update `_TYPE_ORDER` to include trade_finance:

```python
_TYPE_ORDER = {"revolver": 0, "trade_finance": 1, "term_loan": 2, "overdraft": 3}
```

**Step 3: Pass asset values from statements.py**

In `statements.py`, where `apply_funding_waterfall` is called (around line 328), pass asset values:

```python
            asset_values = {
                "ar": [bs_list[t]["accounts_receivable"] for t in range(horizon)],
                "inventory": [bs_list[t]["inventory"] for t in range(horizon)],
            }
            waterfall = apply_funding_waterfall(
                closing_cash, plug_facilities, minimum_cash, horizon, asset_values
            )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_trade_finance.py -v`
Expected: PASS

**Step 5: Run full test suite for regression**

Run: `pytest tests/golden/ tests/unit/ -v -q`
Expected: All PASS

**Step 6: Commit**

```bash
git add shared/fm_shared/model/schemas.py shared/fm_shared/model/funding_waterfall.py shared/fm_shared/model/statements.py tests/unit/test_trade_finance.py
git commit -m "feat: trade finance — asset-linked facilities with advance rate cap (Phase 9)"
```

---

## Phase 10 — Granular OpEx Template (P3, Frontend Only)

> No engine changes needed. Uses existing DAG blueprint to model OpEx categories
> as formula nodes. The frontend provides a wizard that generates blueprint nodes.
> This is the lowest priority and simplest phase.

### Task 10.1: OpEx category wizard component

**Files:**
- Create: `apps/web/components/OpExCategoryWizard.tsx`

**Step 1: Create the wizard component**

The wizard lets users define OpEx categories with share percentages and growth rates. On save, it generates the appropriate blueprint nodes and formula entries that get merged into the model config.

```typescript
"use client";

import { useState } from "react";
import { VAButton, VACard, VAInput } from "@/components/ui";

interface OpExCategory {
  name: string;
  share_pct: number;  // 0-100
  growth_rate: number; // annual, e.g. 0.05 = 5%
}

interface Props {
  totalOpex: number;           // base total OpEx from the model
  onGenerate: (nodes: BlueprintNode[], formulas: BlueprintFormula[]) => void;
}

interface BlueprintNode {
  id: string;
  type: "formula";
  ref: string;
  label: string;
}

interface BlueprintFormula {
  output: string;
  expression: string;
  inputs: string[];
}

export function OpExCategoryWizard({ totalOpex, onGenerate }: Props) {
  const [categories, setCategories] = useState<OpExCategory[]>([
    { name: "Personnel", share_pct: 40, growth_rate: 0.05 },
    { name: "Facilities", share_pct: 20, growth_rate: 0.03 },
    { name: "Admin", share_pct: 15, growth_rate: 0.02 },
    { name: "Sales & Marketing", share_pct: 15, growth_rate: 0.04 },
    { name: "Other", share_pct: 10, growth_rate: 0.02 },
  ]);

  const totalShare = categories.reduce((s, c) => s + c.share_pct, 0);

  function handleGenerate() {
    const nodes: BlueprintNode[] = [];
    const formulas: BlueprintFormula[] = [];

    for (const cat of categories) {
      const id = `opex_${cat.name.toLowerCase().replace(/[^a-z0-9]/g, "_")}`;
      nodes.push({
        id,
        type: "formula",
        ref: id,
        label: `OpEx: ${cat.name}`,
      });
      // Formula: total_opex * share_pct * (1 + growth_rate) ^ (t/12)
      // Simplified for constant driver: total_opex * share_pct / 100
      formulas.push({
        output: id,
        expression: `total_opex * ${cat.share_pct / 100} * (1 + ${cat.growth_rate})`,
        inputs: ["total_opex"],
      });
    }

    onGenerate(nodes, formulas);
  }

  // ... render form with category rows, add/remove, generate button
  // Follow existing VA patterns: VACard container, VAInput for each field,
  // VAButton for actions, Tailwind grid layout
}
```

This is a convenience UI that generates blueprint configuration — no engine changes required.

**Step 2: Build and verify**

Run: `cd apps/web && npx next build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add apps/web/components/OpExCategoryWizard.tsx
git commit -m "feat: OpEx category allocation wizard — frontend template (Phase 10)"
```

---

## Summary

| Phase | Tasks | Files Created | Files Modified | Tests Added |
|-------|-------|--------------|----------------|-------------|
| 7 | 7.1-7.5 | `sensitivity.py`, `test_sensitivity.py` | `runs.py`, `api.ts`, sensitivity `page.tsx` | 3+ |
| 8a | 8a.1-8a.2 | `test_pik_interest.py` | `schemas.py`, `debt.py` | 2 |
| 8b | 8b.1-8b.2 | `test_grace_periods.py` | `schemas.py`, `debt.py` | 1 |
| 8c | 8c.1-8c.2 | `test_convertible_debt.py` | `schemas.py`, `debt.py`, `statements.py` | 2 |
| 9 | 9.1-9.2 | `test_trade_finance.py` | `schemas.py`, `funding_waterfall.py`, `statements.py` | 1 |
| 10 | 10.1 | `OpExCategoryWizard.tsx` | — | 0 (UI only) |

**Total:** ~12 commits, ~9 new test functions, 4 new files, 6 modified files.

**Run order:** 7 → 8a/8b/8c (parallel) → 9 → 10

**Test commands:**
- Unit tests: `pytest tests/unit/ -v`
- Golden tests: `pytest tests/golden/ -v`
- Full suite: `pytest tests/ -v`
- Frontend build: `cd apps/web && npx next build`
