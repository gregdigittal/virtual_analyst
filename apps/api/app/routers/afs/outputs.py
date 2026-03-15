"""AFS output generation endpoints."""

from __future__ import annotations

import base64
import re
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_artifact_store
from apps.api.app.routers.afs._common import (
    VALID_OUTPUT_FORMATS,
    GenerateOutputBody,
    _output_id,
    _validate_engagement,
)
from apps.api.app.services.afs.output_generator import (
    generate_docx,
    generate_ixbrl,
    generate_pdf_html,
)
from shared.fm_shared.storage import ArtifactStore

router = APIRouter()


@router.post("/engagements/{engagement_id}/outputs/generate", status_code=201)
async def generate_output(
    engagement_id: str,
    body: GenerateOutputBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """Generate an output file (PDF, DOCX, iXBRL) from locked sections."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    fmt = body.format.lower()
    if fmt not in VALID_OUTPUT_FORMATS:
        raise HTTPException(400, f"Invalid format '{fmt}'. Must be one of: {', '.join(sorted(VALID_OUTPUT_FORMATS))}")

    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            """SELECT e.*, f.name AS framework_name, f.standard
               FROM afs_engagements e
               JOIN afs_frameworks f ON e.tenant_id = f.tenant_id AND e.framework_id = f.framework_id
               WHERE e.tenant_id = $1 AND e.engagement_id = $2""",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        # Load locked sections
        sections = await conn.fetch(
            """SELECT * FROM afs_sections
               WHERE tenant_id = $1 AND engagement_id = $2 AND status = 'locked'
               ORDER BY section_number ASC""",
            x_tenant_id, engagement_id,
        )
        if not sections:
            raise HTTPException(400, "No locked sections found. Lock sections before generating output.")

        section_dicts = [dict(s) for s in sections]
        entity_name = eng["entity_name"]
        period_start = str(eng["period_start"])
        period_end = str(eng["period_end"])
        framework_name = eng["framework_name"]
        standard = eng["standard"]

        # Generate
        if fmt == "pdf":
            content_bytes = generate_pdf_html(entity_name, period_start, period_end, framework_name, section_dicts)
            content_type = "text/html"
            ext = "html"
        elif fmt == "docx":
            content_bytes = generate_docx(entity_name, period_start, period_end, framework_name, section_dicts)
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ext = "docx"
        elif fmt == "ixbrl":
            content_bytes = generate_ixbrl(entity_name, period_start, period_end, framework_name, standard, section_dicts)
            content_type = "text/html"
            ext = "html"
        else:
            raise HTTPException(400, f"Unsupported format: {fmt}")

        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", entity_name)[:50]
        filename = f"{safe_name}_AFS_{period_end}.{ext}"

        oid = _output_id()
        store.save(x_tenant_id, "afs_output", oid, {
            "b64": base64.b64encode(content_bytes).decode("ascii"),
            "content_type": content_type,
            "filename": filename,
        })

        row = await conn.fetchrow(
            """INSERT INTO afs_outputs
               (tenant_id, output_id, engagement_id, format, filename,
                file_size_bytes, artifact_key, status, generated_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, 'ready', $8)
               RETURNING *""",
            x_tenant_id, oid, engagement_id, fmt, filename,
            len(content_bytes), oid, x_user_id or None,
        )
        return dict(row)


@router.get("/engagements/{engagement_id}/outputs")
async def list_outputs(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List generated outputs for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT * FROM afs_outputs
               WHERE tenant_id = $1 AND engagement_id = $2
               ORDER BY generated_at DESC""",
            x_tenant_id, engagement_id,
        )
        return {"items": [dict(r) for r in rows]}


@router.get("/engagements/{engagement_id}/outputs/{output_id}/download")
async def download_output(
    engagement_id: str,
    output_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
):
    """Download a generated output file."""
    from fastapi.responses import Response

    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT * FROM afs_outputs
               WHERE tenant_id = $1 AND output_id = $2 AND engagement_id = $3""",
            x_tenant_id, output_id, engagement_id,
        )
        if not row:
            raise HTTPException(404, f"Output {output_id} not found")
        if row["status"] != "ready":
            raise HTTPException(400, f"Output is not ready (status={row['status']})")

    artifact = store.load(x_tenant_id, "afs_output", row["artifact_key"] or output_id)
    if not artifact:
        raise HTTPException(404, "Output file not found in storage")

    content_bytes = base64.b64decode(artifact["b64"])
    content_type = artifact.get("content_type", "application/octet-stream")
    filename = artifact.get("filename", row["filename"])

    return Response(
        content=content_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
