# Code Review Fix Prompt — Round 2 (Document Collaboration Feature)

> Apply ALL fixes below in order. Each fix is numbered and specifies exact file(s) and changes. Do NOT skip any fix. Do NOT add unrelated changes.

---

## FIX 1 — File Size Limit on Document Upload (HIGH)

`await file.read()` at line 40 reads the entire upload into memory with no cap. A multi-GB upload will OOM the worker.

**File: `apps/api/app/routers/documents.py`**

Add a constant at the top of the file (after `ENTITY_TYPES`):

```python
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
```

Replace the current `content = await file.read()` block (line 40) with a size-checked read:

```python
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large; maximum size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    content_type = file.content_type or "application/octet-stream"
```

---

## FIX 2 — Content-Disposition Header Injection (HIGH)

The `filename` on line 157 comes from the uploaded file's original name, which could contain `"`, newlines, or non-ASCII characters that break the header or enable injection.

**File: `apps/api/app/routers/documents.py`**

Add import at the top of the file:

```python
from urllib.parse import quote
```

Replace the Content-Disposition header in `get_document` (line 157):

```python
    # Old:
    #   headers={"Content-Disposition": f'attachment; filename="{filename}"'},

    # New — RFC 5987 encoding for safe filenames:
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
```

---

## FIX 3 — Comment Delete Authorization (MEDIUM)

Any user in the tenant can delete any comment. Only the comment author (or an admin, once roles exist) should be allowed.

**File: `apps/api/app/routers/comments.py`**

Replace the `delete_comment` endpoint (lines 137–153):

```python
@router.delete("/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> None:
    """Delete a comment (only by author). Replies cascade-delete via FK."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if not x_user_id:
        raise HTTPException(400, "X-User-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT created_by FROM comments WHERE tenant_id = $1 AND comment_id = $2""",
            x_tenant_id,
            comment_id,
        )
        if not row:
            raise HTTPException(404, "Comment not found")
        if row["created_by"] != x_user_id:
            raise HTTPException(403, "Only the comment author can delete this comment")
        await conn.execute(
            """DELETE FROM comments WHERE tenant_id = $1 AND comment_id = $2""",
            x_tenant_id,
            comment_id,
        )
```

---

## FIX 4 — Cache `get_artifact_store()` Singleton (MEDIUM)

`get_artifact_store()` in `deps.py` creates a new `ArtifactStore` (and potentially a new Supabase client) on every request. This is wasteful and was flagged in the prior review round as well.

**File: `apps/api/app/deps.py`**

Add a module-level cache variable and modify `get_artifact_store`:

```python
_artifact_store: ArtifactStore | None = None


def get_artifact_store() -> ArtifactStore:
    """Return ArtifactStore with Supabase client when configured, else in-memory."""
    global _artifact_store
    if _artifact_store is not None:
        return _artifact_store
    settings = get_settings()
    client: Any = None
    if settings.supabase_url and (settings.supabase_service_key or settings.supabase_anon_key):
        try:
            from supabase import create_client

            client = create_client(
                settings.supabase_url,
                settings.supabase_service_key or settings.supabase_anon_key,
            )
        except Exception:
            pass
    _artifact_store = ArtifactStore(supabase_client=client)
    return _artifact_store


def reset_artifact_store() -> None:
    global _artifact_store
    _artifact_store = None
```

---

## FIX 5 — Non-Atomic Document Upload (MEDIUM)

In `documents.py`, the artifact is stored (line 46) BEFORE the DB row is inserted (line 60). If the DB insert fails, there's an orphaned blob with no metadata. Reverse the order: insert DB row first, then store the artifact. On artifact failure, delete the DB row.

**File: `apps/api/app/routers/documents.py`**

Replace the upload logic inside `upload_document` (from `content = ...` through the return statement) with:

```python
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large; maximum size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    content_type = file.content_type or "application/octet-stream"
    filename = (file.filename or "attachment").strip() or "attachment"
    document_id = f"doc_{uuid.uuid4().hex[:16]}"

    # DB row first so we can roll back cleanly if artifact storage fails
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            """INSERT INTO document_attachments (tenant_id, document_id, entity_type, entity_id, filename, content_type, created_by)
             VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            x_tenant_id,
            document_id,
            entity_type,
            entity_id.strip(),
            filename,
            content_type,
            x_user_id or None,
        )

    try:
        store.save(
            x_tenant_id,
            DOCUMENT_ARTIFACT_TYPE,
            document_id,
            {
                "b64": base64.b64encode(content).decode("ascii"),
                "content_type": content_type,
                "filename": filename,
            },
        )
    except StorageError as e:
        # Clean up the DB row since artifact storage failed
        async with tenant_conn(x_tenant_id) as conn:
            await conn.execute(
                """DELETE FROM document_attachments WHERE tenant_id = $1 AND document_id = $2""",
                x_tenant_id,
                document_id,
            )
        raise HTTPException(500, str(e)) from e

    return {
        "document_id": document_id,
        "entity_type": entity_type,
        "entity_id": entity_id.strip(),
        "filename": filename,
        "content_type": content_type,
    }
```

---

## FIX 6 — Validate Mentioned Users Exist (MEDIUM)

In `comments.py`, `create_notification` is called for `@mentioned` user IDs without checking they exist. This creates orphaned notification rows.

**File: `apps/api/app/routers/comments.py`**

Replace the mention notification loop (lines 74–86) with a version that checks user existence:

```python
        if mentioned:
            existing = await conn.fetch(
                """SELECT id FROM users WHERE id = ANY($1::text[])""",
                list(mentioned),
            )
            valid_user_ids = {r["id"] for r in existing}
            for user_id in valid_user_ids:
                if user_id == x_user_id:
                    continue
                await create_notification(
                    conn,
                    x_tenant_id,
                    type_="comment_mention",
                    title="You were mentioned in a comment",
                    body=body.body[:200] + ("..." if len(body.body) > 200 else ""),
                    entity_type=body.entity_type,
                    entity_id=body.entity_id.strip(),
                    user_id=user_id,
                )
```

---

## FIX 7 — Activity Feed Double-Fetch Inconsistency (MEDIUM)

The activity endpoint fetches `limit` rows from audit_log AND `limit` rows from comments separately, then merges and truncates in Python. This means it always over-fetches, and the merged result may miss items that fall between the two result sets chronologically.

**File: `apps/api/app/routers/activity.py`**

This is an acceptable trade-off for v1 but add a comment making the behavior explicit, and double the per-source limit to reduce the chance of missing items:

Replace lines 48 and 77 (where `params_audit.append(limit)` and `params_cmt.append(limit)`) with:

```python
        # Fetch 2x limit from each source to reduce gaps after merge + truncate
        params_audit.append(limit * 2)
```

and:

```python
        params_cmt.append(limit * 2)
```

---

## FIX 8 — Log Artifact Delete Failures (MEDIUM)

In `artifact_store.py`, the new `delete` method silently swallows all exceptions. Storage failures should be logged.

**File: `shared/fm_shared/storage/artifact_store.py`**

Add import at the top of the file (after `from typing import Any`):

```python
import logging

_log = logging.getLogger(__name__)
```

Replace the `delete` method's except block (lines 92-93):

```python
            except Exception as exc:
                _log.warning("artifact_delete_failed", extra={"path": path, "error": str(exc)})
```

---

## FIX 9 — Validate `since` Parameter as ISO Datetime (LOW)

In `activity.py`, an invalid `since` value causes a Postgres cast error that surfaces as a 500 instead of a 400.

**File: `apps/api/app/routers/activity.py`**

Add import at the top of the file:

```python
from datetime import datetime
```

Add validation before the query building, right after the `if not x_tenant_id` check:

```python
    if since:
        try:
            datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(400, "Invalid 'since' parameter; must be ISO 8601 datetime")
```

---

## FIX 10 — Add `max_length` to Comment Body (LOW)

`CreateCommentBody.body` has `min_length=1` but no upper bound. A single comment could be arbitrarily large.

**File: `apps/api/app/routers/comments.py`**

Update the `body` field in `CreateCommentBody`:

```python
    body: str = Field(..., min_length=1, max_length=10000, description="Comment text; @user_id creates mention notification")
```

---

## FIX 11 — Add Pagination to `list_comments` (LOW)

Returns all comments for an entity with no limit.

**File: `apps/api/app/routers/comments.py`**

Add `limit` and `offset` parameters to `list_comments`:

```python
@router.get("")
async def list_comments(
    entity_type: str = Query(..., description="Entity type"),
    entity_id: str = Query(..., description="Entity ID"),
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List comments for an entity (flat list; parent_comment_id indicates threading)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(400, f"entity_type must be one of: {sorted(ENTITY_TYPES)}")

    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT comment_id, entity_type, entity_id, parent_comment_id, body, created_at, created_by
               FROM comments
               WHERE tenant_id = $1 AND entity_type = $2 AND entity_id = $3
               ORDER BY created_at ASC
               LIMIT $4 OFFSET $5""",
            x_tenant_id,
            entity_type,
            entity_id,
            limit,
            offset,
        )

    return {
        "comments": [
            {
                "comment_id": r["comment_id"],
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
                "parent_comment_id": r["parent_comment_id"],
                "body": r["body"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "created_by": r["created_by"],
            }
            for r in rows
        ],
    }
```

---

## FIX 12 — Add Pagination to `list_documents` (LOW)

Returns all documents for an entity with no limit.

**File: `apps/api/app/routers/documents.py`**

Add `limit` and `offset` parameters to `list_documents`:

```python
@router.get("")
async def list_documents(
    entity_type: str = Query(..., description="Entity type"),
    entity_id: str = Query(..., description="Entity ID"),
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List document attachments for an entity."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(400, f"entity_type must be one of: {sorted(ENTITY_TYPES)}")

    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT document_id, entity_type, entity_id, filename, content_type, created_at, created_by
               FROM document_attachments
               WHERE tenant_id = $1 AND entity_type = $2 AND entity_id = $3
               ORDER BY created_at DESC
               LIMIT $4 OFFSET $5""",
            x_tenant_id,
            entity_type,
            entity_id,
            limit,
            offset,
        )

    return {
        "documents": [
            {
                "document_id": r["document_id"],
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
                "filename": r["filename"],
                "content_type": r["content_type"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "created_by": r["created_by"],
            }
            for r in rows
        ],
    }
```

---

## FIX 13 — Add `file_size` Column to `document_attachments` (LOW)

Without file size at the DB level, you can't enforce storage quotas or display file size in listings without loading from the artifact store.

**File: `apps/api/app/db/migrations/0018_document_collaboration.sql`**

Add `file_size` column to the `document_attachments` table definition (after `content_type`):

```sql
create table if not exists document_attachments (
  tenant_id text not null references tenants(id) on delete cascade,
  document_id text not null,
  entity_type text not null,
  entity_id text not null,
  filename text not null,
  content_type text not null default 'application/octet-stream',
  file_size bigint not null default 0,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, document_id)
);
```

**File: `apps/api/app/routers/documents.py`**

In `upload_document`, add `file_size` to the INSERT (add `$8` and `len(content)`) and to the return dict.

In `list_documents`, add `file_size` to the SELECT and response dict.

---

## Summary

| Fix | Severity | File(s) | Description |
|-----|----------|---------|-------------|
| 1 | HIGH | documents.py | File size limit on upload |
| 2 | HIGH | documents.py | Content-Disposition header injection |
| 3 | MEDIUM | comments.py | Comment delete authorization |
| 4 | MEDIUM | deps.py | Cache artifact store singleton |
| 5 | MEDIUM | documents.py | Non-atomic upload (DB-first ordering) |
| 6 | MEDIUM | comments.py | Validate mentioned users exist |
| 7 | MEDIUM | activity.py | Double-fetch 2x buffer |
| 8 | MEDIUM | artifact_store.py | Log delete failures |
| 9 | LOW | activity.py | Validate `since` param |
| 10 | LOW | comments.py | Comment body max_length |
| 11 | LOW | comments.py | List comments pagination |
| 12 | LOW | documents.py | List documents pagination |
| 13 | LOW | migration + documents.py | Add file_size column |
