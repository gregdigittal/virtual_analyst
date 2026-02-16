"""Memo pack API (VA-P5-03): generate, list, get, download."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_artifact_store, require_role, ROLES_CAN_WRITE
from apps.api.app.services.memo_service import MEMO_TYPES, generate_memo_html, html_to_pdf
from shared.fm_shared.errors import StorageError
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/memos", tags=["memos"], dependencies=[require_role(*ROLES_CAN_WRITE)])

MEMO_ARTIFACT_TYPE = "memo_pack"


class CreateMemoBody(BaseModel):
    run_id: str = Field(..., description="Source run ID")
    memo_type: str = Field(
        default="investment_committee",
        description="investment_committee, credit_memo, or valuation_note",
    )
    title: str | None = Field(default=None, description="Custom title")


@router.post("", status_code=201)
async def create_memo(
    body: CreateMemoBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """Generate a memo pack from a run. Body: run_id, memo_type, options (optional)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.memo_type not in MEMO_TYPES:
        raise HTTPException(400, f"memo_type must be one of: {MEMO_TYPES}")
    try:
        data = store.load(x_tenant_id, "run_results", f"{body.run_id}_statements")
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Run results not found") from e
        raise
    statements = data.get("statements", {})
    kpis = data.get("kpis", [])
    html = generate_memo_html(
        body.memo_type, statements, kpis=kpis, run_id=body.run_id, title=body.title
    )
    memo_id = f"memo_{uuid.uuid4().hex[:12]}"
    source_json = {
        "baseline_id": None,
        "baseline_version": None,
        "run_id": body.run_id,
        "scenario_id": None,
    }
    sections_json: list[dict[str, Any]] = []
    store.save(
        x_tenant_id,
        MEMO_ARTIFACT_TYPE,
        memo_id,
        {"html": html, "memo_type": body.memo_type, "source": source_json},
    )
    outputs_json = {"html_path": f"{x_tenant_id}/{MEMO_ARTIFACT_TYPE}/{memo_id}"}

    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            """INSERT INTO memo_packs (tenant_id, memo_id, memo_type, title, source_json, sections_json, outputs_json, status, created_by)
               VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb, 'ready', $8)""",
            x_tenant_id,
            memo_id,
            body.memo_type,
            body.title or f"{body.memo_type.replace('_', ' ').title()} — {body.run_id}",
            json.dumps(source_json),
            json.dumps(sections_json),
            json.dumps(outputs_json),
            x_user_id or None,
        )
    return {
        "memo_id": memo_id,
        "memo_type": body.memo_type,
        "run_id": body.run_id,
        "status": "ready",
    }


@router.get("")
async def list_memos(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    memo_type: str | None = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List memo packs for the tenant."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        if memo_type:
            rows = await conn.fetch(
                """SELECT memo_id, memo_type, title, source_json, status, created_at
                   FROM memo_packs WHERE tenant_id = $1 AND memo_type = $2 ORDER BY created_at DESC LIMIT $3 OFFSET $4""",
                x_tenant_id,
                memo_type,
                limit,
                offset,
            )
        else:
            rows = await conn.fetch(
                """SELECT memo_id, memo_type, title, source_json, status, created_at
                   FROM memo_packs WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
                x_tenant_id,
                limit,
                offset,
            )
    items = [
        {
            "memo_id": r["memo_id"],
            "memo_type": r["memo_type"],
            "title": r["title"],
            "source_json": r["source_json"] if isinstance(r["source_json"], dict) else json.loads(r["source_json"] or "{}"),
            "status": r["status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/{memo_id}")
async def get_memo(
    memo_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get memo metadata."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT memo_id, memo_type, title, source_json, sections_json, outputs_json, status, created_at
               FROM memo_packs WHERE tenant_id = $1 AND memo_id = $2""",
            x_tenant_id,
            memo_id,
        )
    if not row:
        raise HTTPException(404, "Memo not found")
    return {
        "memo_id": row["memo_id"],
        "memo_type": row["memo_type"],
        "title": row["title"],
        "source_json": row["source_json"] if isinstance(row["source_json"], dict) else json.loads(row["source_json"] or "{}"),
        "sections_json": row["sections_json"] if isinstance(row["sections_json"], list) else json.loads(row["sections_json"] or "[]"),
        "outputs_json": row["outputs_json"] if isinstance(row["outputs_json"], dict) else json.loads(row["outputs_json"] or "{}"),
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.get("/{memo_id}/download")
async def download_memo(
    memo_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    download_format: str = Query("html", alias="format", description="html or pdf"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> Response:
    """Download memo as HTML or PDF (VA-P5-03)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if download_format not in ("html", "pdf"):
        raise HTTPException(400, "format must be html or pdf")
    try:
        data = store.load(x_tenant_id, MEMO_ARTIFACT_TYPE, memo_id)
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Memo not found") from e
        raise
    html = data.get("html", "")
    if download_format == "html":
        return HTMLResponse(
            content=html,
            headers={"Content-Disposition": f'attachment; filename="{memo_id}.html"'},
        )  # type: ignore[arg-type]
    try:
        pdf_bytes = html_to_pdf(html)
    except RuntimeError as e:
        raise HTTPException(501, str(e)) from e
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{memo_id}.pdf"'},
    )


@router.delete("/{memo_id}")
async def delete_memo(
    memo_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Delete a memo pack."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        result = await conn.execute(
            "DELETE FROM memo_packs WHERE tenant_id = $1 AND memo_id = $2",
            x_tenant_id,
            memo_id,
        )
    if result == "DELETE 0":
        raise HTTPException(404, "Memo not found")
    return {"memo_id": memo_id, "deleted": True}
