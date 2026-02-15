# Cursor Prompt — Round 6 Code Review Fixes

> Generated from code review of Round 5 fix application + new Phase 6 features: auth middleware (C1), notification helpers, deadline reminder cron (VA-P6-07), LLM learning points (VA-P6-06), feedback API, Bearer token auth in frontend.
> All 11 Round 5 fixes verified applied correctly.

---

## FIX R6-01 — HIGH: Auth middleware silently passes requests on JWT failure

**File:** `apps/api/app/middleware/auth.py` lines 55–57

**Problem:** When JWT verification fails (expired token, wrong signature, bad audience), the middleware logs a warning but still calls `call_next(request)` **without stripping the original client-supplied X-Tenant-ID / X-User-ID headers**. This means an attacker can send a deliberately invalid/expired JWT alongside forged `X-Tenant-ID: victim_tenant` headers and the request will be processed as that tenant.

```python
    except Exception as e:
        logger.warning("auth_jwt_invalid", path=path, error=str(e))
        return await call_next(request)  # ← forged headers pass through
```

This defeats the entire purpose of the auth middleware (C1 fix).

**Fix:** Return HTTP 401 when a JWT is present but invalid:

```python
    except Exception as e:
        logger.warning("auth_jwt_invalid", path=path, error=str(e))
        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or expired token"},
        )
```

---

## FIX R6-02 — HIGH: Auth middleware allows unauthenticated requests with forged headers

**File:** `apps/api/app/middleware/auth.py` lines 38–39

**Problem:** When `SUPABASE_JWT_SECRET` is set (production mode) but no `Authorization` header is present, the middleware passes the request through with whatever `X-Tenant-ID` / `X-User-ID` headers the client sent. This means any unauthenticated client can call any endpoint with forged tenant/user headers.

```python
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return await call_next(request)  # ← no auth required, forged headers accepted
```

**Fix:** When JWT secret is configured, require a Bearer token on all non-skipped paths. Return 401 if missing:

```python
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=401,
            content={"detail": "Authorization header required"},
        )
```

If you need a transition period where some endpoints work without auth (e.g. the cron endpoint), add those paths to `SKIP_AUTH_PATHS` explicitly.

---

## FIX R6-03 — MEDIUM: `cron_deadline_reminders` has no authentication or authorization

**File:** `apps/api/app/routers/assignments.py` lines 575–659

**Problem:** The `POST /api/v1/assignments/cron/deadline-reminders` endpoint has no tenant/user headers, no auth check, and iterates over ALL tenants using a raw `asyncpg.connect()` call that bypasses connection pooling and RLS. Any external client can trigger this endpoint, which:
1. Reveals the number of tenants (via the `created` count)
2. Creates notifications for every tenant
3. Causes database load from iterating all tenants

**Fix:** Protect the cron endpoint with a shared secret:

```python
@router.post("/cron/deadline-reminders", status_code=200)
async def cron_deadline_reminders(
    x_cron_secret: str = Header("", alias="X-Cron-Secret"),
) -> dict[str, Any]:
    """Create deadline notifications. Requires X-Cron-Secret header matching CRON_SECRET env var."""
    from apps.api.app.core.settings import get_settings
    settings = get_settings()
    if not settings.cron_secret or x_cron_secret != settings.cron_secret:
        raise HTTPException(403, "Invalid cron secret")
    # ... rest of the function
```

Add `cron_secret: str | None = Field(default=None, alias="CRON_SECRET")` to `Settings`.

Also add `/api/v1/assignments/cron/deadline-reminders` to `SKIP_AUTH_PATHS` in `auth.py` (since the cron caller won't have a user JWT, it uses its own secret).

---

## FIX R6-04 — MEDIUM: `cron_deadline_reminders` fails all tenants on single tenant error

**File:** `apps/api/app/routers/assignments.py` lines 586–656

**Problem:** If any exception occurs while processing one tenant (e.g. a missing notifications table, a constraint violation), the entire cron job fails and no subsequent tenants are processed. The `try/finally` only protects the raw connection close.

**Fix:** Wrap the per-tenant processing in a try/except:

```python
    for trow in tenant_rows:
        tenant_id = trow["id"]
        try:
            async with tenant_conn(tenant_id) as tconn:
                # ... existing notification logic ...
        except Exception as e:
            logger.error("cron_deadline_tenant_error", tenant_id=tenant_id, error=str(e))
            continue
```

---

## FIX R6-05 — MEDIUM: `cron_deadline_reminders` N+1 query pattern per assignment

**File:** `apps/api/app/routers/assignments.py` lines 607–627 and 637–656

**Problem:** For each assignment with an approaching deadline, the code does an individual `SELECT 1 FROM notifications WHERE ...` to check for duplicates. With 100 tenants and 50 assignments each, that's 5000+ individual queries per cron run.

**Fix:** Use a `NOT EXISTS` subquery to fetch only assignments that don't already have a notification in one query:

```python
rows = await tconn.fetch(
    """SELECT assignment_id, entity_type, entity_id, assignee_user_id
       FROM task_assignments ta
       WHERE ta.tenant_id = $1 AND ta.deadline IS NOT NULL AND ta.assignee_user_id IS NOT NULL
         AND ta.status IN ('draft', 'assigned', 'in_progress', 'submitted')
         AND ta.deadline > $2 AND ta.deadline <= $3
         AND NOT EXISTS (
           SELECT 1 FROM notifications n
           WHERE n.tenant_id = $1 AND n.type = $4
             AND n.entity_type = 'assignment' AND n.entity_id = ta.assignment_id
             AND n.created_at > now() - interval '48 hours'
         )""",
    tenant_id, start, end, type_,
)
# Now just insert for each row — no need for individual existence checks
for r in rows:
    await create_notification(...)
    created += 1
```

Apply the same pattern for the overdue query.

---

## FIX R6-06 — MEDIUM: `submit_review` LLM call blocks the HTTP response

**File:** `apps/api/app/routers/assignments.py` lines 493–520

**Problem:** After the review is committed to the database, the endpoint calls `llm.complete_with_routing()` to generate learning points. This is an external LLM API call that could take 2-10+ seconds. The HTTP response is blocked until the LLM call completes (or fails). The user sees a long spinner on the review form.

The comment says "non-blocking" but it's actually synchronous — `await` blocks the response.

**Fix:** Move the LLM call to a background task so the response returns immediately:

```python
from fastapi import BackgroundTasks

@router.post("/{assignment_id}/review", status_code=201)
async def submit_review(
    assignment_id: str,
    body: SubmitReviewBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm: LLMRouter = Depends(get_llm_router),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> dict[str, Any]:
    # ... existing DB operations ...

    # Generate learning points in background (VA-P6-06)
    if summary_id and summary_text and body.corrections:
        background_tasks.add_task(
            _generate_learning_points, x_tenant_id, summary_id, summary_text, body.corrections, llm
        )

    return { ... }


async def _generate_learning_points(
    tenant_id: str,
    summary_id: str,
    summary_text: str,
    corrections: list[CorrectionItem],
    llm: LLMRouter,
) -> None:
    try:
        prompt = (
            "You are helping an analyst learn from review feedback. ..."
            + summary_text
        )
        resp = await llm.complete_with_routing(
            tenant_id=tenant_id,
            messages=[{"role": "user", "content": prompt}],
            response_schema=REVIEW_SUMMARY_SCHEMA,
            task_label="review_summary",
            max_tokens=1024,
            temperature=0.2,
        )
        points = resp.content.get("learning_points") or []
        if isinstance(points, list) and points:
            async with tenant_conn(tenant_id) as conn:
                await conn.execute(
                    """UPDATE change_summaries SET learning_points_json = $1::jsonb
                       WHERE tenant_id = $2 AND summary_id = $3""",
                    json.dumps(points),
                    tenant_id,
                    summary_id,
                )
    except Exception:
        pass  # leave learning_points_json as default []
```

---

## FIX R6-07 — LOW: `jose` imported at request time inside auth middleware

**File:** `apps/api/app/middleware/auth.py` line 46

**Problem:** `from jose import jwt` is inside the request handler. Python caches module imports, so performance is fine after the first call. But if the `python-jose` package is not installed, the app starts normally and only fails at runtime on the first authenticated request — a confusing failure mode.

**Fix:** Move the import to the module level and handle the missing dependency at import time:

```python
"""Auth middleware: verify Supabase JWT and set X-Tenant-ID / X-User-ID from token (C1)."""

from __future__ import annotations

import structlog
from starlette.requests import Request

try:
    from jose import jwt as jose_jwt
except ImportError:
    jose_jwt = None  # type: ignore[assignment]

from apps.api.app.core.settings import get_settings

logger = structlog.get_logger()
```

Then in the middleware:

```python
    if jose_jwt is None:
        logger.warning("auth_jose_not_installed", msg="python-jose not installed; JWT verification disabled")
        return await call_next(request)

    try:
        payload = jose_jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": True},
        )
    except Exception as e:
        # ... handle error per R6-01 ...
```

---

## FIX R6-08 — LOW: `create_notification` doesn't specify an ID column

**File:** `apps/api/app/db/notifications.py` lines 20–30

**Problem:** The INSERT into `notifications` does not include an `id` column:

```python
await conn.execute(
    """INSERT INTO notifications (tenant_id, user_id, type, title, body, entity_type, entity_id)
       VALUES ($1, $2, $3, $4, $5, $6, $7)""",
    ...
)
```

This relies on the `notifications` table having a default value for `id` (e.g. `DEFAULT gen_random_uuid()`). If the table schema doesn't have this default, every notification insert will fail silently within the assignment lifecycle endpoints (since `create_notification` is called without error handling in some paths).

**Fix:** Generate the ID explicitly in the helper for safety and consistency with the `asn_`, `rev_`, `cs_` patterns used elsewhere:

```python
import uuid

async def create_notification(
    conn: asyncpg.Connection,
    tenant_id: str,
    type_: str,
    title: str,
    body: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    user_id: str | None = None,
) -> str:
    notification_id = f"ntf_{uuid.uuid4().hex[:12]}"
    await conn.execute(
        """INSERT INTO notifications (id, tenant_id, user_id, type, title, body, entity_type, entity_id)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
        notification_id,
        tenant_id,
        user_id,
        type_,
        title,
        body,
        entity_type,
        entity_id,
    )
    return notification_id
```

---

## FIX R6-09 — LOW: `_accessToken` module-level mutable state is SSR-unsafe

**File:** `apps/web/lib/api.ts` lines 9–14

**Problem:** `_accessToken` is module-level mutable state. In Next.js, if any server component or server-side code imports `api`, this token persists in the Node.js process across requests — one user's token could leak to another user's server-rendered request. Currently all consumers are `"use client"` pages, but this pattern is fragile.

**Fix:** This is low priority since all current usage is client-only. For future-proofing, add a comment warning:

```ts
/**
 * Module-level access token. ONLY safe in client-side ("use client") contexts.
 * Do NOT import api.ts from server components or getServerSideProps — the token
 * would persist across requests in the Node.js process.
 */
let _accessToken: string | null = null;
```

Or alternatively, consider passing the token per-request via the `ApiOptions` interface instead of global state.

---

## Summary

| Fix | Severity | File(s) | Description |
|-----|----------|---------|-------------|
| R6-01 | HIGH | middleware/auth.py:55-57 | Return 401 on invalid JWT instead of passing through with forged headers |
| R6-02 | HIGH | middleware/auth.py:38-39 | Require Bearer token when JWT secret is configured |
| R6-03 | MEDIUM | assignments.py:575-659 | Protect cron endpoint with shared secret |
| R6-04 | MEDIUM | assignments.py:586-656 | Catch per-tenant errors so one tenant failure doesn't stop all |
| R6-05 | MEDIUM | assignments.py:607-656 | Replace N+1 notification existence checks with NOT EXISTS subquery |
| R6-06 | MEDIUM | assignments.py:493-520 | Move LLM learning points call to BackgroundTasks |
| R6-07 | LOW | middleware/auth.py:46 | Move `jose` import to module level with graceful fallback |
| R6-08 | LOW | db/notifications.py:20-30 | Generate notification ID explicitly |
| R6-09 | LOW | api.ts:9-14 | Document SSR safety constraint on module-level token |

**Round 5 fixes — all verified applied:**
R5-01 ✓ Pydantic model, R5-02 ✓ atomic claim, R5-03 ✓ self-review guard, R5-04 ✓ getAuthContext helper, R5-05 ✓ getUser(), R5-06 ✓ toLocaleString, R5-07 ✓ Query() validation, R5-08 ✓ list_reviews pagination, R5-09 ✓ plain strings, R5-10 ✓ load deps fixed, R5-11 ✓ updated_at trigger

**Still outstanding from Round 1:**
- C5: LLM client singleton leak (partially addressed by `deps.py` singleton pattern, but `reset_llm_router()` is available)
