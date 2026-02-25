# Phase 5 — Consolidation Integration Validation

> **CRITICAL SCOPE RULE — READ THIS FIRST**
>
> You may ONLY create or modify the **2 files** listed in the Scope table
> below. Do NOT touch ANY other file in the repository. Do NOT create
> helper modules, utility files, shared fixtures, or any file not listed.
> Do NOT refactor, lint, type-annotate, add docstrings to, or "improve"
> files outside scope. If you feel the urge to edit another file, STOP —
> the task does not require it.
>
> **HARD BLOCKLIST — do NOT open, read for editing, or modify:**
> - Any file under `app/`, `frontend/`, `web/`, `infra/`, `deploy/`
> - `shared/fm_shared/model/statements.py`
> - `shared/fm_shared/model/engine.py`
> - `shared/fm_shared/model/schemas.py`
> - `shared/fm_shared/model/graph.py`
> - `shared/fm_shared/model/evaluator.py`
> - `shared/fm_shared/model/debt.py`
> - `shared/fm_shared/model/funding_waterfall.py`
> - `shared/fm_shared/model/kpis.py`
> - `shared/fm_shared/analysis/monte_carlo.py`
> - `shared/fm_shared/analysis/distributions.py`
> - `tests/conftest.py`
> - `tests/unit/*.py`
> - `tests/golden/test_debt_golden.py`
> - `tests/golden/test_waterfall_golden.py`
> - `tests/golden/test_manufacturing_golden.py`
> - `pyproject.toml`, `requirements*.txt`, `Dockerfile*`, `*.toml`, `*.cfg`
> - Any CI/CD, config, or migration file
>
> **Do NOT create a git worktree.**

## Goal

Create an integration test that exercises the consolidation engine
(`shared/fm_shared/analysis/consolidation.py`) against a realistic
multi-entity scenario matching Digital Genius's org structure. Fix any
bugs found during the process.

## Context

The consolidation module already supports:
- FX translation (avg rate for IS/CF, closing rate for BS) with CTA
- Full, proportional, and equity-method consolidation
- NCI share of profit (IS) and equity (BS)
- Intercompany eliminations (management_fee, royalty, trade, dividend, loan)

However it has **never been tested end-to-end** with our engine +
three-statement generator. This phase wires the pieces together and
validates correctness.

## Architecture

```
Holding (USD)  ──80%──▶  Sub A (GBP)   management_fee Sub A → Holding
               ──100%──▶ Sub B (KES)   loan Holding → Sub B
```

Each entity is a standalone ModelConfig run through `run_engine` →
`generate_statements`, then the three sets of statements are fed into
`consolidation.consolidate()`.

## Scope — ONLY touch these files

| # | File | Action |
|---|------|--------|
| 1 | `tests/golden/test_consolidation_dg_parity.py` | **CREATE** — integration test |
| 2 | `shared/fm_shared/analysis/consolidation.py` | **FIX** bugs found during integration |

Do NOT modify any other files. Do NOT create a git worktree.
Do NOT modify `statements.py`, `engine.py`, `schemas.py`, `conftest.py`,
or any frontend files.

## Detailed Requirements

### 1. Test fixture — three entity configs

Build three `ModelConfig` dicts in the test file (do NOT use JSON fixture
files — inline the dicts for readability).

**Holding Company (USD)**
- `entity_name`: "Holding Co"
- `currency`: "USD"
- `horizon_months`: 12
- `tax_rate`: 0.25
- `initial_cash`: 200_000
- `initial_equity`: 500_000
- Revenue: 1 stream, unit_sale, 200 units @ $50 = $10,000/month
- No costs, no capex, no debt
- Blueprint: 2 driver nodes (units, price) → 1 output node (revenue)
  with formula `units * price`

**Sub A (GBP, 80% owned)**
- `entity_name`: "Sub A"
- `currency`: "GBP"
- `horizon_months`: 12
- `tax_rate`: 0.20
- `initial_cash`: 50_000
- `initial_equity`: 100_000
- Revenue: 1 stream, unit_sale, 100 units @ £30 = £3,000/month
- Fixed cost: 1 item, category "sga", drv:sga_cost = £500/month
- No capex, no debt
- Blueprint: 3 driver nodes (units, price, sga_cost) → 1 output node
  (revenue) with formula `units * price`

**Sub B (KES, 100% owned)**
- `entity_name`: "Sub B"
- `currency`: "KES"
- `horizon_months`: 12
- `tax_rate`: 0.30
- `initial_cash`: 1_000_000
- `initial_equity`: 5_000_000
- Revenue: 1 stream, unit_sale, 500 units @ KES 200 = KES 100,000/month
- Fixed cost: 1 item, category "cogs", drv:cogs = KES 20,000/month
- **Funding**: 1 revolver `is_cash_plug: true`, limit 2,000,000 KES,
  interest_rate 0.15. Sub B's initial_cash is low enough that the
  waterfall should trigger draws.
  Actually, set `initial_cash: 10_000` and `initial_equity: 5_000_000` so
  working capital needs force the waterfall to inject cash.
- Blueprint: 3 driver nodes (units, price, cogs) → 1 output (revenue)
  with formula `units * price`

Use the same boilerplate structure as `tests/conftest.py:minimal_model_config_dict`
for fields like `artifact_type`, `artifact_version`, `tenant_id`, etc.

### 2. FX rates

```python
FX_AVG = {
    ("GBP", "USD"): 1.27,
    ("KES", "USD"): 0.0077,
}
FX_CLOSING = {
    ("GBP", "USD"): 1.25,
    ("KES", "USD"): 0.0077,
}
```

### 3. Intercompany links

```python
IC_LINKS = [
    {
        "from_entity_id": "sub_a",
        "to_entity_id": "holding",
        "link_type": "management_fee",
        "amount_or_rate": 500.0,      # £500/month
        "frequency": "monthly",
        "withholding_tax_applicable": False,
    },
    {
        "from_entity_id": "holding",
        "to_entity_id": "sub_b",
        "link_type": "loan",
        "amount_or_rate": 0.08,        # 8% interest rate
        "frequency": "annual",
        "withholding_tax_applicable": False,
    },
]
```

### 4. Wiring: standalone → consolidation

```python
from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.model.statements import Statements
from shared.fm_shared.analysis.consolidation import (
    EntityResult,
    IntercompanyElimination,
    consolidate,
    compute_intercompany_amounts,
)
```

For each entity:
1. `config = ModelConfig.model_validate(entity_dict)`
2. `ts = run_engine(config)`
3. `stmts = generate_statements(config, ts)`

Then convert `Statements` → the dict format `consolidation.py` expects.
The consolidation module's `_get_period_values` (line 48) handles two
formats:
- **list of row-dicts**: `[{"label": "revenue", "period_0": 1000, ...}]`
- **dict of label→list**: `{"revenue": [1000, 1000, ...]}`

Our `Statements` dataclass has `income_statement`, `balance_sheet`,
`cash_flow` as `list[dict[str, Any]]` where keys are line names (e.g.
`revenue`, `cogs`, `gross_profit`). This is the **dict-per-period** format,
NOT the label→list format that `_get_period_values` expects.

**Important**: You need to convert from our format:
```python
# Our format: list of period-dicts
# [{"revenue": 1000, "cogs": 0, ...}, {"revenue": 1000, ...}]

# consolidation.py expects either:
# A) list of {"label": X, "period_0": v0, "period_1": v1, ...}
# B) dict of {"revenue": [v0, v1, ...], "cogs": [v0, v1, ...]}
```

Write a helper `_statements_to_consolidation_format(stmts: Statements, horizon: int) -> dict`:
```python
def _statements_to_consolidation_format(stmts: Statements, horizon: int) -> dict:
    """Convert Statements (list of period-dicts) to consolidation format (label→list)."""
    def _convert(period_dicts: list[dict]) -> dict[str, list[float]]:
        if not period_dicts:
            return {}
        keys = [k for k in period_dicts[0].keys() if isinstance(period_dicts[0][k], (int, float))]
        return {k: [float(period_dicts[t].get(k, 0.0)) for t in range(len(period_dicts))] for k in keys}
    return {
        "income_statement": _convert(stmts.income_statement),
        "balance_sheet": _convert(stmts.balance_sheet),
        "cash_flow": _convert(stmts.cash_flow),
    }
```

Build `EntityResult` objects:
```python
EntityResult(
    entity_id="holding",
    currency="USD",
    statements=_statements_to_consolidation_format(holding_stmts, 12),
    kpis={},
    ownership_pct=100.0,
    consolidation_method="full",
)
```
Sub A: `ownership_pct=80.0`, Sub B: `ownership_pct=100.0`.
All three use `consolidation_method="full"`.

### 5. Test assertions

Write these test functions:

**`test_standalone_holding_revenue`**
- Holding revenue = 200 * 50 = $10,000/month for all 12 periods
- `assert stmts.income_statement[t]["revenue"] == 10_000.0`

**`test_standalone_sub_a_revenue`**
- Sub A revenue = 100 * 30 = £3,000/month
- Sub A has £500 SGA cost → gross_profit = £3,000, opex = £500

**`test_standalone_sub_b_waterfall_triggers`**
- Sub B: initial_cash=10,000 but WC needs should force waterfall draws
- `assert any(row.get("debt_draws", 0) > 0 or row.get("financing", 0) > 0 for row in stmts.cash_flow)`
- BS balances every period: `abs(row["total_assets"] - row["total_liabilities_equity"]) < 0.02`

**`test_consolidated_is_eliminates_ic_revenue`**
- After consolidation with `eliminate_intercompany=True`:
- Consolidated IS should have "Intercompany revenue" and "Intercompany expense"
  lines that reduce the total (net effect on consolidated revenue is negative
  of the elimination amount)

**`test_consolidated_nci_sub_a`**
- NCI = 20% of Sub A's net income (translated at avg GBP/USD rate)
- `consolidated.minority_interest["nci_profit"]` should have non-zero values
- NCI profit per period ≈ 20% × Sub_A_NI × 1.27

**`test_consolidated_bs_ic_loan_eliminated`**
- "Intercompany loan receivable" and "Intercompany loan payable" lines
  should both be present and negative (eliminating the loan)
- Also: "Intercompany interest income" and "Intercompany interest expense"

**`test_fx_translation_is_at_avg_bs_at_closing`**
- Sub A (GBP): IS revenue translated at 1.27, BS cash at 1.25
- Validate by comparing raw GBP values × rate against translated values

**`test_consolidated_integrity_no_errors`**
- `consolidated.integrity["errors"]` should be empty
- Warnings about period mismatch should NOT appear (all entities are 12mo)

**`test_cta_present_for_foreign_subs`**
- The translated statements for Sub A and Sub B should have
  `translation_reserve` (CTA) calculated

### 6. Bug fixes in consolidation.py

When wiring things together, you will likely hit these issues:

**A. `_get_period_values` dict branch (line 74-79)**
The dict branch checks `len(arr) >= horizon` which fails if the value
lists have exactly `horizon` elements (should be `>=`). This is actually
fine (>= is correct). But the dict branch requires values to be lists —
our converted format should work.

**B. NCI line matching (lines 240-252)**
The NCI code searches for a line containing "net" AND "income" in lower
case. Our Statements uses key `net_income` — so the search for
`"net" in k.lower() and "income" in k.lower()` should match `net_income`.
Verify this works.

**C. Equity line matching (lines 248-252)**
Searches for `"equity" in k.lower()`. Our Statements uses `total_equity`
which contains "equity" — should match.

If any of these don't work with our dict-format statements, fix the
matching logic in `consolidation.py`.

## Test file template

```python
"""Integration test: consolidation engine with multi-entity DG parity scenario."""

from __future__ import annotations

import pytest

from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.model.statements import Statements
from shared.fm_shared.analysis.consolidation import (
    EntityResult,
    consolidate,
    compute_intercompany_amounts,
)

HORIZON = 12
FLOAT_TOL = 0.02

# --- FX rates ---
FX_AVG = {("GBP", "USD"): 1.27, ("KES", "USD"): 0.0077}
FX_CLOSING = {("GBP", "USD"): 1.25, ("KES", "USD"): 0.0077}

# --- Entity config builders (inline, no JSON files) ---
# ... _holding_config_dict(), _sub_a_config_dict(), _sub_b_config_dict() ...

# --- Conversion helper ---
# ... _statements_to_consolidation_format() ...

# --- Fixtures ---
@pytest.fixture(scope="module")
def holding_stmts() -> Statements: ...

@pytest.fixture(scope="module")
def sub_a_stmts() -> Statements: ...

@pytest.fixture(scope="module")
def sub_b_stmts() -> Statements: ...

@pytest.fixture(scope="module")
def consolidated(holding_stmts, sub_a_stmts, sub_b_stmts): ...

# --- Tests ---
# ...
```

## Verification

After implementation, run:
```bash
python -m pytest tests/golden/test_consolidation_dg_parity.py -v
```

All tests must pass. If a test fails because of a bug in
`consolidation.py`, fix the bug and document what changed.

## Constraints (re-stated for emphasis)

- **ONLY 2 files in scope** — see the Scope table above. Every other
  file in the repo is OFF LIMITS.
- Do NOT create a git worktree.
- Do NOT modify `statements.py`, `engine.py`, `schemas.py`, `conftest.py`,
  `kpis.py`, `debt.py`, `funding_waterfall.py`, or any existing test file.
- Do NOT touch frontend, infra, CI/CD, Docker, or config files.
- Do NOT add new dependencies to `pyproject.toml`.
- Do NOT create new shared modules, utility files, or JSON fixture files.
- Keep ALL fixture data inline in the test file.
- Use `pytest.fixture(scope="module")` to avoid re-running engine per test.
- If you find yourself wanting to change a file not in scope, STOP.
  The correct approach is to work within the 2 in-scope files only.
