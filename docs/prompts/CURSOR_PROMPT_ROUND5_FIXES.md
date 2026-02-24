# Cursor Prompt — Round 5 Code Review Fixes

> Generated from code review of Phase 6 additions (workflows, assignments, reviews, inbox UI, settings/teams UI) and modified files (memos.py, api.ts, nav.tsx, middleware.ts).
> Round 4 fixes verified: all applied correctly.

---

## FIX R5-01 — MEDIUM: `update_assignment` uses raw `dict` body instead of Pydantic model

**File:** `apps/api/app/routers/assignments.py` line 258

**Problem:** `update_assignment` accepts `body: dict[str, Any]` instead of a Pydantic `BaseModel`. This is the only endpoint in the codebase that does this — all other endpoints (e.g. `CreateAssignmentBody`, `SubmitReviewBody`, `CreateInstanceBody`) use Pydantic. Without a model, FastAPI generates no schema in OpenAPI docs, there's no input validation, and arbitrary keys are silently accepted.

**Fix:** Create an `UpdateAssignmentBody` Pydantic model with optional fields:

```python
class UpdateAssignmentBody(BaseModel):
    status: str | None = Field(default=None, description="New status")
    instructions: str | None = None
    deadline: datetime | str | None = None
```

Update the endpoint signature:

```python
@router.patch("/{assignment_id}")
async def update_assignment(
    assignment_id: str,
    body: UpdateAssignmentBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
```

Update the field access to use `body.status`, `body.instructions`, `body.deadline` instead of `body["status"]`, etc. Keep the existing status validation logic (`if s not in (...)`).

---

## FIX R5-02 — MEDIUM: `claim_assignment` has check-then-update race condition

**File:** `apps/api/app/routers/assignments.py` lines 186–205

**Problem:** The claim flow does a SELECT to check `assignee_user_id IS NULL AND status = 'draft'`, then a separate UPDATE. Two users calling `/claim` at the same time can both pass the SELECT check, and only the last UPDATE wins — both get a 200 success response but only one is actually the assignee.

**Fix:** Replace the SELECT-check-then-UPDATE pattern with a single atomic UPDATE ... WHERE and check the rowcount:

```python
@router.post("/{assignment_id}/claim", status_code=200)
async def claim_assignment(
    assignment_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    if not x_tenant_id or not x_user_id:
        raise HTTPException(400, "X-Tenant-ID and X-User-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        result = await conn.execute(
            """UPDATE task_assignments
               SET assignee_user_id = $1, status = 'assigned'
               WHERE tenant_id = $2 AND assignment_id = $3
                 AND assignee_user_id IS NULL AND status = 'draft'""",
            x_user_id,
            x_tenant_id,
            assignment_id,
        )
        if result == "UPDATE 0":
            # Check why — either not found, already claimed, or wrong status
            row = await conn.fetchrow(
                "SELECT assignment_id, assignee_user_id, status FROM task_assignments WHERE tenant_id = $1 AND assignment_id = $2",
                x_tenant_id,
                assignment_id,
            )
            if not row:
                raise HTTPException(404, "Assignment not found")
            if row["assignee_user_id"] is not None:
                raise HTTPException(409, "Assignment already claimed")
            raise HTTPException(400, "Only draft pool assignments can be claimed")
        row = await conn.fetchrow(
            """SELECT assignment_id, workflow_instance_id, entity_type, entity_id,
                      assignee_user_id, assigned_by_user_id, status, deadline, instructions, created_at, submitted_at
               FROM task_assignments WHERE tenant_id = $1 AND assignment_id = $2""",
            x_tenant_id,
            assignment_id,
        )
    return _serialize_row(row)
```

Note: use HTTP 409 Conflict for the "already claimed" case to differentiate from validation errors.

---

## FIX R5-03 — MEDIUM: No server-side self-review guard

**File:** `apps/api/app/routers/assignments.py` lines 333–401

**Problem:** The frontend blocks self-review (review/page.tsx line 134 checks `assignment.assignee_user_id === userId`), but the API endpoint `submit_review` does NOT check this. Any tenant user can POST a review on their own assignment by calling the API directly, bypassing the UI guard.

**Fix:** After fetching the assignment row (line 349), add a check:

```python
        row = await conn.fetchrow(
            """SELECT assignment_id, assignee_user_id, status FROM task_assignments
               WHERE tenant_id = $1 AND assignment_id = $2""",
            x_tenant_id,
            assignment_id,
        )
        if not row:
            raise HTTPException(404, "Assignment not found")
        if row["assignee_user_id"] == x_user_id:
            raise HTTPException(403, "Cannot review your own assignment")
        if row["status"] != "submitted":
            raise HTTPException(400, "Only submitted assignments can be reviewed")
```

---

## FIX R5-04 — MEDIUM: Frontend conflates `tenantId` with `userId`

**Files:** (all of these set `tenantId = session.user.id` AND `userId = session.user.id`)
- `apps/web/app/inbox/page.tsx` lines 127–128
- `apps/web/app/inbox/[id]/page.tsx` lines 43–44
- `apps/web/app/inbox/[id]/review/page.tsx` lines 55–56
- `apps/web/app/settings/teams/page.tsx` lines 31–32
- `apps/web/app/settings/teams/[teamId]/page.tsx` line 123
- `apps/web/app/assignments/new/page.tsx` lines 32–33

**Problem:** In a multi-tenant system, `tenantId` (the organization) and `userId` (the auth user) are NOT the same value. All new pages set both to `session.user.id`. This will fail once real multi-tenancy is enabled — all API calls will send the wrong `X-Tenant-ID` header.

**Fix:** The user's tenant should come from user metadata (e.g. `session.user.user_metadata.tenant_id` or `app_metadata.tenant_id`). Create a shared helper and use it across all pages:

Create `apps/web/lib/auth.ts`:

```ts
import { createClient } from "@/lib/supabase/client";

export async function getAuthContext(): Promise<{
  tenantId: string;
  userId: string;
} | null> {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user?.id) return null;
  // Use tenant_id from user metadata if available, otherwise fall back to user.id
  // TODO: Once real multi-tenancy is live, require tenant_id in metadata
  const tenantId =
    (user.app_metadata?.tenant_id as string) ??
    (user.user_metadata?.tenant_id as string) ??
    user.id;
  return { tenantId, userId: user.id };
}
```

Then in each page, replace the `getSession` useEffect with:

```ts
import { getAuthContext } from "@/lib/auth";
// ...
useEffect(() => {
  let cancelled = false;
  (async () => {
    const ctx = await getAuthContext();
    if (cancelled || !ctx) return;
    setTenantId(ctx.tenantId);
    setUserId(ctx.userId);
  })();
  return () => { cancelled = true; };
}, []);
```

This also fixes FIX R5-05 (below) because `getAuthContext` uses `getUser()` internally.

---

## FIX R5-05 — MEDIUM: Frontend uses `getSession()` instead of `getUser()`

**Files:** Same files as R5-04 above.

**Problem:** Supabase recommends `getUser()` over `getSession()` for reading user data because `getUser()` validates with the Supabase Auth server, while `getSession()` only reads from local storage (JWT could be stale or tampered). This was flagged in Round 1 (C1) and has been propagated to all new pages.

**Fix:** Addressed by R5-04 above — the shared `getAuthContext()` helper uses `getUser()`. If R5-04 is deferred, at minimum change all `supabase.auth.getSession()` calls to `supabase.auth.getUser()` and read from `data.user` instead of `data.session.user`.

---

## FIX R5-06 — LOW: `AssignmentCard` uses `toLocaleDateString` with `timeStyle`

**File:** `apps/web/app/inbox/page.tsx` lines 27–30

**Problem:** `toLocaleDateString` does not support `timeStyle` — that option is only valid for `toLocaleString` or `toLocaleTimeString`. The `timeStyle` option is silently ignored (or may error in strict environments), so the deadline display won't show the time.

```ts
// Current (broken):
const deadlineStr = a.deadline
  ? new Date(a.deadline).toLocaleDateString(undefined, {
      dateStyle: "short",
      timeStyle: "short",
    })
  : null;
```

**Fix:** Change `toLocaleDateString` to `toLocaleString`:

```ts
const deadlineStr = a.deadline
  ? new Date(a.deadline).toLocaleString(undefined, {
      dateStyle: "short",
      timeStyle: "short",
    })
  : null;
```

---

## FIX R5-07 — LOW: `list_memos` limit/offset not validated with `Query()`

**File:** `apps/api/app/routers/memos.py` lines 97–98

**Problem:** `limit` and `offset` are plain `int` parameters without `Query()` bounds. This allows negative or extremely large values (e.g. `limit=-1` or `limit=999999999`), which may cause unexpected query results. All other list endpoints in the codebase use `Query(50, ge=1, le=200)` and `Query(0, ge=0)`.

**Fix:**

```python
@router.get("")
async def list_memos(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    memo_type: str | None = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
```

---

## FIX R5-08 — LOW: `list_reviews` has no pagination

**File:** `apps/api/app/routers/assignments.py` lines 404–438

**Problem:** The `list_reviews` endpoint returns ALL reviews for an assignment with no `LIMIT`/`OFFSET`. While it's unlikely any single assignment will have thousands of reviews, this is inconsistent with every other list endpoint and could cause issues at scale.

**Fix:** Add `limit` and `offset` parameters:

```python
@router.get("/{assignment_id}/reviews")
async def list_reviews(
    assignment_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
```

And update the SQL query:

```sql
SELECT ... FROM reviews WHERE tenant_id = $1 AND assignment_id = $2
ORDER BY created_at DESC LIMIT $3 OFFSET $4
```

Return `{"reviews": reviews_list, "limit": limit, "offset": offset}`.

---

## FIX R5-09 — LOW: `_build_summary_from_corrections` uses `repr()` for user-facing text

**File:** `apps/api/app/routers/assignments.py` line 326

**Problem:** The line `part += f"{c.old_value!r} → {c.new_value!r}"` uses Python `repr()` which wraps strings in quotes and adds escape characters (e.g. `'hello'` instead of `hello`). This text is stored in `change_summaries.summary_text` and is user-facing.

**Fix:** Use plain string values:

```python
if c.old_value is not None or c.new_value is not None:
    old_display = c.old_value if c.old_value is not None else "(empty)"
    new_display = c.new_value if c.new_value is not None else "(empty)"
    part += f"{old_display} → {new_display}"
```

---

## FIX R5-10 — LOW: Team detail `load` has unnecessary dep on `addJobFunctionId`

**File:** `apps/web/app/settings/teams/[teamId]/page.tsx` line 113

**Problem:** The `load` callback includes `addJobFunctionId` in its dependency array. `addJobFunctionId` is a form field that changes when the user selects a job function in the "Add member" form. This means selecting a different job function in the dropdown triggers a full data reload (re-fetching team and job functions from the API).

**Fix:** Move the default-job-function logic outside the `load` callback. Remove `addJobFunctionId` from the dependency array:

```ts
const load = useCallback(async () => {
    if (!tenantId) return;
    setError(null);
    try {
      const [teamRes, jfRes] = await Promise.all([
        api.teams.get(tenantId, teamId),
        api.teams.listJobFunctions(tenantId),
      ]);
      setTeam(teamRes);
      setEditName(teamRes.name);
      setEditDescription(teamRes.description ?? "");
      setJobFunctions(jfRes.job_functions);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, teamId]);
```

Then set the default job function in a separate `useEffect`:

```ts
useEffect(() => {
  if (jobFunctions.length && !addJobFunctionId) {
    setAddJobFunctionId(jobFunctions[0].job_function_id);
  }
}, [jobFunctions, addJobFunctionId]);
```

---

## FIX R5-11 — LOW: `workflow_instances.updated_at` has no auto-update trigger

**File:** `apps/api/app/db/migrations/0020_workflow_templates.sql`

**Problem:** `workflow_instances` has `updated_at timestamptz not null default now()` but no trigger to auto-update it on row changes. Manual updates (e.g. advancing `current_stage_index` or changing `status`) will leave `updated_at` stale at the original `now()`.

**Fix:** Add a trigger function and trigger in a new migration (or append to 0020 if it hasn't been applied yet):

```sql
-- Auto-update updated_at on workflow_instances
create or replace function update_workflow_instances_updated_at()
returns trigger as $$
begin
  NEW.updated_at = now();
  return NEW;
end;
$$ language plpgsql;

drop trigger if exists trg_workflow_instances_updated_at on workflow_instances;
create trigger trg_workflow_instances_updated_at
  before update on workflow_instances
  for each row execute function update_workflow_instances_updated_at();
```

---

## Summary

| Fix | Severity | File(s) | Description |
|-----|----------|---------|-------------|
| R5-01 | MEDIUM | assignments.py:258 | Replace raw dict body with Pydantic model |
| R5-02 | MEDIUM | assignments.py:186-205 | Atomic claim with UPDATE...WHERE |
| R5-03 | MEDIUM | assignments.py:333-401 | Server-side self-review guard |
| R5-04 | MEDIUM | 6 frontend pages | Extract shared auth helper; decouple tenantId from userId |
| R5-05 | MEDIUM | 6 frontend pages | Use `getUser()` instead of `getSession()` |
| R5-06 | LOW | inbox/page.tsx:27-30 | Change `toLocaleDateString` → `toLocaleString` |
| R5-07 | LOW | memos.py:97-98 | Add Query() validation to limit/offset |
| R5-08 | LOW | assignments.py:404-438 | Add pagination to list_reviews |
| R5-09 | LOW | assignments.py:326 | Remove `repr()` from user-facing summary |
| R5-10 | LOW | teams/[teamId]/page.tsx:113 | Remove stale `addJobFunctionId` dep from load |
| R5-11 | LOW | 0020_workflow_templates.sql | Add updated_at trigger for workflow_instances |

**Still outstanding from Round 1 (not re-listed here):**
- C1: No real auth middleware — `X-Tenant-ID` / `X-User-ID` headers are forgeable
- C5: LLM client singleton leak
