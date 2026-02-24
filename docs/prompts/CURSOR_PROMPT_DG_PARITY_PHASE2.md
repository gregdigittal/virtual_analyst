# Cursor Prompt — DG Parity Phase 2: Dividends, Equity Raises & Funding Waterfall

> **Context:** Phase 1 complete (commit 64abc01). 364 backend tests pass, 0 fail.
> Design doc at `docs/plans/2026-02-24-dg-parity-design.md`.
> This is Phase 2 of 6 to close the feature gap between Virtual Analyst and Digital Genius.

> **CRITICAL — Worktree warning:** Do NOT create a git worktree. Work in the current
> project directory. Do NOT modify any files outside the scope listed below.

---

## Context Update

### What exists after Phase 1

- **`shared/fm_shared/model/debt.py`** — `DebtScheduleResult` and `calculate_debt_schedule()`.
  Handles non-cash-plug facilities. Cash-plug facilities (`is_cash_plug=True`) are filtered out.

- **`shared/fm_shared/model/statements.py`** — Three-statement generator.
  - Lines 113-121: Calls `calculate_debt_schedule()` for non-plug facilities, sets `interest`.
  - Lines 187-191: `total_liab = ap + debt_current + debt_non_current`.
  - Lines 206-209: BS includes `debt_current`, `debt_non_current`, `total_current_liabilities`.
  - Lines 227-228: CF includes `debt_draws`, `debt_repayments`.
  - Lines 176-179: Retained earnings `re[t+1] = re[t] + ni` (no dividends yet).
  - Line 230: Financing is still a plug: `financing = closing - opening - operating - investing`.

- **`shared/fm_shared/model/kpis.py`** — Reads `debt_current`, `debt_non_current` from BS
  and `debt_repayments` from CF for `debt_equity` and `dscr`.

- **`shared/fm_shared/model/schemas.py`** — Already has all schemas needed:
  - `DividendsPolicy` (lines 141-143): `policy` (none|fixed_amount|payout_ratio), `value`
  - `EquityRaise` (lines 119-122): `amount`, `month`, `label`
  - `Funding` (lines 146-149): `equity_raises`, `debt_facilities`, `dividends`
  - `DebtFacility` (lines 130-138): `is_cash_plug` field for waterfall facilities
  - `WorkingCapital.minimum_cash` (line 101): `float = 0, ge=0`

- **`tests/conftest.py`** — `minimal_model_config_dict()` builds minimal configs.
  The `funding` key can be added to `assumptions` for test fixtures.

### What's missing (Phase 2 scope)

1. Dividends not applied — `DividendsPolicy` exists but is never read
2. Equity raises not applied — `EquityRaise` exists but is never read
3. No funding waterfall — cash-plug facilities (`is_cash_plug=True`) are ignored
4. No feedback loop — interest doesn't recalculate when waterfall injects debt

---

## Task: Implement Dividends, Equity Raises & Funding Waterfall

### Step 1 — Dividends in `statements.py`

In the IS loop (around line 134), after calculating `ni`, add a dividend line:

```python
dividend = 0.0
if config.assumptions.funding and config.assumptions.funding.dividends:
    policy = config.assumptions.funding.dividends
    if policy.policy == "fixed_amount":
        dividend = policy.value or 0.0
    elif policy.policy == "payout_ratio":
        dividend = max(0.0, ni * (policy.value or 0.0))
```

Add `"dividends": dividend` to the IS dict (after `net_income`).

Update retained earnings (around line 179):

```python
# Change from: re.append(re[-1] + is_list[t]["net_income"])
# Change to:
re.append(re[-1] + is_list[t]["net_income"] - is_list[t]["dividends"])
```

Add `"dividends_paid": dividend` to the CF dict.

### Step 2 — Equity Raises in `statements.py`

Create an equity raise schedule array before the BS loop:

```python
equity_raises_per_period = [0.0] * horizon
if config.assumptions.funding and config.assumptions.funding.equity_raises:
    for er in config.assumptions.funding.equity_raises:
        if 0 <= er.month < horizon:
            equity_raises_per_period[er.month] += er.amount
```

Update retained earnings to include equity raises:

```python
re.append(re[-1] + is_list[t]["net_income"] - is_list[t]["dividends"] + equity_raises_per_period[t])
```

Add `"equity_raised": equity_raises_per_period[t]` to the CF dict.

### Step 3 — Create `shared/fm_shared/model/funding_waterfall.py`

New module:

```python
from __future__ import annotations

from dataclasses import dataclass

from shared.fm_shared.model.schemas import DebtFacility


@dataclass
class WaterfallResult:
    cash_after_funding: list[float]
    additional_draws: dict[str, list[float]]  # facility_id -> extra draws per period
    overdraft_interest: list[float]
    equity_injected: list[float]


def empty_waterfall_result(horizon: int) -> WaterfallResult:
    return WaterfallResult(
        cash_after_funding=[0.0] * horizon,
        additional_draws={},
        overdraft_interest=[0.0] * horizon,
        equity_injected=[0.0] * horizon,
    )


def apply_funding_waterfall(
    closing_cash: list[float],
    facilities: list[DebtFacility],
    minimum_cash: float,
    horizon: int,
) -> WaterfallResult:
```

**Algorithm per period t:**

1. Sort facilities: revolvers first, overdrafts last
2. Track running balance per facility (start at 0)
3. If `closing_cash[t] < minimum_cash`:
   - `shortfall = minimum_cash - closing_cash[t]`
   - For each facility (in order):
     - Available = `facility.limit - current_balance`
     - Draw = `min(shortfall, available)`
     - Record draw in `additional_draws[facility_id][t]`
     - Update facility balance: `balance += draw`
     - `shortfall -= draw`
   - If shortfall remains and an overdraft facility exists:
     - Record overdraft amount
     - `overdraft_interest[t] = shortfall * overdraft.interest_rate / 12`
4. If `closing_cash[t] > minimum_cash` and facilities have outstanding balances:
   - Excess = `closing_cash[t] - minimum_cash`
   - Repay facilities in reverse order (overdraft first, then revolver)
   - Reduce balances accordingly
5. `cash_after_funding[t] = closing_cash[t] + total_draws - total_repays`

### Step 4 — Three-Statement Feedback Loop in `statements.py`

After the initial statement generation (after the CF loop), add an iteration:

```python
# Funding waterfall: detect cash shortfalls and inject funding
plug_facilities = []
minimum_cash = config.assumptions.working_capital.minimum_cash
if config.assumptions.funding and config.assumptions.funding.debt_facilities:
    plug_facilities = [f for f in config.assumptions.funding.debt_facilities if f.is_cash_plug]

if plug_facilities and minimum_cash > 0:
    from shared.fm_shared.model.funding_waterfall import apply_funding_waterfall

    for iteration in range(2):  # max 2 iterations to converge
        closing_cash = [bs_list[t]["cash"] for t in range(horizon)]
        waterfall = apply_funding_waterfall(closing_cash, plug_facilities, minimum_cash, horizon)

        # Check if any injection happened
        any_injection = any(
            waterfall.additional_draws.get(f.facility_id, [0.0] * horizon)[t] > 0
            for f in plug_facilities
            for t in range(horizon)
        )
        if not any_injection and all(v == 0.0 for v in waterfall.overdraft_interest):
            break  # converged

        # Recalculate: add waterfall interest to IS, rebuild RE, BS, CF
        for t in range(horizon):
            extra_interest = waterfall.overdraft_interest[t]
            # Add draws to total_liab
            extra_debt = sum(
                waterfall.additional_draws.get(f.facility_id, [0.0] * horizon)[t]
                for f in plug_facilities
            )
            if extra_interest > 0 or extra_debt > 0:
                # Update IS
                is_list[t]["interest_expense"] += extra_interest
                is_list[t]["ebt"] = is_list[t]["ebit"] - is_list[t]["interest_expense"]
                is_list[t]["tax"] = max(0.0, is_list[t]["ebt"] * tax_rate)
                is_list[t]["net_income"] = is_list[t]["ebt"] - is_list[t]["tax"]

        # Rebuild retained earnings and BS
        re = [initial_equity]
        for t in range(horizon):
            re.append(
                re[-1]
                + is_list[t]["net_income"]
                - is_list[t]["dividends"]
                + equity_raises_per_period[t]
            )

        # Rebuild BS with waterfall debt
        for t in range(horizon):
            waterfall_debt = sum(
                sum(waterfall.additional_draws.get(f.facility_id, [0.0] * horizon)[:t+1])
                for f in plug_facilities
            )
            total_liab = (
                ap[t]
                + debt_result.current_debt_per_period[t]
                + debt_result.non_current_debt_per_period[t]
                + waterfall_debt
            )
            total_equity = re[t + 1]
            cash_plug = total_liab + total_equity - (ar[t] + inv[t] + (ppe_gross[t] - acc_depr[t]))
            bs_list[t]["cash"] = cash_plug
            bs_list[t]["total_liabilities"] = total_liab
            bs_list[t]["total_equity"] = total_equity
            bs_list[t]["total_assets"] = (ar[t] + inv[t] + (ppe_gross[t] - acc_depr[t])) + cash_plug
            bs_list[t]["total_current_assets"] = cash_plug + ar[t] + inv[t]
            bs_list[t]["total_liabilities_equity"] = total_liab + total_equity

        # Rebuild CF
        opening_cash = [initial_cash] + [bs_list[t]["cash"] for t in range(horizon - 1)]
        for t in range(horizon):
            ni_t = is_list[t]["net_income"]
            da_t = da_per_month[t]
            delta_ar = ar[t] - (ar[t - 1] if t > 0 else 0)
            delta_inv = inv[t] - (inv[t - 1] if t > 0 else 0)
            delta_ap = ap[t] - (ap[t - 1] if t > 0 else 0)
            operating = ni_t + da_t - delta_ar - delta_inv + delta_ap
            investing = -(ppe_gross[t] - (ppe_gross[t - 1] if t > 0 else 0))
            closing = bs_list[t]["cash"]
            financing = closing - opening_cash[t] - operating - investing
            cf_list[t]["operating"] = operating
            cf_list[t]["financing"] = financing
            cf_list[t]["closing_cash"] = closing
            cf_list[t]["opening_cash"] = opening_cash[t]
            cf_list[t]["net_cf"] = operating + investing + financing
```

**Note:** This is pseudo-code showing the logic. The actual implementation should be clean
and well-structured. Consider extracting the BS/CF rebuild into helper functions if it
improves readability.

### Step 5 — Write tests

#### 5a: Unit tests for `funding_waterfall.py` — new file `tests/unit/test_funding_waterfall.py`

Write 8-10 tests:

1. **No shortfall** — cash always above minimum → no injections
2. **Single revolver injection** — cash goes negative in month 6, revolver draws to cover
3. **Revolver capped at limit** — shortfall exceeds revolver limit → partial cover
4. **Overdraft fallback** — revolver full, overdraft covers remainder
5. **Overdraft interest** — verify `overdraft_interest = |shortfall| * rate / 12`
6. **Surplus repayment** — cash exceeds minimum, repay outstanding draws
7. **Multiple facilities ordering** — revolver before overdraft
8. **Empty facilities** — no plug facilities → empty result

#### 5b: Unit tests for dividends and equity raises — `tests/unit/test_statements.py`

Add 4 tests:

1. **Fixed amount dividends** — $10K/month; verify IS dividends, RE reduced, CF dividends_paid
2. **Payout ratio dividends** — 30% of NI; verify calculation, no dividend when NI < 0
3. **Equity raise** — $200K at month 3; verify RE increases, CF equity_raised
4. **Combined dividends + debt** — verify both work together and BS balances

#### 5c: Golden test — new file `tests/golden/test_waterfall_golden.py`

Create a model that goes cash-negative to trigger the waterfall:
- Low initial cash ($10K), moderate revenue ($50K/month)
- Large capex at month 0 ($500K) creating immediate cash drain
- Revolver with `is_cash_plug=True`, $300K limit, 6% rate
- Overdraft with `is_cash_plug=True`, $200K limit, 12% rate
- minimum_cash = $5K
- Fixed dividend of $2K/month

Verify:
- Cash never drops below minimum_cash after waterfall
- Revolver draws before overdraft
- Interest recalculates after waterfall injection
- BS balances every period
- CF financing reflects waterfall draws

### Step 6 — Verify everything

1. Run `pytest tests/unit/test_funding_waterfall.py -v` — all new tests pass
2. Run `pytest tests/unit/test_statements.py -v` — existing + new tests pass
3. Run `pytest tests/golden/ -v` — all golden tests pass (manufacturing, debt, waterfall)
4. Run `pytest tests/ -v` — full suite passes, no regressions (currently 364 pass)
5. Verify BS balance: `total_assets == total_liabilities_equity` for every period in every test

---

## Constraints

- Do NOT create a git worktree — work in the current project directory
- Do NOT modify any existing schemas in `schemas.py`
- Do NOT modify `engine.py`, `debt.py`, or `kpis.py`
- Do NOT modify any frontend files (`apps/web/`), API routers, settings, or auth
- Do NOT modify any test files outside of `test_statements.py` and the new test files you create
- Do NOT break existing tests — all 364 backend tests must continue to pass
- Keep the feedback loop to max 2 iterations — if it doesn't converge, accept the result

---

## Files to create

| File | Purpose |
|------|---------|
| `shared/fm_shared/model/funding_waterfall.py` | Waterfall calculator |
| `tests/unit/test_funding_waterfall.py` | Unit tests for waterfall |
| `tests/golden/test_waterfall_golden.py` | Golden comparison test |
| `tests/golden/waterfall_config.json` | Golden test model config |
| `tests/golden/waterfall_base_statements.json` | Golden expected statements |
| `tests/golden/waterfall_base_kpis.json` | Golden expected KPIs |

## Files to modify

| File | Change |
|------|--------|
| `shared/fm_shared/model/statements.py` | Add dividends, equity raises, waterfall feedback loop |
| `tests/unit/test_statements.py` | Add dividend, equity raise, combined tests |

## Commit

Single commit: `DG-P2: dividends, equity raises, funding waterfall with feedback loop`
