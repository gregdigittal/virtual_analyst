# Code Review Fix Prompt — Round 3 (Teams + Signup)

> Apply ALL fixes below in order. Each fix is numbered and specifies exact file(s) and changes. Do NOT skip any fix. Do NOT add unrelated changes.

---

## FIX 1 — Validate `job_function_id` in `update_member` (HIGH)

`update_member` accepts a `job_function_id` in the PATCH body but never validates it exists in the `job_functions` table. The DB FK will catch it, but the error is an opaque 500 instead of a clean 400. The same validation already exists in `add_member` — replicate it.

**File: `apps/api/app/routers/teams.py`**

In the `update_member` function, add a job-function existence check right after the member-not-found guard and before the `reports_to` check. Insert after line 334 (`raise HTTPException(404, "Member not found")`):

```python
        if body.job_function_id is not None:
            jf = await conn.fetchrow(
                """SELECT 1 FROM job_functions WHERE tenant_id = $1 AND job_function_id = $2""",
                x_tenant_id,
                body.job_function_id,
            )
            if not jf:
                raise HTTPException(400, "Unknown job_function_id for this tenant")
```

Place this block **before** the existing `if body.reports_to is not None:` check on line 335.

---

## FIX 2 — Block Self-Referencing `reports_to` (MEDIUM)

A user can currently be set as their own manager in both `add_member` and `update_member`. This is logically invalid and should be rejected.

**File: `apps/api/app/routers/teams.py`**

**In `add_member`** — add a self-reference check at line 283, right before the existing `if body.reports_to:` block:

```python
        if body.reports_to and body.reports_to == body.user_id:
            raise HTTPException(400, "A member cannot report to themselves")
```

Replace the existing `if body.reports_to:` on line 283 with this combined check. The full block becomes:

```python
        if body.reports_to:
            if body.reports_to == body.user_id:
                raise HTTPException(400, "A member cannot report to themselves")
            manager = await conn.fetchrow(
                """SELECT 1 FROM team_members
                   WHERE tenant_id = $1 AND team_id = $2 AND user_id = $3""",
                x_tenant_id,
                team_id,
                body.reports_to,
            )
            if not manager:
                raise HTTPException(
                    400,
                    "reports_to must be a user_id of an existing member in the same team",
                )
```

**In `update_member`** — add the same self-reference check inside the `if body.reports_to is not None:` block on line 335. The block becomes:

```python
        if body.reports_to is not None:
            if body.reports_to and body.reports_to == user_id:
                raise HTTPException(400, "A member cannot report to themselves")
            if body.reports_to:
                manager = await conn.fetchrow(
                    """SELECT 1 FROM team_members
                       WHERE tenant_id = $1 AND team_id = $2 AND user_id = $3""",
                    x_tenant_id,
                    team_id,
                    body.reports_to,
                )
                if not manager:
                    raise HTTPException(
                        400,
                        "reports_to must be a user_id of an existing member in the same team",
                    )
```

---

## FIX 3 — `update_team` No-Op Path Should Check Team Existence (MEDIUM)

When `update_team` receives an empty body (no fields to update), it calls `get_team()` which opens a separate DB connection. If the team doesn't exist, the user gets a generic 404 from `get_team` rather than a clear message. Check existence first.

**File: `apps/api/app/routers/teams.py`**

Replace lines 196-197:

```python
    if not updates:
        return await get_team(team_id, x_tenant_id)
```

With:

```python
    if not updates:
        raise HTTPException(400, "No fields to update; provide at least one of: name, description")
```

---

## FIX 4 — Fix `emailRedirectTo` URL in Signup (MEDIUM)

The signup page constructs the email redirect URL as `${origin}?next=...` which lands on the root page `/` with a query param. After email confirmation, Supabase redirects here, but the root `page.tsx` checks auth and redirects to `/baselines` without reading the `next` param. The redirect should go to `/login` so the user can sign in after confirming.

**File: `apps/web/app/signup/page.tsx`**

Replace line 41:

```tsx
        options: { emailRedirectTo: `${window.location.origin}${next ? `?next=${encodeURIComponent(next)}` : "" } },
```

With:

```tsx
        options: { emailRedirectTo: `${window.location.origin}/login${next ? `?next=${encodeURIComponent(next)}` : ""}` },
```

---

## FIX 5 — Remove Redundant ALTER TABLE in Consolidated Migration (MEDIUM)

The `RUN_ALL_PENDING_MIGRATIONS.sql` file has `file_size bigint not null default 0` in the `CREATE TABLE` for `document_attachments` and then immediately follows with `ALTER TABLE document_attachments ADD COLUMN IF NOT EXISTS file_size ...`. The ALTER is redundant since the column already exists in the CREATE.

**File: `apps/api/app/db/migrations/RUN_ALL_PENDING_MIGRATIONS.sql`**

Find and delete this line (it appears right after the `CREATE TABLE document_attachments` block and before the `CREATE INDEX`):

```sql
alter table document_attachments add column if not exists file_size bigint not null default 0;
```

---

## FIX 6 — Add Pagination to `list_teams` (LOW)

Returns all teams for a tenant with no limit.

**File: `apps/api/app/routers/teams.py`**

Add `Query` to the imports (it's not currently imported):

```python
from fastapi import APIRouter, Header, HTTPException, Query
```

Update the `list_teams` function signature and query:

```python
@router.get("")
async def list_teams(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List teams for the tenant."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT team_id, name, description, created_at, created_by
               FROM teams WHERE tenant_id = $1 ORDER BY name
               LIMIT $2 OFFSET $3""",
            x_tenant_id,
            limit,
            offset,
        )
    return {
        "teams": [
            {
                "team_id": r["team_id"],
                "name": r["name"],
                "description": r["description"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "created_by": r["created_by"],
            }
            for r in rows
        ],
    }
```

---

## FIX 7 — Add Pagination to `list_members` and `get_team` Members (LOW)

Both endpoints return all team members unbounded.

**File: `apps/api/app/routers/teams.py`**

Update `list_members` to accept pagination:

```python
@router.get("/{team_id}/members")
async def list_members(
    team_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List members of a team."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        team = await conn.fetchrow(
            """SELECT 1 FROM teams WHERE tenant_id = $1 AND team_id = $2""",
            x_tenant_id,
            team_id,
        )
        if not team:
            raise HTTPException(404, "Team not found")
        rows = await conn.fetch(
            """SELECT user_id, job_function_id, reports_to, created_at
               FROM team_members WHERE tenant_id = $1 AND team_id = $2
               ORDER BY created_at
               LIMIT $3 OFFSET $4""",
            x_tenant_id,
            team_id,
            limit,
            offset,
        )
    return {
        "members": [
            {
                "user_id": r["user_id"],
                "job_function_id": r["job_function_id"],
                "reports_to": r["reports_to"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
    }
```

Note: `get_team` embeds member list inline. For consistency, cap the embedded members in `get_team` at 200 by adding `LIMIT 200` to its members query on line 153:

```sql
SELECT user_id, job_function_id, reports_to, created_at
FROM team_members WHERE tenant_id = $1 AND team_id = $2
ORDER BY created_at
LIMIT 200
```

Also update the `update_member` return call on line 366 to pass the new pagination params:

```python
    return await list_members(team_id, x_tenant_id)
```

This still works since `limit` and `offset` have defaults, but note that FastAPI will use the defaults (100, 0) when called programmatically.

---

## FIX 8 — Verify SVG Assets Exist (LOW)

The landing page (`apps/web/app/page.tsx`) and auth pages reference `/va-icon.svg` and `/va-wordmark.svg`. Verify these files exist in `apps/web/public/`. If they don't, create placeholder SVGs so the pages don't show broken images.

**File: `apps/web/public/va-icon.svg`** — if missing, create:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none">
  <rect width="32" height="32" rx="6" fill="#3B82F6"/>
  <text x="50%" y="54%" dominant-baseline="middle" text-anchor="middle" fill="white" font-family="system-ui" font-weight="700" font-size="18">VA</text>
</svg>
```

**File: `apps/web/public/va-wordmark.svg`** — if missing, create:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 107" fill="none">
  <rect x="0" y="22" width="64" height="64" rx="10" fill="#3B82F6"/>
  <text x="32" y="60" dominant-baseline="middle" text-anchor="middle" fill="white" font-family="system-ui" font-weight="700" font-size="32">VA</text>
  <text x="84" y="62" dominant-baseline="middle" fill="#E2E8F0" font-family="system-ui" font-weight="600" font-size="28">Virtual Analyst</text>
</svg>
```

Only create these if the files don't already exist. If they exist, skip this fix.

---

## Summary

| Fix | Severity | File(s) | Description |
|-----|----------|---------|-------------|
| 1 | HIGH | teams.py | Validate `job_function_id` in `update_member` |
| 2 | MEDIUM | teams.py | Block self-referencing `reports_to` |
| 3 | MEDIUM | teams.py | `update_team` no-op returns helpful error |
| 4 | MEDIUM | signup/page.tsx | Fix `emailRedirectTo` URL to route to `/login` |
| 5 | MEDIUM | RUN_ALL_PENDING_MIGRATIONS.sql | Remove redundant ALTER TABLE |
| 6 | LOW | teams.py | Pagination on `list_teams` |
| 7 | LOW | teams.py | Pagination on `list_members` + cap in `get_team` |
| 8 | LOW | public/ SVGs | Create placeholder SVGs if missing |
