"""AFS ingestion endpoints — trial balance, prior AFS, reconciliation, projections."""

from __future__ import annotations

import base64
import json
import re
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile

from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_artifact_store
from apps.api.app.routers.afs._common import (
    AFS_ARTIFACT_TYPE,
    MAX_UPLOAD_BYTES,
    VALID_BASE_SOURCES,
    CreateProjectionBody,
    ResolveDiscrepancyBody,
    SetBaseSourceBody,
    _discrepancy_id,
    _prior_afs_id,
    _projection_id,
    _tb_id,
    _validate_engagement,
)
from apps.api.app.services.afs.pdf_extractor import extract_pdf, sections_to_json
from apps.api.app.services.afs.tb_parser import parse_csv_tb, parse_excel_tb, tb_accounts_to_json
from shared.fm_shared.storage import ArtifactStore

router = APIRouter()


@router.post("/engagements/{engagement_id}/trial-balance", status_code=201)
async def upload_trial_balance(
    engagement_id: str,
    file: UploadFile,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """Upload a trial balance file (Excel/CSV) for an engagement and parse it."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large; maximum is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    content_type = file.content_type or "application/octet-stream"
    filename = (file.filename or "trial_balance").strip() or "trial_balance"

    # Parse the uploaded file into structured account data
    lower_name = filename.lower()
    if not lower_name.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(400, "Trial balance must be .xlsx, .xls, or .csv")
    if lower_name.endswith(".csv"):
        parse_result = parse_csv_tb(content)
    else:
        parse_result = parse_excel_tb(content, filename)

    data_json = json.dumps(tb_accounts_to_json(parse_result.accounts))

    source = "upload"
    tb_id = _tb_id()
    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT engagement_id FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        row = await conn.fetchrow(
            """INSERT INTO afs_trial_balances
               (tenant_id, trial_balance_id, engagement_id, source, data_json, is_partial)
               VALUES ($1, $2, $3, $4, $5::jsonb, false)
               RETURNING *""",
            x_tenant_id, tb_id, engagement_id, source, data_json,
        )

    store.save(x_tenant_id, AFS_ARTIFACT_TYPE, tb_id, {
        "b64": base64.b64encode(content).decode("ascii"),
        "content_type": content_type,
        "filename": filename,
    })

    result = dict(row)
    result["parse_warnings"] = parse_result.warnings
    result["account_count"] = parse_result.row_count
    return result


@router.get("/engagements/{engagement_id}/trial-balance")
async def list_trial_balances(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List trial balances for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT engagement_id FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        rows = await conn.fetch(
            "SELECT * FROM afs_trial_balances WHERE tenant_id = $1 AND engagement_id = $2 ORDER BY uploaded_at DESC",
            x_tenant_id, engagement_id,
        )
        return {"items": [dict(r) for r in rows]}


@router.post("/engagements/{engagement_id}/prior-afs", status_code=201)
async def upload_prior_afs(
    engagement_id: str,
    file: UploadFile,
    source_type: str = Query(..., description="Source type: pdf or excel"),
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """Upload a prior AFS file (PDF or Excel) and extract structured data."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if source_type not in {"pdf", "excel"}:
        raise HTTPException(400, "source_type must be 'pdf' or 'excel'")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large; maximum is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    content_type = file.content_type or "application/octet-stream"
    filename = (file.filename or "prior_afs").strip() or "prior_afs"

    # Extract structured data from the uploaded file
    if source_type == "pdf":
        pdf_result = extract_pdf(content)
        extracted = {
            "page_count": pdf_result.page_count,
            "sections": sections_to_json(pdf_result.sections),
            "table_count": len(pdf_result.all_tables),
            "warnings": pdf_result.warnings,
        }
    else:
        excel_result = parse_excel_tb(content, filename)
        extracted = {
            "accounts": tb_accounts_to_json(excel_result.accounts),
            "row_count": excel_result.row_count,
            "warnings": excel_result.warnings,
        }

    extracted_json = json.dumps(extracted)

    pa_id = _prior_afs_id()
    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT engagement_id FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        row = await conn.fetchrow(
            """INSERT INTO afs_prior_afs
               (tenant_id, prior_afs_id, engagement_id, filename, file_size, source_type, extracted_json)
               VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
               RETURNING *""",
            x_tenant_id, pa_id, engagement_id, filename, len(content), source_type, extracted_json,
        )

    store.save(x_tenant_id, AFS_ARTIFACT_TYPE, pa_id, {
        "b64": base64.b64encode(content).decode("ascii"),
        "content_type": content_type,
        "filename": filename,
    })
    return dict(row)


@router.get("/engagements/{engagement_id}/prior-afs")
async def list_prior_afs(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List prior AFS uploads for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT engagement_id FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        rows = await conn.fetch(
            "SELECT * FROM afs_prior_afs WHERE tenant_id = $1 AND engagement_id = $2 ORDER BY uploaded_at DESC",
            x_tenant_id, engagement_id,
        )
        return {"items": [dict(r) for r in rows]}


@router.post("/engagements/{engagement_id}/prior-afs/reconcile")
async def reconcile_prior_afs(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Reconcile prior AFS sources by comparing PDF and Excel extracted data."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT engagement_id FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        # Fetch the most recent PDF and Excel prior AFS with extracted data
        pdf_row = await conn.fetchrow(
            """SELECT extracted_json FROM afs_prior_afs
               WHERE tenant_id = $1 AND engagement_id = $2 AND source_type = 'pdf'
               ORDER BY uploaded_at DESC LIMIT 1""",
            x_tenant_id, engagement_id,
        )
        excel_row = await conn.fetchrow(
            """SELECT extracted_json FROM afs_prior_afs
               WHERE tenant_id = $1 AND engagement_id = $2 AND source_type = 'excel'
               ORDER BY uploaded_at DESC LIMIT 1""",
            x_tenant_id, engagement_id,
        )

        if not pdf_row or not excel_row:
            return {"discrepancies": [], "message": "Both PDF and Excel sources required for reconciliation"}

        pdf_extracted = pdf_row["extracted_json"] if pdf_row["extracted_json"] else {}
        excel_extracted = excel_row["extracted_json"] if excel_row["extracted_json"] else {}

        # Build Excel lookup: account name → net value
        excel_accounts: dict[str, float] = {}
        for acct in excel_extracted.get("accounts", []):
            name = acct.get("account_name", "").strip().lower()
            if name:
                excel_accounts[name] = float(acct.get("net", 0))

        # Build PDF lookup: extract line items from section text
        pdf_line_items: dict[str, float] = {}
        for section in pdf_extracted.get("sections", []):
            text = section.get("text", "")
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                # Try to match "Line Item Name ... 1,234,567.89" pattern
                match = re.match(r"^(.+?)\s+([\d,]+(?:\.\d+)?)\s*$", line)
                if match:
                    item_name = match.group(1).strip().lower()
                    try:
                        value = float(match.group(2).replace(",", ""))
                        pdf_line_items[item_name] = value
                    except ValueError:
                        continue

        # Clear existing unresolved discrepancies for this engagement
        await conn.execute(
            """DELETE FROM afs_source_discrepancies
               WHERE tenant_id = $1 AND engagement_id = $2 AND resolved_at IS NULL""",
            x_tenant_id, engagement_id,
        )

        # Compare and insert real discrepancies
        created = []
        all_items = set(excel_accounts.keys()) | set(pdf_line_items.keys())

        for item_name in sorted(all_items):
            excel_val = excel_accounts.get(item_name)
            pdf_val = pdf_line_items.get(item_name)

            if excel_val is not None and pdf_val is not None:
                diff = abs(excel_val - pdf_val)
                if diff > 0.01:
                    d_id = _discrepancy_id()
                    row = await conn.fetchrow(
                        """INSERT INTO afs_source_discrepancies
                           (tenant_id, discrepancy_id, engagement_id, line_item, pdf_value, excel_value, difference)
                           VALUES ($1, $2, $3, $4, $5, $6, $7)
                           RETURNING *""",
                        x_tenant_id, d_id, engagement_id,
                        item_name, round(pdf_val, 2), round(excel_val, 2), round(diff, 2),
                    )
                    created.append(dict(row))

        return {"discrepancies": created, "items_compared": len(all_items)}


@router.post("/engagements/{engagement_id}/base-source")
async def set_base_source(
    engagement_id: str,
    body: SetBaseSourceBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Set the base source for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.base_source not in VALID_BASE_SOURCES:
        raise HTTPException(400, f"Invalid base_source; must be one of {sorted(VALID_BASE_SOURCES)}")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """UPDATE afs_engagements
               SET base_source = $3, updated_at = now()
               WHERE tenant_id = $1 AND engagement_id = $2
               RETURNING *""",
            x_tenant_id, engagement_id, body.base_source,
        )
        if not row:
            raise HTTPException(404, f"Engagement {engagement_id} not found")
        return dict(row)


@router.get("/engagements/{engagement_id}/discrepancies")
async def list_discrepancies(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List source discrepancies for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT engagement_id FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        rows = await conn.fetch(
            "SELECT * FROM afs_source_discrepancies WHERE tenant_id = $1 AND engagement_id = $2 ORDER BY line_item ASC",
            x_tenant_id, engagement_id,
        )
        return {"items": [dict(r) for r in rows]}


@router.patch("/engagements/{engagement_id}/discrepancies/{discrepancy_id}")
async def resolve_discrepancy(
    engagement_id: str,
    discrepancy_id: str,
    body: ResolveDiscrepancyBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Resolve a source discrepancy."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.resolution not in {"use_pdf", "use_excel", "noted"}:
        raise HTTPException(400, "resolution must be one of: use_pdf, use_excel, noted")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """UPDATE afs_source_discrepancies
               SET resolution = $4, resolution_note = $5, resolved_by = $6, resolved_at = now()
               WHERE tenant_id = $1 AND engagement_id = $2 AND discrepancy_id = $3
               RETURNING *""",
            x_tenant_id, engagement_id, discrepancy_id,
            body.resolution, body.resolution_note, x_user_id or None,
        )
        if not row:
            raise HTTPException(404, f"Discrepancy {discrepancy_id} not found")
        return dict(row)


@router.post("/engagements/{engagement_id}/projections", status_code=201)
async def create_projection(
    engagement_id: str,
    body: CreateProjectionBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Create a month projection for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    p_id = _projection_id()
    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT engagement_id FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        row = await conn.fetchrow(
            """INSERT INTO afs_month_projections
               (tenant_id, projection_id, engagement_id, month, basis_description, created_by)
               VALUES ($1, $2, $3, $4, $5, $6)
               RETURNING *""",
            x_tenant_id, p_id, engagement_id, body.month, body.basis_description, x_user_id or None,
        )
        return dict(row)


@router.get("/engagements/{engagement_id}/projections")
async def list_projections(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List month projections for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT engagement_id FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        rows = await conn.fetch(
            "SELECT * FROM afs_month_projections WHERE tenant_id = $1 AND engagement_id = $2 ORDER BY month ASC",
            x_tenant_id, engagement_id,
        )
        return {"items": [dict(r) for r in rows]}
