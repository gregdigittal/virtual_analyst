"""AFS (Annual Financial Statements) module — frameworks & engagements CRUD (Phase 1, Task 2)."""

from __future__ import annotations

import base64
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_artifact_store, require_role, ROLES_CAN_WRITE
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/afs", tags=["afs"], dependencies=[require_role(*ROLES_CAN_WRITE)])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STANDARDS = {"ifrs", "ifrs_sme", "us_gaap", "sa_companies_act", "custom"}
VALID_STATUSES = {"setup", "ingestion", "drafting", "review", "approved", "published"}
VALID_BASE_SOURCES = {"pdf", "excel", "va_baseline"}

BUILTIN_FRAMEWORKS = [
    {"name": "IFRS (Full)", "standard": "ifrs", "version": "2025", "jurisdiction": "International"},
    {"name": "IFRS for SMEs", "standard": "ifrs_sme", "version": "2025", "jurisdiction": "International"},
    {"name": "US GAAP", "standard": "us_gaap", "version": "2025", "jurisdiction": "United States"},
    {"name": "SA Companies Act / GAAP", "standard": "sa_companies_act", "version": "2025", "jurisdiction": "South Africa"},
]

# ---------------------------------------------------------------------------
# ID generators
# ---------------------------------------------------------------------------


def _framework_id() -> str:
    return f"afw_{uuid.uuid4().hex[:14]}"


def _engagement_id() -> str:
    return f"aen_{uuid.uuid4().hex[:14]}"


def _disclosure_item_id() -> str:
    return f"adi_{uuid.uuid4().hex[:14]}"


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CreateFrameworkBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    standard: str = Field(...)  # ifrs, ifrs_sme, us_gaap, sa_companies_act, custom
    version: str = Field(default="1.0", max_length=32)
    jurisdiction: str | None = Field(default=None, max_length=128)
    disclosure_schema_json: dict | None = None
    statement_templates_json: dict | None = None


class CreateEngagementBody(BaseModel):
    entity_name: str = Field(..., min_length=1, max_length=255)
    framework_id: str = Field(..., min_length=1)
    period_start: str = Field(...)  # ISO date YYYY-MM-DD
    period_end: str = Field(...)
    prior_engagement_id: str | None = None


class UpdateEngagementBody(BaseModel):
    entity_name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = None
    base_source: str | None = None


# ===========================================================================
# Frameworks
# ===========================================================================


@router.get("/frameworks")
async def list_frameworks(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List all frameworks for the tenant (built-in + custom)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            "SELECT * FROM afs_frameworks WHERE tenant_id = $1 ORDER BY is_builtin DESC, name",
            x_tenant_id,
        )
        return {"items": [dict(r) for r in rows]}


@router.post("/frameworks", status_code=201)
async def create_framework(
    body: CreateFrameworkBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Create a custom framework."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.standard not in VALID_STANDARDS:
        raise HTTPException(400, f"Invalid standard; must be one of {sorted(VALID_STANDARDS)}")

    fid = _framework_id()
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO afs_frameworks
               (tenant_id, framework_id, name, standard, version, jurisdiction,
                disclosure_schema_json, statement_templates_json, is_builtin, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, false, $9)
               RETURNING *""",
            x_tenant_id,
            fid,
            body.name,
            body.standard,
            body.version,
            body.jurisdiction,
            json.dumps(body.disclosure_schema_json) if body.disclosure_schema_json else None,
            json.dumps(body.statement_templates_json) if body.statement_templates_json else None,
            x_user_id or None,
        )
        return dict(row)


@router.get("/frameworks/{framework_id}")
async def get_framework(
    framework_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get a single framework by ID."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM afs_frameworks WHERE tenant_id = $1 AND framework_id = $2",
            x_tenant_id,
            framework_id,
        )
        if not row:
            raise HTTPException(404, "Framework not found")
        return dict(row)


@router.get("/frameworks/{framework_id}/checklist")
async def list_disclosure_items(
    framework_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List disclosure checklist items for a framework."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            "SELECT * FROM afs_disclosure_items WHERE tenant_id = $1 AND framework_id = $2 ORDER BY section, reference",
            x_tenant_id,
            framework_id,
        )
        return {"items": [dict(r) for r in rows]}


@router.post("/frameworks/seed")
async def seed_builtin_frameworks(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Seed the 4 built-in accounting frameworks for this tenant."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    seeded = 0
    async with tenant_conn(x_tenant_id) as conn:
        for fw in BUILTIN_FRAMEWORKS:
            fid = _framework_id()
            result = await conn.execute(
                """INSERT INTO afs_frameworks
                   (tenant_id, framework_id, name, standard, version, jurisdiction, is_builtin, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6, true, $7)
                   ON CONFLICT (tenant_id, framework_id) DO NOTHING""",
                x_tenant_id,
                fid,
                fw["name"],
                fw["standard"],
                fw["version"],
                fw["jurisdiction"],
                x_user_id or None,
            )
            # asyncpg returns "INSERT 0 1" or "INSERT 0 0"
            if result and result.endswith("1"):
                seeded += 1

    return {"seeded": seeded, "message": f"Seeded {seeded} built-in framework(s)"}


# ===========================================================================
# Engagements
# ===========================================================================


@router.post("/engagements", status_code=201)
async def create_engagement(
    body: CreateEngagementBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Create a new AFS engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        # Validate framework exists for this tenant
        fw = await conn.fetchrow(
            "SELECT framework_id FROM afs_frameworks WHERE tenant_id = $1 AND framework_id = $2",
            x_tenant_id,
            body.framework_id,
        )
        if not fw:
            raise HTTPException(404, "Framework not found")

        eid = _engagement_id()
        row = await conn.fetchrow(
            """INSERT INTO afs_engagements
               (tenant_id, engagement_id, entity_name, framework_id, period_start, period_end,
                prior_engagement_id, status, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, 'setup', $8)
               RETURNING *""",
            x_tenant_id,
            eid,
            body.entity_name,
            body.framework_id,
            body.period_start,
            body.period_end,
            body.prior_engagement_id,
            x_user_id or None,
        )
        return dict(row)


@router.get("/engagements")
async def list_engagements(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(default=None, description="Filter by engagement status"),
) -> dict[str, Any]:
    """List engagements with pagination and optional status filter."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status; must be one of {sorted(VALID_STATUSES)}")

    async with tenant_conn(x_tenant_id) as conn:
        conditions = ["tenant_id = $1"]
        args: list[Any] = [x_tenant_id]
        idx = 1

        if status:
            idx += 1
            conditions.append(f"status = ${idx}")
            args.append(status)

        where = " AND ".join(conditions)

        # Total count
        total_row = await conn.fetchrow(
            f"SELECT count(*) AS cnt FROM afs_engagements WHERE {where}",
            *args,
        )
        total = total_row["cnt"] if total_row else 0

        # Paginated rows
        idx += 1
        limit_ph = idx
        idx += 1
        offset_ph = idx
        rows = await conn.fetch(
            f"SELECT * FROM afs_engagements WHERE {where} ORDER BY created_at DESC LIMIT ${limit_ph} OFFSET ${offset_ph}",
            *args,
            limit,
            offset,
        )
        return {"items": [dict(r) for r in rows], "total": total}


@router.get("/engagements/{engagement_id}")
async def get_engagement(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get a single engagement by ID."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id,
            engagement_id,
        )
        if not row:
            raise HTTPException(404, "Engagement not found")
        return dict(row)


@router.patch("/engagements/{engagement_id}")
async def update_engagement(
    engagement_id: str,
    body: UpdateEngagementBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Update an engagement (partial). Only non-None fields are applied."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    # Validate status if provided
    if body.status is not None and body.status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status; must be one of {sorted(VALID_STATUSES)}")

    # Validate base_source if provided
    if body.base_source is not None and body.base_source not in VALID_BASE_SOURCES:
        raise HTTPException(400, f"Invalid base_source; must be one of {sorted(VALID_BASE_SOURCES)}")

    async with tenant_conn(x_tenant_id) as conn:
        # Check existence
        existing = await conn.fetchrow(
            "SELECT * FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id,
            engagement_id,
        )
        if not existing:
            raise HTTPException(404, "Engagement not found")

        # Build dynamic SET clause from non-None fields
        updates: list[str] = []
        args: list[Any] = [x_tenant_id, engagement_id]
        idx = 2

        if body.entity_name is not None:
            idx += 1
            updates.append(f"entity_name = ${idx}")
            args.append(body.entity_name)
        if body.status is not None:
            idx += 1
            updates.append(f"status = ${idx}")
            args.append(body.status)
        if body.base_source is not None:
            idx += 1
            updates.append(f"base_source = ${idx}")
            args.append(body.base_source)

        if not updates:
            return dict(existing)

        updates.append("updated_at = now()")
        set_clause = ", ".join(updates)

        row = await conn.fetchrow(
            f"UPDATE afs_engagements SET {set_clause} WHERE tenant_id = $1 AND engagement_id = $2 RETURNING *",
            *args,
        )
        return dict(row)


@router.delete("/engagements/{engagement_id}", status_code=204)
async def delete_engagement(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> None:
    """Delete an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        result = await conn.execute(
            "DELETE FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id,
            engagement_id,
        )
        if result and result.endswith("0"):
            raise HTTPException(404, "Engagement not found")


# ===========================================================================
# Data Ingestion — constants, helpers, models
# ===========================================================================

AFS_ARTIFACT_TYPE = "afs_files"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _tb_id() -> str:
    return f"atb_{uuid.uuid4().hex[:14]}"


def _prior_afs_id() -> str:
    return f"apa_{uuid.uuid4().hex[:14]}"


def _discrepancy_id() -> str:
    return f"asd_{uuid.uuid4().hex[:14]}"


def _projection_id() -> str:
    return f"amp_{uuid.uuid4().hex[:14]}"


class SetBaseSourceBody(BaseModel):
    base_source: str = Field(...)  # pdf, excel, va_baseline


class ResolveDiscrepancyBody(BaseModel):
    resolution: str = Field(...)  # use_pdf, use_excel, noted
    resolution_note: str = Field(default="", max_length=2000)


class CreateProjectionBody(BaseModel):
    month: str = Field(..., min_length=7, max_length=7)  # YYYY-MM
    basis_description: str = Field(..., min_length=1, max_length=2000)


def _validate_engagement(row, engagement_id: str):
    """Raise 404 if engagement not found."""
    if not row:
        raise HTTPException(404, f"Engagement {engagement_id} not found")


# ===========================================================================
# Trial Balance
# ===========================================================================


@router.post("/engagements/{engagement_id}/trial-balance", status_code=201)
async def upload_trial_balance(
    engagement_id: str,
    file: UploadFile,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """Upload a trial balance file (Excel/CSV) for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large; maximum is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    content_type = file.content_type or "application/octet-stream"
    filename = (file.filename or "trial_balance").strip() or "trial_balance"

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
               VALUES ($1, $2, $3, $4, '[]'::jsonb, false)
               RETURNING *""",
            x_tenant_id, tb_id, engagement_id, source,
        )

    store.save(x_tenant_id, AFS_ARTIFACT_TYPE, tb_id, {
        "b64": base64.b64encode(content).decode("ascii"),
        "content_type": content_type,
        "filename": filename,
    })
    return dict(row)


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
            "SELECT * FROM afs_trial_balances WHERE tenant_id = $1 AND engagement_id = $2 ORDER BY created_at DESC",
            x_tenant_id, engagement_id,
        )
        return {"items": [dict(r) for r in rows]}


# ===========================================================================
# Prior AFS
# ===========================================================================


@router.post("/engagements/{engagement_id}/prior-afs", status_code=201)
async def upload_prior_afs(
    engagement_id: str,
    file: UploadFile,
    source_type: str = Query(..., description="Source type: pdf or excel"),
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """Upload a prior AFS file (PDF or Excel) for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if source_type not in {"pdf", "excel"}:
        raise HTTPException(400, "source_type must be 'pdf' or 'excel'")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large; maximum is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    content_type = file.content_type or "application/octet-stream"
    filename = (file.filename or "prior_afs").strip() or "prior_afs"

    pa_id = _prior_afs_id()
    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT engagement_id FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        row = await conn.fetchrow(
            """INSERT INTO afs_prior_afs
               (tenant_id, prior_afs_id, engagement_id, filename, file_size, source_type)
               VALUES ($1, $2, $3, $4, $5, $6)
               RETURNING *""",
            x_tenant_id, pa_id, engagement_id, filename, len(content), source_type,
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
            "SELECT * FROM afs_prior_afs WHERE tenant_id = $1 AND engagement_id = $2 ORDER BY created_at DESC",
            x_tenant_id, engagement_id,
        )
        return {"items": [dict(r) for r in rows]}


# ===========================================================================
# Source Reconciliation & Discrepancies
# ===========================================================================


@router.post("/engagements/{engagement_id}/prior-afs/reconcile")
async def reconcile_prior_afs(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Reconcile prior AFS sources. Phase 1 stub: generates mock discrepancies."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT engagement_id FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        # Check that at least one PDF and one Excel prior AFS exist
        has_pdf = await conn.fetchval(
            "SELECT count(*) FROM afs_prior_afs WHERE tenant_id = $1 AND engagement_id = $2 AND source_type = 'pdf'",
            x_tenant_id, engagement_id,
        )
        has_excel = await conn.fetchval(
            "SELECT count(*) FROM afs_prior_afs WHERE tenant_id = $1 AND engagement_id = $2 AND source_type = 'excel'",
            x_tenant_id, engagement_id,
        )

        if not has_pdf or not has_excel:
            return {"discrepancies": [], "message": "Both PDF and Excel sources required for reconciliation"}

        # Phase 1 stub: generate 3 mock discrepancy rows
        mock_items = [
            {"line_item": "Revenue", "pdf_value": "1200000.00", "excel_value": "1250000.00", "difference": "50000.00"},
            {"line_item": "Total Assets", "pdf_value": "5000000.00", "excel_value": "4980000.00", "difference": "20000.00"},
            {"line_item": "Net Profit", "pdf_value": "350000.00", "excel_value": "340000.00", "difference": "10000.00"},
        ]

        created = []
        for item in mock_items:
            d_id = _discrepancy_id()
            row = await conn.fetchrow(
                """INSERT INTO afs_source_discrepancies
                   (tenant_id, discrepancy_id, engagement_id, line_item, pdf_value, excel_value, difference)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   RETURNING *""",
                x_tenant_id, d_id, engagement_id,
                item["line_item"], item["pdf_value"], item["excel_value"], item["difference"],
            )
            created.append(dict(row))

        return {"discrepancies": created}


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
            "SELECT * FROM afs_source_discrepancies WHERE tenant_id = $1 AND engagement_id = $2 ORDER BY created_at DESC",
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


# ===========================================================================
# Month Projections
# ===========================================================================


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
