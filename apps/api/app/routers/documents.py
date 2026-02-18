"""Document attachments API (VA-P5-04): upload, list, get, delete."""

from __future__ import annotations

import base64
import uuid
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response

from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_artifact_store, require_role, ROLES_CAN_WRITE
from shared.fm_shared.errors import StorageError
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[require_role(*ROLES_CAN_WRITE)])

DOCUMENT_ARTIFACT_TYPE = "documents"
ENTITY_TYPES = frozenset({"run", "draft_session", "memo_pack", "baseline", "scenario", "venture"})
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile,
    entity_type: str = Query(..., description="Entity type (run, draft_session, memo_pack, baseline, scenario, venture)"),
    entity_id: str = Query(..., description="Target entity ID"),
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """Upload a document attached to an entity. File stored in artifact store."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(400, f"entity_type must be one of: {sorted(ENTITY_TYPES)}")
    if not entity_id or not entity_id.strip():
        raise HTTPException(400, "entity_id required")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large; maximum size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    content_type = file.content_type or "application/octet-stream"
    filename = (file.filename or "attachment").strip() or "attachment"
    document_id = f"doc_{uuid.uuid4().hex[:16]}"

    # DB row first so we can roll back cleanly if artifact storage fails
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            """INSERT INTO document_attachments (tenant_id, document_id, entity_type, entity_id, filename, content_type, file_size, created_by)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            x_tenant_id,
            document_id,
            entity_type,
            entity_id.strip(),
            filename,
            content_type,
            len(content),
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
        "file_size": len(content),
    }


@router.get("")
async def list_documents(
    entity_type: str = Query(..., description="Entity type"),
    entity_id: str = Query(..., description="Entity ID"),
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List document attachments for an entity."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(400, f"entity_type must be one of: {sorted(ENTITY_TYPES)}")

    async with tenant_conn(x_tenant_id) as conn:
        total = await conn.fetchval(
            """SELECT count(*) FROM document_attachments
               WHERE tenant_id = $1 AND entity_type = $2 AND entity_id = $3""",
            x_tenant_id,
            entity_type,
            entity_id,
        )
        rows = await conn.fetch(
            """SELECT document_id, entity_type, entity_id, filename, content_type, file_size, created_at, created_by
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

    items = [
        {
            "document_id": r["document_id"],
            "entity_type": r["entity_type"],
            "entity_id": r["entity_id"],
            "filename": r["filename"],
            "content_type": r["content_type"],
            "file_size": r.get("file_size"),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "created_by": r["created_by"],
        }
        for r in rows
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> Response:
    """Download a document by ID. Returns file with Content-Disposition."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT document_id, filename, content_type FROM document_attachments
               WHERE tenant_id = $1 AND document_id = $2""",
            x_tenant_id,
            document_id,
        )
    if not row:
        raise HTTPException(404, "Document not found")

    try:
        data = store.load(x_tenant_id, DOCUMENT_ARTIFACT_TYPE, document_id)
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Document content not found") from e
        raise HTTPException(500, str(e)) from e

    b64 = data.get("b64")
    if not b64:
        raise HTTPException(500, "Invalid document storage format")
    content = base64.b64decode(b64)
    content_type = data.get("content_type") or row["content_type"] or "application/octet-stream"
    filename = data.get("filename") or row["filename"] or "attachment"

    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> None:
    """Delete a document and its stored content."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT 1 FROM document_attachments WHERE tenant_id = $1 AND document_id = $2""",
            x_tenant_id,
            document_id,
        )
        if not row:
            raise HTTPException(404, "Document not found")
        await conn.execute(
            """DELETE FROM document_attachments WHERE tenant_id = $1 AND document_id = $2""",
            x_tenant_id,
            document_id,
        )

    try:
        store.delete(x_tenant_id, DOCUMENT_ARTIFACT_TYPE, document_id)
    except Exception:
        pass
