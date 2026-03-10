# Deferred Code Review Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the 5 deferred suggestions from the CE-Africa parity code review to improve correctness, test quality, and robustness.

**Architecture:** Each fix is isolated — no dependencies between tasks. All fixes target existing files with minimal changes. TDD approach: write failing test first, then fix the code.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, TypeScript/React (Next.js)

---

## Items

| # | Review ID | Description |
|---|-----------|-------------|
| 1 | S1 | OpEx wizard growth formula missing `^t` exponent — produces flat projections |
| 2 | S4 | Sensitivity test uses deferred imports — move to module level |
| 3 | S5 | Trade finance test lacks direct AR cap assertion |
| 4 | S7 | Duplicate OpEx category names generate conflicting node IDs |
| 5 | S2 | Document that sensitivity engine is sequential (no parallelism needed yet) |

---

### Task 1: Fix OpEx Growth Formula (S1)

The formula `total_opex * share * (1 + growth_rate)` is a constant — it doesn't compound over time. It should be `total_opex * share * (1 + growth_rate)^t` where `t` is the period index.

**Files:**
- Modify: `apps/web/components/OpExCategoryWizard.tsx:72-74`

**Step 1: Update the expression to include `^t` exponent**

In `apps/web/components/OpExCategoryWizard.tsx`, line 73, change:

```typescript
// FROM:
expression: `total_opex * ${cat.share_pct / 100} * (1 + ${cat.growth_rate})`,

// TO:
expression: `total_opex * ${cat.share_pct / 100} * (1 + ${cat.growth_rate}) ^ t`,
```

The `t` variable is the period index, resolved by the blueprint evaluator at runtime.

**Step 2: Verify frontend builds**

Run: `cd apps/web && npx next build`
Expected: Build succeeds with no errors.

**Step 3: Commit**

```bash
git add apps/web/components/OpExCategoryWizard.tsx
git commit -m "fix(opex-wizard): add ^t exponent to growth formula for compounding"
```

---

### Task 2: Move Sensitivity Test Imports to Module Level (S4)

The test file `tests/unit/test_sensitivity.py` uses deferred (in-function) imports. These should be at the top of the file for clarity and standard practice.

**Files:**
- Modify: `tests/unit/test_sensitivity.py:1-88`

**Step 1: Refactor imports to module level**

Replace the entire file content. Move the `from shared.fm_shared.analysis.sensitivity import ...` statements to the top, alongside the other imports:

```python
"""Unit tests for sensitivity sweep and heat map."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.fm_shared.analysis.sensitivity import (
    HeatMapResult,
    SensitivityResult,
    run_heatmap,
    run_sensitivity,
)
from shared.fm_shared.model import ModelConfig

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "golden"
CONFIG_PATH = GOLDEN_DIR / "debt_config.json"


def _load_config() -> ModelConfig:
    data = json.loads(CONFIG_PATH.read_text())
    return ModelConfig.model_validate(data)


def test_sensitivity_tax_rate_sweep_monotonic() -> None:
    """Sweeping tax_rate 0.15->0.35 should monotonically decrease net_income."""
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
    # Higher tax -> lower net income: monotonic decrease
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


def test_heatmap_tax_rate_vs_initial_cash() -> None:
    """2D sweep: tax_rate x initial_cash -> net_income matrix."""
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
    # Higher tax -> lower net income (rows correspond to increasing tax_rate)
    for i in range(1, len(result.matrix)):
        assert result.matrix[i][0] <= result.matrix[i - 1][0], (
            f"Expected row {i} (tax={result.values_a[i]}) <= row {i-1} (tax={result.values_a[i-1]})"
        )
```

**Step 2: Run tests to verify no regressions**

Run: `pytest tests/unit/test_sensitivity.py -v`
Expected: All 3 tests PASS.

**Step 3: Commit**

```bash
git add tests/unit/test_sensitivity.py
git commit -m "refactor(tests): move sensitivity imports to module level"
```

---

### Task 3: Add Direct AR Cap Assertion to Trade Finance Test (S5)

The test `test_debtor_finance_capped_at_ar_advance` only checks that the model runs and BS balances. It should directly assert that the trade finance facility draw never exceeds `advance_rate * AR`.

**Files:**
- Modify: `tests/unit/test_trade_finance.py:39-72`

**Step 1: Write the stronger assertion test**

Replace `test_debtor_finance_capped_at_ar_advance` with a version that inspects the waterfall result directly:

```python
def test_debtor_finance_capped_at_ar_advance() -> None:
    """Trade finance with is_cash_plug: waterfall draw capped at 80% of AR."""
    config = _load_config()
    # Keep existing non-plug term loan, add trade finance as cash plug
    tf = DebtFacility(
        facility_id="tf_1",
        label="Debtor Finance",
        type="trade_finance",
        limit=5000000,
        interest_rate=0.09,
        is_cash_plug=True,
        asset_linked="ar",
        advance_rate=0.80,
    )
    config.assumptions.funding.debt_facilities.append(tf)
    config.assumptions.working_capital.minimum_cash = 50000.0

    ts = run_engine(config)
    stmts = generate_statements(config, ts)

    # BS should balance every period
    for t in range(config.metadata.horizon_months):
        bs = stmts.balance_sheet[t]
        assert bs["total_assets"] == pytest.approx(
            bs["total_liabilities_equity"], abs=1.0
        ), f"BS imbalance at period {t}"

    # Direct AR cap assertion: waterfall debt from tf_1 must never exceed 80% of AR
    for t in range(config.metadata.horizon_months):
        bs = stmts.balance_sheet[t]
        ar_value = bs.get("accounts_receivable", 0.0)
        max_draw = ar_value * 0.80
        # The total plug-facility debt includes tf_1; check it's within AR cap
        # Since tf_1 is the only asset-linked facility, its balance <= max_draw
        waterfall_debt = bs.get("waterfall_debt", 0.0)
        assert waterfall_debt <= max_draw + 1.0, (
            f"Period {t}: waterfall debt {waterfall_debt:.0f} exceeds "
            f"80% of AR {ar_value:.0f} (cap={max_draw:.0f})"
        )
```

**Step 2: Run the test to verify it passes**

Run: `pytest tests/unit/test_trade_finance.py -v`
Expected: Both tests PASS. If the `waterfall_debt` key doesn't exist in BS, the test gracefully defaults to 0.0 and passes.

**Step 3: If `waterfall_debt` is not a BS key, check what key the waterfall balance is stored under**

Run: `pytest tests/unit/test_trade_finance.py::test_debtor_finance_capped_at_ar_advance -v`

If the assertion doesn't meaningfully exercise the cap (because `waterfall_debt` defaults to 0), inspect BS keys by temporarily adding a print. The key is likely in `stmts.balance_sheet[t]`. Check `apps/api/app/routers/runs.py` or `shared/fm_shared/model/statements.py` to find the right key name. Adjust the assertion to use the correct key.

**Step 4: Commit**

```bash
git add tests/unit/test_trade_finance.py
git commit -m "test(trade-finance): add direct AR cap assertion for waterfall debt"
```

---

### Task 4: Handle Duplicate OpEx Category Names (S7)

If a user enters two categories with the same name (e.g., "Admin" twice), `toNodeId` produces the same ID for both, creating conflicting blueprint nodes. Add deduplication.

**Files:**
- Modify: `apps/web/components/OpExCategoryWizard.tsx:38-39,64-79`

**Step 1: Add deduplication logic to `handleGenerate`**

In `apps/web/components/OpExCategoryWizard.tsx`, replace the `handleGenerate` function (lines 64-79) with a version that appends a suffix when duplicate IDs are detected:

```typescript
function handleGenerate() {
    const nodes: BlueprintNode[] = [];
    const formulas: BlueprintFormula[] = [];
    const usedIds = new Set<string>();

    for (const cat of categories) {
      let id = toNodeId(cat.name);
      // Deduplicate: append _2, _3, etc. if ID already used
      if (usedIds.has(id)) {
        let suffix = 2;
        while (usedIds.has(`${id}_${suffix}`)) suffix++;
        id = `${id}_${suffix}`;
      }
      usedIds.add(id);

      nodes.push({ id, type: "formula", ref: id, label: `OpEx: ${cat.name}` });
      formulas.push({
        output: id,
        expression: `total_opex * ${cat.share_pct / 100} * (1 + ${cat.growth_rate}) ^ t`,
        inputs: ["total_opex"],
      });
    }

    onGenerate(nodes, formulas);
  }
```

Note: This also includes the `^t` fix from Task 1, so if Task 1 was already committed, the expression here must match.

**Step 2: Verify frontend builds**

Run: `cd apps/web && npx next build`
Expected: Build succeeds.

**Step 3: Commit**

```bash
git add apps/web/components/OpExCategoryWizard.tsx
git commit -m "fix(opex-wizard): deduplicate node IDs when category names collide"
```

---

### Task 5: Run Full Test Suite and Final Verification

**Step 1: Run all Python tests**

Run: `pytest tests/unit/ tests/golden/ -v --tb=short`
Expected: All 390+ tests PASS.

**Step 2: Run frontend build**

Run: `cd apps/web && npx next build`
Expected: Build succeeds.

**Step 3: Push all commits**

```bash
git push
```
