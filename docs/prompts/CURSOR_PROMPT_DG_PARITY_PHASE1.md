# Cursor Prompt — DG Parity Phase 1: Debt & Interest Calculation

> **Context:** Design doc at `docs/plans/2026-02-24-dg-parity-design.md` (commit c3c1c18).
> 329 backend tests pass, 45 frontend, 20 E2E. All green on main.
> This is Phase 1 of 6 to close the feature gap between Virtual Analyst and Digital Genius.

---

## Context Update

### What exists today

- **`shared/fm_shared/model/statements.py`** — Three-statement generator (IS, BS, CF).
  Lines 112-113 hardcode `interest = [0.0] * horizon`. The BS cash line is a plug
  (line 181: `cash_plug = total_liab + total_equity - total_assets_ex_cash`).
  CF financing is also a plug (line 212: `financing = closing - opening - operating - investing`).
  Total liabilities = only AP today (line 179).

- **`shared/fm_shared/model/schemas.py`** — Pydantic v2 schemas.
  `DebtFacility` (lines 130-138) has facility_id, label, type (term_loan|revolver|overdraft),
  limit, interest_rate, draw_schedule, repayment_schedule, is_cash_plug. `DrawRepayPoint`
  (lines 125-127) has month + amount. `DividendsPolicy` (141-143), `EquityRaise`,
  `Funding` (146-149) all exist. `Assumptions.funding` (line 158) is `Funding | None = None`.
  **None of the funding schemas are wired into the engine.**

- **`shared/fm_shared/model/kpis.py`** — KPI calculator.
  Lines 40-48 stub `total_debt = 0.0`, `debt_equity = None`, `dscr = None`.
  These need to read actual debt balances once available.

- **`shared/fm_shared/model/engine.py`** — DAG calculation engine.
  `run_engine()` returns `dict[str, list[float]]` keyed by node_id.
  Uses safe AST expression evaluator, no eval().

- **`tests/conftest.py`** — `minimal_model_config()` / `minimal_model_config_dict()`
  helpers build a minimal `model_config_v1` with a single unit_sale revenue stream.
  These can be extended with a `funding` key for debt test fixtures.

- **`tests/golden/test_manufacturing_golden.py`** — Existing golden test pattern.
  Loads config JSON, runs engine + statements + kpis, compares to golden JSON files
  with float tolerance of 0.01.

### What's missing (Phase 1 scope)

1. No debt schedule calculation — interest hardcoded to 0
2. No debt balances on the balance sheet (no debt_current, debt_non_current)
3. No debt draws/repayments on the cash flow statement
4. KPI debt_equity and DSCR permanently return None
5. Total liabilities only counts AP, ignores debt

---

## Task: Implement Debt & Interest Calculation

### Step 1 — Create `shared/fm_shared/model/debt.py`

Create a new module with:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from shared.fm_shared.model.schemas import DebtFacility


@dataclass
class DebtScheduleResult:
    balance_per_period: dict[str, list[float]]  # facility_id -> [balance_t0..tn]
    interest_per_period: list[float]             # total interest per period
    draws_per_period: list[float]                # total draws per period
    repayments_per_period: list[float]           # total repayments per period
    current_debt_per_period: list[float]         # maturing within 12 months
    non_current_debt_per_period: list[float]     # long-term portion


def empty_debt_result(horizon: int) -> DebtScheduleResult:
    """Return a zero-filled result when no debt facilities exist."""
    return DebtScheduleResult(
        balance_per_period={},
        interest_per_period=[0.0] * horizon,
        draws_per_period=[0.0] * horizon,
        repayments_per_period=[0.0] * horizon,
        current_debt_per_period=[0.0] * horizon,
        non_current_debt_per_period=[0.0] * horizon,
    )


def calculate_debt_schedule(
    facilities: list[DebtFacility],
    horizon: int,
) -> DebtScheduleResult:
    """
    Calculate debt balances, interest, draws, and repayments for each period.

    For each facility per period t:
    - draws[t] = sum of draw_schedule amounts at month t
    - repays[t] = sum of repayment_schedule amounts at month t
    - balance[t] = balance[t-1] + draws[t] - repays[t], clamped to [0, limit]
    - interest[t] = balance[t] * interest_rate / 12

    Current vs non-current split:
    - Sum of repayments due within the next 12 months = current portion
    - Remainder = non-current portion
    """
```

**Algorithm details:**
- Process each facility independently, accumulating into the result arrays
- Balance starts at 0 and is clamped: `max(0, min(limit, balance))`
- Interest = `balance[t] * interest_rate / 12` (simple monthly interest on closing balance)
- Current debt: for each facility, sum repayments due in months `[t+1, t+12]`. If that sum exceeds the balance, cap at balance. The non-current portion = balance - current.
- Skip facilities where `is_cash_plug=True` (those are handled in Phase 2 funding waterfall)

### Step 2 — Wire debt into `statements.py`

Replace lines 112-113 (`interest = [0.0] * horizon`) with:

```python
from shared.fm_shared.model.debt import calculate_debt_schedule, empty_debt_result

debt_result = empty_debt_result(horizon)
if config.assumptions.funding and config.assumptions.funding.debt_facilities:
    non_plug = [f for f in config.assumptions.funding.debt_facilities if not f.is_cash_plug]
    if non_plug:
        debt_result = calculate_debt_schedule(non_plug, horizon)

interest = debt_result.interest_per_period
```

**Balance sheet changes** (modify the BS loop starting at line 174):

Add these lines to the BS dict (after `accounts_payable`):

```python
"debt_current": debt_result.current_debt_per_period[t],
"debt_non_current": debt_result.non_current_debt_per_period[t],
```

Update `total_liab` calculation (currently line 179):

```python
total_liab = ap[t] + debt_result.current_debt_per_period[t] + debt_result.non_current_debt_per_period[t]
```

Also add `total_current_liabilities` to the BS dict:

```python
"total_current_liabilities": ap[t] + debt_result.current_debt_per_period[t],
```

**Cash flow changes** (modify the CF loop starting at line 202):

Replace the financing plug with explicit debt items. After `investing`:

```python
debt_draws = debt_result.draws_per_period[t]
debt_repayments = debt_result.repayments_per_period[t]
```

Add these to the CF dict:

```python
"debt_draws": debt_draws,
"debt_repayments": debt_repayments,
```

Keep the financing plug intact (it still includes the cash-balancing residual):

```python
financing = closing - opening_cash[t] - operating - investing
```

**Important:** The existing cash plug mechanism (BS cash = total_liab + total_equity - total_assets_ex_cash)
and CF financing plug naturally absorb the debt flows because debt changes total_liab and interest
flows through net_income → retained earnings → total_equity. The three statements will still balance.

### Step 3 — Update KPIs (`kpis.py`)

Replace lines 40-48 with:

```python
debt_current = bs_list[t].get("debt_current", 0.0)
debt_non_current = bs_list[t].get("debt_non_current", 0.0)
total_debt = debt_current + debt_non_current
total_equity = bs_list[t]["total_equity"]
debt_equity = (total_debt / total_equity) if (total_equity and total_debt) else None

interest = is_list[t]["interest_expense"]
# For principal, use debt_repayments from CF if available
principal = cf_list[t].get("debt_repayments", 0.0)
debt_service = interest + principal
dscr = (ebitda / debt_service) if debt_service else None
```

### Step 4 — Write tests

#### 4a: Unit tests for `debt.py` — new file `tests/unit/test_debt.py`

Write 8-10 tests covering:

1. **Empty facilities** → returns zero-filled result (same as `empty_debt_result`)
2. **Single term loan** — $1M limit, 8% annual rate, draw $500K at month 0, repay $50K/month starting month 3
   - Verify balance trajectory: 500K, 500K, 500K, 450K, 400K, ...
   - Verify interest: 500000 * 0.08 / 12 = 3333.33 for months 0-2
3. **Multiple facilities** — two facilities, verify totals sum correctly
4. **Balance clamped at 0** — repayment exceeds balance → balance = 0, not negative
5. **Balance clamped at limit** — draws exceeding limit are capped
6. **Cash-plug facilities are skipped** — pass a facility with `is_cash_plug=True`, verify it's excluded
7. **Current vs non-current split** — term loan with known repayment schedule, verify current = next-12-month repayments
8. **Interest calculation accuracy** — verify monthly interest = balance * rate / 12

Use `DebtFacility` and `DrawRepayPoint` from `shared.fm_shared.model.schemas` to build test fixtures.
Create helpers as needed (e.g., `_make_facility()`).

#### 4b: Update existing statement tests — `tests/unit/test_statements.py`

Add tests:

1. **Statements with debt facilities** — extend `minimal_model_config_dict` with a `funding` key containing
   one term loan. Verify IS `interest_expense > 0`, BS has `debt_current` and `debt_non_current`,
   CF has `debt_draws` and `debt_repayments`, and BS still balances.
2. **No funding config** — verify backward compatibility (existing tests should still pass as-is)

#### 4c: Golden test — new file `tests/golden/test_debt_golden.py`

Create a golden test following the pattern in `tests/golden/test_manufacturing_golden.py`:

1. Create `tests/golden/debt_config.json` — a model config with 2 debt facilities:
   - Term loan: $1,000,000 limit, 8% rate, drawn $800K at month 0, repay $66,667/month starting month 1
   - Revolver: $500,000 limit, 6% rate, drawn $200K at month 3, repay $100K at months 8 and 9
2. Run engine → statements → kpis
3. Save the output as `tests/golden/debt_base_statements.json` and `tests/golden/debt_base_kpis.json`
4. Write comparison tests that verify the golden files match

**Golden file creation workflow:**
- First write the config JSON
- Then write a one-off script or test that generates the golden files
- Then write the comparison test

### Step 5 — Verify everything

1. Run `pytest tests/unit/test_debt.py -v` — all new unit tests pass
2. Run `pytest tests/unit/test_statements.py -v` — existing + new tests pass
3. Run `pytest tests/golden/ -v` — all golden tests pass (including existing manufacturing)
4. Run `pytest tests/ -v` — full suite passes, no regressions
5. Verify BS balance: `total_assets == total_liabilities_equity` for every period in every test

---

## Constraints

- Do NOT modify any existing schemas in `schemas.py` — the `DebtFacility`, `DrawRepayPoint`, `Funding`, and `Assumptions` schemas already have everything needed
- Do NOT implement funding waterfall, dividends, or equity raises — those are Phase 2
- Do NOT modify `engine.py` — debt calculation is post-engine, in the statement generator
- Do NOT break existing tests — all 329 backend tests must continue to pass
- Keep `is_cash_plug` facilities out of this phase — filter them out in `calculate_debt_schedule`

---

## Files to create

| File | Purpose |
|------|---------|
| `shared/fm_shared/model/debt.py` | Debt schedule calculator |
| `tests/unit/test_debt.py` | Unit tests for debt module |
| `tests/golden/test_debt_golden.py` | Golden comparison test |
| `tests/golden/debt_config.json` | Golden test model config |
| `tests/golden/debt_base_statements.json` | Golden expected statements |
| `tests/golden/debt_base_kpis.json` | Golden expected KPIs |

## Files to modify

| File | Change |
|------|--------|
| `shared/fm_shared/model/statements.py` | Wire debt_result, add BS debt lines, update total_liab |
| `shared/fm_shared/model/kpis.py` | Read actual debt from BS, compute debt_equity & DSCR |

## Commit

Single commit: `DG-P1: debt schedule calculation — interest, BS debt lines, KPI debt_equity & DSCR`
