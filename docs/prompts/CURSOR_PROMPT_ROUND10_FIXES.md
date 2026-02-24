# Round 10 — Code Review Fixes

Apply **all** fixes below in one pass. Each item includes the file, line range, the
problem, and the exact change required. Do NOT add, remove, or refactor anything
beyond what is specified.

---

## HIGH

### R10-01  XSS — `primary_color` unsanitised in CSS (board_pack_export.py)

**File:** `apps/api/app/services/board_pack_export.py`
**Lines:** 56, 97-114
**Problem:** `primary_color` from user-supplied `branding_json` is interpolated
directly into CSS `style` attributes and a `<style>` block. A malicious tenant
could store `#2563eb; } body{background:url('https://evil.com')} .x{color:#fff`
as a colour and break out of the CSS context.

**Fix:** Validate `primary_color` at the top of `build_board_pack_html` with a
strict regex. If it fails, fall back to the default colour.

Add this import at the top of the file (after `from typing import Any`):

```python
import re
```

Replace line 56:

```python
    primary_color = (branding.get("primary_color") or "#2563eb").strip()
```

with:

```python
    _raw_color = (branding.get("primary_color") or "#2563eb").strip()
    primary_color = _raw_color if re.fullmatch(r"#[0-9a-fA-F]{3,8}", _raw_color) else "#2563eb"
```

---

### R10-02  XSS — `logo_url` unsanitised in `<img>` src (board_pack_export.py)

**File:** `apps/api/app/services/board_pack_export.py`
**Line:** 84
**Problem:** `logo_url` from branding is placed into an `<img src='…'>` with only
`_html.escape` which does not block `javascript:` or `data:` URI schemes.

**Fix:** Validate that `logo_url` uses an allowed scheme before rendering.

Replace line 58 (the `logo_url` assignment):

```python
    logo_url = branding.get("logo_url") or ""
```

with:

```python
    _raw_logo = branding.get("logo_url") or ""
    logo_url = _raw_logo if _raw_logo.startswith(("https://", "http://")) else ""
```

---

## MEDIUM

### R10-03  Budget submit lacks transaction wrapper (budgets.py)

**File:** `apps/api/app/routers/budgets.py`
**Lines:** 480-511 (the `submit_budget` function body after `async with tenant_conn`)
**Problem:** The workflow instance INSERT and budget UPDATE are two separate
writes with no explicit transaction. If the INSERT succeeds and the UPDATE
fails (or a concurrent request also submits), you get an orphaned workflow
instance or duplicate submissions.

**Fix:** Wrap the writes in `conn.transaction()`:

Replace:

```python
    async with tenant_conn(x_tenant_id) as conn:
        row = await get_budget(conn, x_tenant_id, budget_id)
        if not row:
            raise HTTPException(404, "Budget not found")
        if row["status"] != "draft":
            raise HTTPException(400, "Only draft budgets can be submitted for approval")
        if row.get("workflow_instance_id"):
            raise HTTPException(400, "Budget already submitted (workflow exists)")
        instance_id = f"wf_{uuid.uuid4().hex[:14]}"
        await conn.execute(
```

with:

```python
    async with tenant_conn(x_tenant_id) as conn:
        row = await get_budget(conn, x_tenant_id, budget_id)
        if not row:
            raise HTTPException(404, "Budget not found")
        if row["status"] != "draft":
            raise HTTPException(400, "Only draft budgets can be submitted for approval")
        if row.get("workflow_instance_id"):
            raise HTTPException(400, "Budget already submitted (workflow exists)")
        instance_id = f"wf_{uuid.uuid4().hex[:14]}"
        async with conn.transaction():
            await conn.execute(
```

And indent the two `await conn.execute(...)` calls plus the final re-read
by one additional level so they live inside the `conn.transaction()` block.
The lines to indent are from the first `await conn.execute` (the INSERT into
workflow_instances) through the closing of the second `await conn.execute`
(the UPDATE budgets), inclusive. The final `row = await get_budget(...)` can
stay inside or outside the transaction — either is fine.

---

### R10-04  Workflow update_instance + budget activate not in transaction (workflows.py)

**File:** `apps/api/app/routers/workflows.py`
**Problem:** The `update_instance` endpoint (PATCH) performs the workflow
status UPDATE and (conditionally) the budget status UPDATE as separate writes
without a transaction. If the budget update fails, the workflow is still
marked completed.

**Fix:** Wrap both writes in `conn.transaction()`.

In the `update_instance` function, change:

```python
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
```

to:

```python
    async with tenant_conn(x_tenant_id) as conn:
      async with conn.transaction():
        row = await conn.fetchrow(
```

And indent everything inside the `tenant_conn` context (from the `fetchrow`
through the conditional budget update) by one additional level so it lives
inside `conn.transaction()`.

---

### R10-05  Workflow update_instance skips status transition validation (workflows.py)

**File:** `apps/api/app/routers/workflows.py` — `update_instance` endpoint
**Problem:** The endpoint accepts any valid status regardless of current state.
A user can PATCH `status=completed` directly from `pending`, bypassing all
approval stages. This defeats the purpose of the budget approval workflow.

**Fix:** After the `fetchrow` that retrieves the current instance, add a
transition check. Add a `current_status` read and a transition map:

After the `if not row: raise HTTPException(404, ...)` block, and before the
`await conn.execute("""UPDATE workflow_instances ...`)`, add:

```python
        current_status = row.get("status", "pending") if hasattr(row, "get") else "pending"
        # Fetch current status
        current_row = await conn.fetchrow(
            "SELECT status FROM workflow_instances WHERE tenant_id = $1 AND instance_id = $2",
            x_tenant_id, instance_id,
        )
        current_status = current_row["status"] if current_row else "pending"
        allowed_transitions = {
            "pending": {"in_progress", "submitted"},
            "in_progress": {"submitted", "returned"},
            "submitted": {"approved", "returned"},
            "approved": {"completed"},
            "returned": {"in_progress", "submitted"},
        }
        if body.status not in allowed_transitions.get(current_status, set()):
            raise HTTPException(
                400,
                f"Cannot transition from '{current_status}' to '{body.status}'; "
                f"allowed: {sorted(allowed_transitions.get(current_status, set()))}",
            )
```

Also update the initial `fetchrow` SELECT to include `status`:

```sql
SELECT entity_type, entity_id, status FROM workflow_instances
WHERE tenant_id = $1 AND instance_id = $2
```

Then you can simplify — use `row["status"]` directly instead of the second
fetchrow. The final version:

```python
        row = await conn.fetchrow(
            """SELECT entity_type, entity_id, status FROM workflow_instances
               WHERE tenant_id = $1 AND instance_id = $2""",
            x_tenant_id,
            instance_id,
        )
        if not row:
            raise HTTPException(404, "Workflow instance not found")
        current_status = row["status"]
        allowed_transitions = {
            "pending": {"in_progress", "submitted"},
            "in_progress": {"submitted", "returned"},
            "submitted": {"approved", "returned"},
            "approved": {"completed"},
            "returned": {"in_progress", "submitted"},
        }
        if body.status not in allowed_transitions.get(current_status, set()):
            raise HTTPException(
                400,
                f"Cannot transition from '{current_status}' to '{body.status}'; "
                f"allowed: {sorted(allowed_transitions.get(current_status, set()))}",
            )
```

---

### R10-06  Budget submit — unhandled FK error for missing template (budgets.py)

**File:** `apps/api/app/routers/budgets.py`
**Lines:** 489-498
**Problem:** If migration 0032 hasn't been applied or the `tpl_budget_approval`
template is missing, the INSERT into `workflow_instances` raises an asyncpg
`ForeignKeyViolationError` which is unhandled. This surfaces as a 500 error
to the caller.

**Fix:** Wrap the transaction block in a try/except for ForeignKeyViolationError:

After the `async with conn.transaction():` (from R10-03 fix) and around the
INSERT into workflow_instances, add:

```python
        try:
            async with conn.transaction():
                await conn.execute(
                    """INSERT INTO workflow_instances ...""",
                    ...
                )
                await conn.execute(
                    """UPDATE budgets SET status = 'submitted' ...""",
                    ...
                )
        except asyncpg.ForeignKeyViolationError:
            raise HTTPException(
                500,
                "Budget approval workflow template not found; run migration 0032",
            )
```

Note: `asyncpg` is already imported at the top of budgets.py.

---

### R10-07  Budget dashboard burn_rate uses total periods not actual periods (budgets.py)

**File:** `apps/api/app/routers/budgets.py`
**Lines:** 421-423
**Problem:** `burn_rate = (total_actual / n_periods)` where `n_periods` is the
count of budget periods with data, NOT the count of periods that have actuals.
If a 12-period budget has actuals for only 3 months, burn rate is divided by
12, understating the true monthly spend rate by 4x. This produces incorrect
runway calculations downstream.

**Fix:** Replace:

```python
            n_periods = len(budget_by_period) or 1
            burn_rate = (total_actual / n_periods) if n_periods else None
```

with:

```python
            n_actual_periods = len(actual_by_period) or 0
            burn_rate = (total_actual / n_actual_periods) if n_actual_periods > 0 else None
```

---

## LOW

### R10-08  `format` parameter shadows Python builtin (board_packs.py)

**File:** `apps/api/app/routers/board_packs.py`
**Line:** 404
**Problem:** The parameter name `format` shadows the Python builtin.

**Fix:** Rename the parameter to `export_format` while keeping the query
alias as `"format"` for API compatibility:

```python
    export_format: str = Query("html", alias="format", description="html, pdf, or pptx"),
```

Then update all references to `format` in the function body (lines 411, 447,
461, 483) to `export_format`.

---

### R10-09  Unconventional import placement (board_pack_schedules.py)

**File:** `apps/api/app/routers/board_pack_schedules.py`
**Line:** 25
**Problem:** `from pydantic import BaseModel, Field` is placed after the
router assignment at line 22, inconsistent with every other router file.

**Fix:** Move the import to the top-level import block (after line 9):

Delete line 25-26 (the blank line + the import) and add the import after line 9:

```python
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
```

---

### R10-10  RUN_ALL_PENDING_MIGRATIONS.sql header mismatch (recurring)

**File:** `apps/api/app/db/migrations/RUN_ALL_PENDING_MIGRATIONS.sql`
**Line:** 2
**Problem:** Header says "0008 through 0032" but file content only contains
through 0028. Carried forward from R9-01.

**Fix:** Change the header from:

```sql
-- Virtual Analyst — Pending migrations (0008 through 0032)
```

to:

```sql
-- Virtual Analyst — Pending migrations (0008 through 0028)
```

---

## Verification checklist

After applying all fixes, verify:

1. `grep -n "primary_color" apps/api/app/services/board_pack_export.py` → line
   with `re.fullmatch` present
2. `grep -n "logo_url" apps/api/app/services/board_pack_export.py` → line with
   `startswith(("https://", "http://"))` present
3. `grep -n "conn.transaction" apps/api/app/routers/budgets.py` → the
   `submit_budget` function now uses `conn.transaction()`
4. `grep -n "conn.transaction" apps/api/app/routers/workflows.py` → the
   `update_instance` function now uses `conn.transaction()`
5. `grep -n "allowed_transitions" apps/api/app/routers/workflows.py` → transition
   map is present
6. `grep -n "ForeignKeyViolationError" apps/api/app/routers/budgets.py` → FK
   error is caught in submit
7. `grep -n "n_actual_periods" apps/api/app/routers/budgets.py` → burn rate
   uses actual period count
8. `grep -n "export_format" apps/api/app/routers/board_packs.py` → builtin
   shadow removed
9. `head -5 apps/api/app/routers/board_pack_schedules.py` → no pydantic import
   below router assignment
10. `head -3 apps/api/app/db/migrations/RUN_ALL_PENDING_MIGRATIONS.sql` →
    header says "0028" not "0032"
