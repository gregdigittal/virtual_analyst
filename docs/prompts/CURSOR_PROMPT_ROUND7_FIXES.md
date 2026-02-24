# Cursor Prompt — Round 7 Code Review Fixes

> Generated from code review of Round 6 fix application + new Phase 7 features: Budget CRUD (VA-P7-02), budget templates with LLM initialization (VA-P7-03), actuals import & variance analysis (VA-P7-04), rolling reforecast (VA-P7-05), Nav component, SSO/OAuth flow.
> All 9 Round 6 fixes verified applied correctly (R6-07 improved beyond suggestion — returns 501 instead of pass-through when jose missing; R6-08 uses raw UUID instead of `ntf_` prefix but is functional).

---

## FIX R7-01 — HIGH: Nav component uses `getSession()` instead of `getUser()` and conflates tenantId with userId

**File:** `apps/web/components/nav.tsx` lines 17–27

**Problem:** R5-04 and R5-05 fixed all pages to use `getAuthContext()` (which calls `getUser()`) and derive `tenantId` from `app_metadata.tenant_id`. However, the Nav component was added after those fixes and uses the old unsafe pattern:

```typescript
const {
  data: { session },
} = await supabase.auth.getSession();
if (!session?.user?.id) return;
try {
  const res = await api.notifications.list(session.user.id, false, 1, 0);
```

Two problems:
1. `getSession()` reads from local storage without revalidating against the server (per Supabase docs). It should use `getUser()` for auth verification.
2. `session.user.id` is passed as `tenantId` to `api.notifications.list()`. This is wrong — the tenant ID should come from `app_metadata.tenant_id ?? user_metadata.tenant_id ?? user.id`, matching every other page.

**Fix:** Use the shared `getAuthContext()` helper (same pattern as every other page):

```typescript
"use client";

import { api } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export function Nav() {
  const router = useRouter();
  const [unreadCount, setUnreadCount] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      try {
        const res = await api.notifications.list(ctx.tenantId, false, 1, 0);
        if (!cancelled) setUnreadCount(res.unread_count);
      } catch {
        if (!cancelled) setUnreadCount(0);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSignOut() {
    api.setAccessToken(null);
    const { createClient } = await import("@/lib/supabase/client");
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
    router.refresh();
  }

  // ... rest of JSX unchanged ...
}
```

This also fixes the missing `setAccessToken` call (see R7-02 below).

---

## FIX R7-02 — HIGH: Nav component doesn't set access token before API call

**File:** `apps/web/components/nav.tsx` lines 16–27

**Problem:** The Nav calls `api.notifications.list()` without first calling `api.setAccessToken()`. When the auth middleware (R6-02) requires a Bearer token, this API call will be rejected with 401. If the Nav's `useEffect` fires before the page's `useEffect` sets the token, notifications will silently fail to load.

**Fix:** This is addressed by the R7-01 fix above — `getAuthContext()` returns the `accessToken`, and `api.setAccessToken(ctx.accessToken)` is called before any API request.

---

## FIX R7-03 — HIGH: `update_budget` SQL placeholder off-by-one will crash every PATCH request

**File:** `apps/api/app/routers/budgets.py` lines 371–403

**Problem:** The dynamic UPDATE query has an off-by-one error in its `$N` placeholder indices. After building SET clauses (e.g. `label = $1, fiscal_year = $2, status = $3`), the code appends `"updated_at = now()"` to the updates list but **also increments `n` even though this clause has no `$N` placeholder**. Then it uses `${n}` and `${n + 1}` for the WHERE clause, which reference non-existent arguments.

Trace with all 3 fields set:
- `n = 3` after SET clauses, `args = [label, fy, status]`
- `n += 1` → `n = 4`, appends `"updated_at = now()"` (no placeholder), appends `x_tenant_id` to args → `$4 = x_tenant_id`
- `n += 1` → `n = 5`, appends `budget_id` → `$5 = budget_id`
- WHERE clause: `tenant_id = ${n} AND budget_id = ${n + 1}` → `tenant_id = $5 AND budget_id = $6`
- **$5 is `budget_id` (not `x_tenant_id`) and $6 doesn't exist** → asyncpg crash

This will crash on **every** budget update call.

**Fix:** Remove the erroneous `n += 1` for the `updated_at = now()` clause (which has no placeholder), and fix the WHERE indices:

```python
    if not updates:
        return {
            "budget_id": row["budget_id"],
            "label": row["label"],
            "fiscal_year": row["fiscal_year"],
            "status": row["status"],
            "current_version_id": row["current_version_id"],
        }
    updates.append("updated_at = now()")
    n += 1
    args.append(x_tenant_id)
    n += 1
    args.append(budget_id)
    await conn.execute(
        f"UPDATE budgets SET {', '.join(updates)} WHERE tenant_id = ${n - 1} AND budget_id = ${n}",
        *args,
    )
    row = await get_budget(conn, x_tenant_id, budget_id)
```

Verify: with 3 fields, `n = 3` after SET. Then `n = 4` (x_tenant_id = $4), `n = 5` (budget_id = $5). WHERE: `${n-1}` = `$4`, `${n}` = `$5`. Correct.

---

## FIX R7-04 — MEDIUM: `list_line_items` N+1 query for amounts

**File:** `apps/api/app/routers/budgets.py` lines 596–617

**Problem:** For each line item, an individual SELECT fetches amounts:

```python
for r in rows:
    amt_rows = await conn.fetch(
        "SELECT period_ordinal, amount FROM budget_line_item_amounts WHERE tenant_id = $1 AND line_item_id = $2 ...",
        x_tenant_id, r["line_item_id"],
    )
```

With 100 line items, this executes 101 queries. Should fetch all amounts in one query and group in Python.

**Fix:** Use a single JOIN query:

```python
@router.get("/{budget_id}/line-items")
async def list_line_items(
    budget_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List line items for the budget's current version."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        _, version_id = await _resolve_current_version(conn, x_tenant_id, budget_id)
        rows = await conn.fetch(
            """SELECT bli.line_item_id, bli.account_ref, bli.notes, bli.confidence_score,
                      blia.period_ordinal, blia.amount
               FROM budget_line_items bli
               LEFT JOIN budget_line_item_amounts blia
                 ON blia.tenant_id = bli.tenant_id AND blia.line_item_id = bli.line_item_id
               WHERE bli.tenant_id = $1 AND bli.budget_id = $2 AND bli.version_id = $3
               ORDER BY bli.account_ref, blia.period_ordinal""",
            x_tenant_id,
            budget_id,
            version_id,
        )
        # Group by line_item_id
        from collections import OrderedDict
        grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for r in rows:
            lid = r["line_item_id"]
            if lid not in grouped:
                grouped[lid] = {
                    "line_item_id": lid,
                    "account_ref": r["account_ref"],
                    "notes": r["notes"],
                    "confidence_score": float(r["confidence_score"]) if r["confidence_score"] is not None else None,
                    "amounts": [],
                }
            if r["period_ordinal"] is not None:
                grouped[lid]["amounts"].append({
                    "period_ordinal": r["period_ordinal"],
                    "amount": float(r["amount"]),
                })
    return {"line_items": list(grouped.values())}
```

---

## FIX R7-05 — MEDIUM: `reforecast_budget` has triple N+1 query pattern per line item

**File:** `apps/api/app/routers/budgets.py` lines 1099–1184

**Problem:** The reforecast endpoint, inside a single transaction, does three individual SELECTs per line item:
1. Fetch amounts per line item (lines 1100–1103) — for building context
2. Fetch summed actuals per line item per period (lines 1152–1158) — for locking actuals
3. Fetch original amounts per line item (lines 1169–1173) — for fallback

With 50 line items and 12 periods, this is 150+ queries in one transaction.

**Fix:** Pre-fetch all data with bulk queries before the loop:

```python
    # Pre-fetch ALL amounts for current version in one query
    all_amounts = await conn.fetch(
        """SELECT bli.line_item_id, bli.account_ref, blia.period_ordinal, blia.amount
           FROM budget_line_items bli
           JOIN budget_line_item_amounts blia ON blia.tenant_id = bli.tenant_id AND blia.line_item_id = bli.line_item_id
           WHERE bli.tenant_id = $1 AND bli.budget_id = $2 AND bli.version_id = $3""",
        x_tenant_id, budget_id, cur_vid,
    )
    amounts_by_item: dict[str, list[dict]] = {}
    for r in all_amounts:
        amounts_by_item.setdefault(r["line_item_id"], []).append(
            {"period_ordinal": r["period_ordinal"], "amount": float(r["amount"])}
        )

    # Pre-fetch ALL actuals in one query
    all_actuals = await conn.fetch(
        """SELECT period_ordinal, account_ref, SUM(amount) AS total
           FROM budget_actuals WHERE tenant_id = $1 AND budget_id = $2
           GROUP BY period_ordinal, account_ref""",
        x_tenant_id, budget_id,
    )
    actuals_map: dict[tuple[int, str], float] = {}
    for r in all_actuals:
        actuals_map[(r["period_ordinal"], r["account_ref"])] = float(r["total"])
```

Then use `amounts_by_item[li["line_item_id"]]` and `actuals_map.get((per, account_ref), 0.0)` inside the loop instead of individual queries.

Apply the same bulk-fetch pattern to the `clone_budget` endpoint (lines 860–893) which has the same N+1 issue.

---

## FIX R7-06 — MEDIUM: `clone_budget` N+1 query for amounts per line item

**File:** `apps/api/app/routers/budgets.py` lines 860–893

**Problem:** Same N+1 pattern as R7-04/R7-05: for each cloned line item, an individual SELECT fetches its amounts.

**Fix:** Pre-fetch all amounts in one query before the loop:

```python
    # Pre-fetch all amounts for source version
    all_amounts = await conn.fetch(
        """SELECT bli.line_item_id, blia.period_ordinal, blia.amount
           FROM budget_line_items bli
           JOIN budget_line_item_amounts blia ON blia.tenant_id = bli.tenant_id AND blia.line_item_id = bli.line_item_id
           WHERE bli.tenant_id = $1 AND bli.budget_id = $2 AND bli.version_id = $3""",
        x_tenant_id, budget_id, version_id,
    )
    amounts_by_item: dict[str, list[tuple[int, float]]] = {}
    for r in all_amounts:
        amounts_by_item.setdefault(r["line_item_id"], []).append(
            (r["period_ordinal"], float(r["amount"]))
        )

    for r in rows:
        new_li_id = _line_item_id()
        # ... INSERT line item ...
        for period_ordinal, amount in amounts_by_item.get(r["line_item_id"], []):
            await conn.execute(
                """INSERT INTO budget_line_item_amounts (tenant_id, line_item_id, period_ordinal, amount)
                   VALUES ($1, $2, $3, $4)""",
                x_tenant_id, new_li_id, period_ordinal, amount,
            )
```

---

## FIX R7-07 — MEDIUM: `period_end` hardcoded to 28th for all months

**File:** `apps/api/app/routers/budgets.py` line 276

**Problem:** When creating budget periods from a template, the period end date is hardcoded to the 28th:

```python
end = f"{year}-{month:02d}-28"
```

January should end on the 31st, March on the 31st, February on the 28th/29th, etc. Every month except February will have the wrong end date.

**Fix:** Use `calendar.monthrange()`:

```python
import calendar

for ord in range(1, body.num_periods + 1):
    month = ((ord - 1) % 12) + 1
    year_offset = (ord - 1) // 12
    period_year = year + year_offset
    _, last_day = calendar.monthrange(period_year, month)
    period_id = _period_id()
    start = f"{period_year}-{month:02d}-01"
    end = f"{period_year}-{month:02d}-{last_day:02d}"
```

This also fixes R7-08 (year increment for multi-year budgets).

---

## FIX R7-08 — MEDIUM: Multi-year budgets (>12 periods) don't increment the year

**File:** `apps/api/app/routers/budgets.py` lines 272–273

**Problem:** For budgets with `num_periods > 12` (e.g. 18-month budgets), the month wraps correctly via `% 12` but the year never increments:

```python
for ord in range(1, body.num_periods + 1):
    month = ((ord - 1) % 12) + 1
    # year is fixed — period 13 would be Jan of the same year as period 1
```

Period 13 and period 1 would have identical dates (`{year}-01-01` to `{year}-01-28`), causing either duplicate key errors (if there's a unique constraint on dates) or data confusion.

**Fix:** Addressed in R7-07 fix above with `year_offset = (ord - 1) // 12` and `period_year = year + year_offset`.

---

## FIX R7-09 — LOW: `list_budgets` response missing `limit` and `offset` keys

**File:** `apps/api/app/routers/budgets.py` lines 172–185

**Problem:** The response only returns `{"budgets": [...]}` without the `limit` and `offset` fields. Every other list endpoint in the API (assignments, memos, reviews, notifications, workflows, etc.) includes these fields for pagination consistency.

**Fix:**

```python
    return {
        "budgets": [
            {
                "budget_id": r["budget_id"],
                "label": r["label"],
                "fiscal_year": r["fiscal_year"],
                "status": r["status"],
                "current_version_id": r["current_version_id"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rows
        ],
        "limit": limit,
        "offset": offset,
    }
```

---

## FIX R7-10 — LOW: `create_notification` uses raw UUID instead of `ntf_` prefix pattern

**File:** `apps/api/app/db/notifications.py` line 22

**Problem:** R6-08 suggested using the `ntf_` prefix to match the codebase pattern (`asn_`, `rev_`, `cs_`, `bud_`, `bli_`, etc.). The applied fix uses `uuid.uuid4()` directly:

```python
notification_id = uuid.uuid4()
```

This passes a UUID object to asyncpg, which works if the `notifications.id` column is of type `UUID`. But it's inconsistent with every other entity in the codebase which uses string IDs with type prefixes.

**Fix:** Use the string prefix pattern for consistency:

```python
notification_id = f"ntf_{uuid.uuid4().hex[:12]}"
```

If the `notifications.id` column is `UUID` type, change it to `TEXT` in a migration, or keep as UUID and use `str(uuid.uuid4())` — but the prefix pattern is preferred for debuggability and consistency.

---

## FIX R7-11 — LOW: Variance `favourable` flag uses hardcoded account name heuristic

**File:** `apps/api/app/routers/budgets.py` lines 1029–1031

**Problem:** The variance analysis classifies favourable/unfavourable based on whether the `account_ref` starts with "revenue", "income", or "subscription":

```python
favourable = (var_abs > 0 and acc.lower().startswith(("revenue", "income", "subscription"))) or (
    var_abs < 0 and not acc.lower().startswith(("revenue", "income", "subscription"))
)
```

This will misclassify accounts with non-standard names (e.g. "Gains", "Other Income", "Fee Revenue") or cost accounts that happen to match ("Revenue Offset COGS").

**Fix:** Add a comment documenting the convention, and consider adding an `is_revenue` boolean to `budget_line_items` in a future iteration:

```python
    # Heuristic: accounts starting with revenue/income/subscription treat positive variance as favourable.
    # All other accounts treat negative variance (under budget) as favourable.
    # TODO(VA-P7): add explicit is_revenue flag to budget_line_items for accuracy.
    is_revenue_line = acc.lower().startswith(("revenue", "income", "subscription", "fee", "gain"))
    favourable = (var_abs > 0 and is_revenue_line) or (var_abs < 0 and not is_revenue_line)
```

---

## Summary

| Fix | Severity | File(s) | Description |
|-----|----------|---------|-------------|
| R7-01 | HIGH | nav.tsx:17-27 | Uses `getSession()` instead of `getUser()`; conflates tenantId with userId |
| R7-02 | HIGH | nav.tsx:16-27 | Missing `setAccessToken()` before API call; 401 with auth middleware |
| R7-03 | HIGH | budgets.py:371-403 | SQL placeholder off-by-one in `update_budget`; every PATCH crashes |
| R7-04 | MEDIUM | budgets.py:596-617 | `list_line_items` N+1 query for amounts |
| R7-05 | MEDIUM | budgets.py:1099-1184 | `reforecast_budget` triple N+1 per line item |
| R7-06 | MEDIUM | budgets.py:860-893 | `clone_budget` N+1 for amounts per line item |
| R7-07 | MEDIUM | budgets.py:276 | Period end date hardcoded to 28th (wrong for all months except Feb) |
| R7-08 | MEDIUM | budgets.py:272-273 | Multi-year budgets don't increment year past period 12 |
| R7-09 | LOW | budgets.py:172-185 | `list_budgets` response missing `limit` and `offset` keys |
| R7-10 | LOW | notifications.py:22 | Uses raw UUID instead of `ntf_` string prefix pattern |
| R7-11 | LOW | budgets.py:1029-1031 | Variance `favourable` flag hardcodes account name heuristic |

**Round 6 fixes — all verified applied:**
R6-01 ✓ 401 on invalid JWT, R6-02 ✓ 401 on missing Bearer, R6-03 ✓ cron secret, R6-04 ✓ per-tenant error isolation, R6-05 ✓ NOT EXISTS subquery, R6-06 ✓ BackgroundTasks for LLM, R6-07 ✓ module-level jose import (improved: returns 501), R6-08 ✓ explicit notification ID (raw UUID, not `ntf_` prefix), R6-09 ✓ SSR safety comment

**Still outstanding from Round 1:**
- C5: LLM client singleton leak (partially addressed by `deps.py` singleton pattern, but `reset_llm_router()` is available)
