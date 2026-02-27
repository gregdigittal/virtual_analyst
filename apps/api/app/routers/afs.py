"""AFS (Annual Financial Statements) module — frameworks & engagements CRUD (Phase 1, Task 2)."""

from __future__ import annotations

import base64
import json
import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_artifact_store, get_llm_router, require_role, ROLES_CAN_WRITE
from apps.api.app.services.afs.tb_parser import parse_excel_tb, parse_csv_tb, tb_accounts_to_json
from apps.api.app.services.afs.pdf_extractor import extract_pdf, sections_to_json
from apps.api.app.services.afs.disclosure_drafter import draft_section, validate_sections
from apps.api.app.services.llm.router import LLMRouter
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


def _section_id() -> str:
    return f"asc_{uuid.uuid4().hex[:14]}"


def _history_id() -> str:
    return f"ash_{uuid.uuid4().hex[:14]}"


def _review_id() -> str:
    return f"arv_{uuid.uuid4().hex[:14]}"


def _review_comment_id() -> str:
    return f"arc_{uuid.uuid4().hex[:14]}"


def _tax_computation_id() -> str:
    return f"atc_{uuid.uuid4().hex[:14]}"


def _temp_difference_id() -> str:
    return f"atd_{uuid.uuid4().hex[:14]}"


class SetBaseSourceBody(BaseModel):
    base_source: str = Field(...)  # pdf, excel, va_baseline


class ResolveDiscrepancyBody(BaseModel):
    resolution: str = Field(...)  # use_pdf, use_excel, noted
    resolution_note: str = Field(default="", max_length=2000)


class CreateProjectionBody(BaseModel):
    month: str = Field(..., min_length=7, max_length=7)  # YYYY-MM
    basis_description: str = Field(..., min_length=1, max_length=2000)


VALID_SECTION_TYPES = {"note", "statement", "directors_report", "accounting_policy"}


class DraftSectionBody(BaseModel):
    section_type: str = Field(default="note")
    title: str = Field(..., min_length=1, max_length=500)
    nl_instruction: str = Field(..., min_length=1, max_length=10000)


class UpdateSectionBody(BaseModel):
    nl_instruction: str | None = Field(default=None, max_length=10000)
    content_json: dict | None = None
    title: str | None = Field(default=None, max_length=500)


# Phase 3 request models
VALID_REVIEW_STAGES = {"preparer_review", "manager_review", "partner_signoff"}
VALID_DIFF_TYPES = {"asset", "liability"}


class SubmitReviewBody(BaseModel):
    stage: str = Field(...)  # preparer_review, manager_review, partner_signoff
    comments: str | None = Field(default=None, max_length=5000)


class ReviewActionBody(BaseModel):
    comments: str | None = Field(default=None, max_length=5000)


class CreateReviewCommentBody(BaseModel):
    review_id: str = Field(..., min_length=1)
    section_id: str | None = None
    parent_comment_id: str | None = None
    body: str = Field(..., min_length=1, max_length=10000)


class TaxComputationBody(BaseModel):
    entity_id: str | None = None
    jurisdiction: str = Field(default="ZA", max_length=10)
    statutory_rate: float = Field(default=0.27, ge=0, le=1)
    taxable_income: float = Field(default=0)
    adjustments: list[dict] | None = None  # [{description, amount}]


class TemporaryDifferenceBody(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    carrying_amount: float = Field(default=0)
    tax_base: float = Field(default=0)
    diff_type: str = Field(default="liability")  # asset or liability


class GenerateTaxNoteBody(BaseModel):
    nl_instruction: str | None = Field(default=None, max_length=5000)


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


# ===========================================================================
# Source Reconciliation & Discrepancies
# ===========================================================================


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


# ===========================================================================
# Sections (AI-drafted disclosure notes)
# ===========================================================================


@router.get("/engagements/{engagement_id}/sections")
async def list_sections(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List all sections for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT engagement_id FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        rows = await conn.fetch(
            """SELECT * FROM afs_sections
               WHERE tenant_id = $1 AND engagement_id = $2
               ORDER BY section_number ASC, created_at ASC""",
            x_tenant_id, engagement_id,
        )
        return {"items": [dict(r) for r in rows]}


@router.post("/engagements/{engagement_id}/sections/draft", status_code=201)
async def draft_new_section(
    engagement_id: str,
    body: DraftSectionBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """AI-draft a new section for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.section_type not in VALID_SECTION_TYPES:
        raise HTTPException(400, f"Invalid section_type; must be one of {sorted(VALID_SECTION_TYPES)}")

    async with tenant_conn(x_tenant_id) as conn:
        # Load engagement with framework info
        eng = await conn.fetchrow(
            """SELECT e.*, f.name AS framework_name, f.standard
               FROM afs_engagements e
               JOIN afs_frameworks f ON e.tenant_id = f.tenant_id AND e.framework_id = f.framework_id
               WHERE e.tenant_id = $1 AND e.engagement_id = $2""",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        # Load trial balance data for context
        tb_row = await conn.fetchrow(
            """SELECT data_json FROM afs_trial_balances
               WHERE tenant_id = $1 AND engagement_id = $2
               ORDER BY uploaded_at DESC LIMIT 1""",
            x_tenant_id, engagement_id,
        )
        tb_summary = ""
        if tb_row and tb_row["data_json"]:
            accounts = tb_row["data_json"] if isinstance(tb_row["data_json"], list) else []
            lines = []
            for acct in accounts[:100]:  # limit context size
                name = acct.get("account_name", "")
                net = acct.get("net", 0)
                lines.append(f"- {name}: {net:,.2f}")
            tb_summary = "\n".join(lines) if lines else "No trial balance data available."

        # Load prior AFS context
        prior_row = await conn.fetchrow(
            """SELECT extracted_json FROM afs_prior_afs
               WHERE tenant_id = $1 AND engagement_id = $2 AND source_type = 'pdf'
               ORDER BY uploaded_at DESC LIMIT 1""",
            x_tenant_id, engagement_id,
        )
        prior_context = ""
        if prior_row and prior_row["extracted_json"]:
            extracted = prior_row["extracted_json"] if isinstance(prior_row["extracted_json"], dict) else {}
            sections = extracted.get("sections", [])
            parts = []
            for s in sections[:10]:
                title = s.get("title", "")
                text = s.get("text", "")[:500]
                parts.append(f"### {title}\n{text}")
            prior_context = "\n\n".join(parts)

        # Call AI drafter
        llm_result = await draft_section(
            llm,
            x_tenant_id,
            framework_name=eng["framework_name"],
            standard=eng["standard"],
            period_start=str(eng["period_start"]),
            period_end=str(eng["period_end"]),
            entity_name=eng["entity_name"],
            section_title=body.title,
            nl_instruction=body.nl_instruction,
            trial_balance_summary=tb_summary,
            prior_afs_context=prior_context,
        )

        # Determine next section number
        max_num = await conn.fetchval(
            """SELECT COALESCE(MAX(section_number), 0) FROM afs_sections
               WHERE tenant_id = $1 AND engagement_id = $2""",
            x_tenant_id, engagement_id,
        )
        section_number = max_num + 1

        # Insert section
        s_id = _section_id()
        content_json = json.dumps(llm_result.content)
        row = await conn.fetchrow(
            """INSERT INTO afs_sections
               (tenant_id, section_id, engagement_id, section_type, section_number,
                title, content_json, version, status, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, 1, 'draft', $8)
               RETURNING *""",
            x_tenant_id, s_id, engagement_id, body.section_type, section_number,
            body.title, content_json, x_user_id or None,
        )

        # Record history
        h_id = _history_id()
        await conn.execute(
            """INSERT INTO afs_section_history
               (tenant_id, history_id, section_id, version,
                content_json, nl_instruction, changed_by)
               VALUES ($1, $2, $3, 1, $4::jsonb, $5, $6)""",
            x_tenant_id, h_id, s_id,
            content_json, body.nl_instruction, x_user_id or None,
        )

        result = dict(row)
        result["llm_cost_usd"] = llm_result.cost_estimate_usd
        result["llm_tokens"] = llm_result.tokens.total_tokens
        return result


@router.get("/engagements/{engagement_id}/sections/{section_id}")
async def get_section(
    engagement_id: str,
    section_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get a single section by ID."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT * FROM afs_sections
               WHERE tenant_id = $1 AND engagement_id = $2 AND section_id = $3""",
            x_tenant_id, engagement_id, section_id,
        )
        if not row:
            raise HTTPException(404, f"Section {section_id} not found")
        return dict(row)


@router.patch("/engagements/{engagement_id}/sections/{section_id}")
async def update_section(
    engagement_id: str,
    section_id: str,
    body: UpdateSectionBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Update a section: manual edit (content_json) or AI re-draft (nl_instruction only)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        existing = await conn.fetchrow(
            """SELECT * FROM afs_sections
               WHERE tenant_id = $1 AND engagement_id = $2 AND section_id = $3""",
            x_tenant_id, engagement_id, section_id,
        )
        if not existing:
            raise HTTPException(404, f"Section {section_id} not found")
        if existing["status"] == "locked":
            raise HTTPException(409, "Section is locked; unlock it before editing")

        new_version = existing["version"] + 1
        new_title = body.title if body.title is not None else existing["title"]
        llm_cost = None
        llm_tokens = None

        if body.nl_instruction and not body.content_json:
            # AI re-draft: load context and call drafter with existing content
            eng = await conn.fetchrow(
                """SELECT e.*, f.name AS framework_name, f.standard
                   FROM afs_engagements e
                   JOIN afs_frameworks f ON e.tenant_id = f.tenant_id AND e.framework_id = f.framework_id
                   WHERE e.tenant_id = $1 AND e.engagement_id = $2""",
                x_tenant_id, engagement_id,
            )
            _validate_engagement(eng, engagement_id)

            # Load TB data
            tb_row = await conn.fetchrow(
                """SELECT data_json FROM afs_trial_balances
                   WHERE tenant_id = $1 AND engagement_id = $2
                   ORDER BY uploaded_at DESC LIMIT 1""",
                x_tenant_id, engagement_id,
            )
            tb_summary = ""
            if tb_row and tb_row["data_json"]:
                accounts = tb_row["data_json"] if isinstance(tb_row["data_json"], list) else []
                lines = []
                for acct in accounts[:100]:
                    name = acct.get("account_name", "")
                    net = acct.get("net", 0)
                    lines.append(f"- {name}: {net:,.2f}")
                tb_summary = "\n".join(lines) if lines else "No trial balance data available."

            # Load prior AFS context
            prior_row = await conn.fetchrow(
                """SELECT extracted_json FROM afs_prior_afs
                   WHERE tenant_id = $1 AND engagement_id = $2 AND source_type = 'pdf'
                   ORDER BY uploaded_at DESC LIMIT 1""",
                x_tenant_id, engagement_id,
            )
            prior_context = ""
            if prior_row and prior_row["extracted_json"]:
                extracted = prior_row["extracted_json"] if isinstance(prior_row["extracted_json"], dict) else {}
                sections = extracted.get("sections", [])
                parts = []
                for s in sections[:10]:
                    title = s.get("title", "")
                    text = s.get("text", "")[:500]
                    parts.append(f"### {title}\n{text}")
                prior_context = "\n\n".join(parts)

            # Pass existing draft for revision
            existing_draft_json = existing["content_json"]
            existing_draft_str = json.dumps(existing_draft_json) if existing_draft_json else None
            llm_result = await draft_section(
                llm,
                x_tenant_id,
                framework_name=eng["framework_name"],
                standard=eng["standard"],
                period_start=str(eng["period_start"]),
                period_end=str(eng["period_end"]),
                entity_name=eng["entity_name"],
                section_title=new_title,
                nl_instruction=body.nl_instruction,
                trial_balance_summary=tb_summary,
                prior_afs_context=prior_context,
                existing_draft=existing_draft_str,
            )
            content_json = json.dumps(llm_result.content)
            nl_instruction = body.nl_instruction
            llm_cost = llm_result.cost_estimate_usd
            llm_tokens = llm_result.tokens.total_tokens
        elif body.content_json is not None:
            # Manual edit
            content_json = json.dumps(body.content_json)
            nl_instruction = body.nl_instruction
        else:
            # Title-only update or no-op
            content_json = json.dumps(existing["content_json"]) if existing["content_json"] else None
            nl_instruction = body.nl_instruction

        row = await conn.fetchrow(
            """UPDATE afs_sections
               SET title = $4, content_json = $5::jsonb,
                   version = $6, updated_at = now()
               WHERE tenant_id = $1 AND engagement_id = $2 AND section_id = $3
               RETURNING *""",
            x_tenant_id, engagement_id, section_id,
            new_title, content_json, new_version,
        )

        # Record history
        h_id = _history_id()
        await conn.execute(
            """INSERT INTO afs_section_history
               (tenant_id, history_id, section_id, version,
                content_json, nl_instruction, changed_by)
               VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)""",
            x_tenant_id, h_id, section_id,
            new_version, content_json, nl_instruction, x_user_id or None,
        )

        result = dict(row)
        if llm_cost is not None:
            result["llm_cost_usd"] = llm_cost
            result["llm_tokens"] = llm_tokens
        return result


@router.post("/engagements/{engagement_id}/sections/{section_id}/lock")
async def lock_section(
    engagement_id: str,
    section_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Lock a section to prevent further edits."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """UPDATE afs_sections
               SET status = 'locked', updated_at = now()
               WHERE tenant_id = $1 AND engagement_id = $2 AND section_id = $3
               RETURNING *""",
            x_tenant_id, engagement_id, section_id,
        )
        if not row:
            raise HTTPException(404, f"Section {section_id} not found")
        return dict(row)


@router.post("/engagements/{engagement_id}/sections/{section_id}/unlock")
async def unlock_section(
    engagement_id: str,
    section_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Unlock a section to allow edits."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """UPDATE afs_sections
               SET status = 'draft', updated_at = now()
               WHERE tenant_id = $1 AND engagement_id = $2 AND section_id = $3
               RETURNING *""",
            x_tenant_id, engagement_id, section_id,
        )
        if not row:
            raise HTTPException(404, f"Section {section_id} not found")
        return dict(row)


@router.post("/engagements/{engagement_id}/validate")
async def validate_engagement_sections(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Validate all sections against the disclosure checklist via AI."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        # Load engagement with framework
        eng = await conn.fetchrow(
            """SELECT e.*, f.name AS framework_name, f.standard
               FROM afs_engagements e
               JOIN afs_frameworks f ON e.tenant_id = f.tenant_id AND e.framework_id = f.framework_id
               WHERE e.tenant_id = $1 AND e.engagement_id = $2""",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        # Load all sections
        section_rows = await conn.fetch(
            """SELECT section_type, section_number, title, content_json
               FROM afs_sections
               WHERE tenant_id = $1 AND engagement_id = $2
               ORDER BY section_number ASC""",
            x_tenant_id, engagement_id,
        )

        if not section_rows:
            raise HTTPException(400, "No sections to validate; draft sections first")

        # Build sections summary
        parts = []
        for s in section_rows:
            content = s["content_json"] if s["content_json"] else {}
            title = content.get("title", s["title"]) if isinstance(content, dict) else s["title"]
            paragraphs = content.get("paragraphs", []) if isinstance(content, dict) else []
            text_preview = " ".join(
                p.get("content", "")[:200] for p in paragraphs[:5]
            ) if paragraphs else "(empty)"
            parts.append(f"### {s['section_number']}. {title}\n{text_preview}")
        sections_summary = "\n\n".join(parts)

        # Load disclosure checklist
        checklist_rows = await conn.fetch(
            """SELECT section, reference, description, required
               FROM afs_disclosure_items
               WHERE tenant_id = $1 AND framework_id = $2
               ORDER BY section, reference""",
            x_tenant_id, eng["framework_id"],
        )

        checklist_parts = []
        for item in checklist_rows:
            mandatory = " [MANDATORY]" if item["required"] else ""
            checklist_parts.append(f"- {item['reference']}: {item['description']}{mandatory}")
        checklist_items = "\n".join(checklist_parts) if checklist_parts else "No disclosure checklist items found."

        # Call AI validator
        llm_result = await validate_sections(
            llm,
            x_tenant_id,
            framework_name=eng["framework_name"],
            standard=eng["standard"],
            sections_summary=sections_summary,
            checklist_items=checklist_items,
        )

        result = {**llm_result.content}
        result["llm_cost_usd"] = llm_result.cost_estimate_usd
        result["llm_tokens"] = llm_result.tokens.total_tokens
        result["sections_validated"] = len(section_rows)
        result["checklist_items_checked"] = len(checklist_rows)
        return result


# ===========================================================================
# Review Workflow (Phase 3)
# ===========================================================================


@router.post("/engagements/{engagement_id}/reviews/submit", status_code=201)
async def submit_review(
    engagement_id: str,
    body: SubmitReviewBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Submit engagement for review at a given stage."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.stage not in VALID_REVIEW_STAGES:
        raise HTTPException(400, f"Invalid stage '{body.stage}'. Must be one of: {', '.join(sorted(VALID_REVIEW_STAGES))}")

    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT * FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        # Verify all sections are reviewed or locked (none in draft)
        draft_count = await conn.fetchval(
            """SELECT count(*) FROM afs_sections
               WHERE tenant_id = $1 AND engagement_id = $2 AND status = 'draft'""",
            x_tenant_id, engagement_id,
        )
        if draft_count and draft_count > 0:
            raise HTTPException(400, f"{draft_count} section(s) still in draft. Review or lock all sections before submitting.")

        # Guard against duplicate pending review for the same stage
        existing = await conn.fetchval(
            """SELECT review_id FROM afs_reviews
               WHERE tenant_id = $1 AND engagement_id = $2 AND stage = $3 AND status = 'pending'""",
            x_tenant_id, engagement_id, body.stage,
        )
        if existing:
            raise HTTPException(409, f"A pending review already exists for stage '{body.stage}'.")

        rid = _review_id()
        row = await conn.fetchrow(
            """INSERT INTO afs_reviews (tenant_id, review_id, engagement_id, stage, status, submitted_by, comments)
               VALUES ($1, $2, $3, $4, 'pending', $5, $6)
               RETURNING *""",
            x_tenant_id, rid, engagement_id, body.stage, x_user_id or None, body.comments,
        )

        # Update engagement status to review
        await conn.execute(
            "UPDATE afs_engagements SET status = 'review', updated_at = now() WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )

        return dict(row)


@router.get("/engagements/{engagement_id}/reviews")
async def list_reviews(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List all reviews for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT * FROM afs_reviews
               WHERE tenant_id = $1 AND engagement_id = $2
               ORDER BY submitted_at DESC""",
            x_tenant_id, engagement_id,
        )
        return {"items": [dict(r) for r in rows]}


@router.post("/engagements/{engagement_id}/reviews/{review_id}/approve")
async def approve_review(
    engagement_id: str,
    review_id: str,
    body: ReviewActionBody | None = None,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Approve a pending review."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        review = await conn.fetchrow(
            "SELECT * FROM afs_reviews WHERE tenant_id = $1 AND review_id = $2 AND engagement_id = $3",
            x_tenant_id, review_id, engagement_id,
        )
        if not review:
            raise HTTPException(404, f"Review {review_id} not found")
        if review["status"] != "pending":
            raise HTTPException(400, f"Review is already '{review['status']}', cannot approve")

        comments = body.comments if body else None
        row = await conn.fetchrow(
            """UPDATE afs_reviews
               SET status = 'approved', reviewed_by = $1, reviewed_at = now(),
                   comments = CASE WHEN $2 IS NOT NULL THEN coalesce(comments || E'\n', '') || $2 ELSE comments END
               WHERE tenant_id = $3 AND review_id = $4
               RETURNING *""",
            x_user_id or None, comments, x_tenant_id, review_id,
        )

        # If partner sign-off approved, update engagement to approved
        if review["stage"] == "partner_signoff":
            await conn.execute(
                "UPDATE afs_engagements SET status = 'approved', updated_at = now() WHERE tenant_id = $1 AND engagement_id = $2",
                x_tenant_id, engagement_id,
            )

        return dict(row)


@router.post("/engagements/{engagement_id}/reviews/{review_id}/reject")
async def reject_review(
    engagement_id: str,
    review_id: str,
    body: ReviewActionBody | None = None,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Reject a pending review."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        review = await conn.fetchrow(
            "SELECT * FROM afs_reviews WHERE tenant_id = $1 AND review_id = $2 AND engagement_id = $3",
            x_tenant_id, review_id, engagement_id,
        )
        if not review:
            raise HTTPException(404, f"Review {review_id} not found")
        if review["status"] != "pending":
            raise HTTPException(400, f"Review is already '{review['status']}', cannot reject")

        comments = body.comments if body else None
        row = await conn.fetchrow(
            """UPDATE afs_reviews
               SET status = 'rejected', reviewed_by = $1, reviewed_at = now(),
                   comments = CASE WHEN $2 IS NOT NULL THEN coalesce(comments || E'\n', '') || $2 ELSE comments END
               WHERE tenant_id = $3 AND review_id = $4
               RETURNING *""",
            x_user_id or None, comments, x_tenant_id, review_id,
        )
        return dict(row)


@router.post("/engagements/{engagement_id}/reviews/comments", status_code=201)
async def create_review_comment(
    engagement_id: str,
    body: CreateReviewCommentBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Add a comment to a review."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        # Verify review belongs to this engagement
        review = await conn.fetchrow(
            "SELECT review_id FROM afs_reviews WHERE tenant_id = $1 AND review_id = $2 AND engagement_id = $3",
            x_tenant_id, body.review_id, engagement_id,
        )
        if not review:
            raise HTTPException(404, f"Review {body.review_id} not found for engagement {engagement_id}")

        cid = _review_comment_id()
        row = await conn.fetchrow(
            """INSERT INTO afs_review_comments
               (tenant_id, comment_id, review_id, section_id, parent_comment_id, body, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               RETURNING *""",
            x_tenant_id, cid, body.review_id, body.section_id, body.parent_comment_id,
            body.body, x_user_id or None,
        )
        return dict(row)


@router.get("/engagements/{engagement_id}/reviews/{review_id}/comments")
async def list_review_comments(
    engagement_id: str,
    review_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List comments for a review."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        # Verify review belongs to this engagement
        review = await conn.fetchrow(
            "SELECT review_id FROM afs_reviews WHERE tenant_id = $1 AND review_id = $2 AND engagement_id = $3",
            x_tenant_id, review_id, engagement_id,
        )
        if not review:
            raise HTTPException(404, f"Review {review_id} not found for engagement {engagement_id}")

        rows = await conn.fetch(
            """SELECT * FROM afs_review_comments
               WHERE tenant_id = $1 AND review_id = $2
               ORDER BY created_at ASC""",
            x_tenant_id, review_id,
        )
        return {"items": [dict(r) for r in rows]}


# ===========================================================================
# Tax Computation (Phase 3)
# ===========================================================================


@router.post("/engagements/{engagement_id}/tax/compute", status_code=201)
async def compute_tax(
    engagement_id: str,
    body: TaxComputationBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Create a tax computation for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT * FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        current_tax = round(body.taxable_income * body.statutory_rate, 2)

        # Build reconciliation from adjustments
        reconciliation = []
        if body.adjustments:
            for adj in body.adjustments:
                desc = adj.get("description", "")
                amount = adj.get("amount", 0)
                effect = round(amount * body.statutory_rate, 2)
                reconciliation.append({"description": desc, "amount": amount, "tax_effect": effect})

        cid = _tax_computation_id()
        row = await conn.fetchrow(
            """INSERT INTO afs_tax_computations
               (tenant_id, computation_id, engagement_id, entity_id, jurisdiction,
                statutory_rate, taxable_income, current_tax, reconciliation_json, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
               RETURNING *""",
            x_tenant_id, cid, engagement_id, body.entity_id, body.jurisdiction,
            body.statutory_rate, body.taxable_income, current_tax,
            json.dumps(reconciliation), x_user_id or None,
        )
        result = dict(row)
        result["temporary_differences"] = []
        return result


@router.get("/engagements/{engagement_id}/tax")
async def list_tax_computations(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List all tax computations for an engagement with their temporary differences."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        comp_rows = await conn.fetch(
            """SELECT * FROM afs_tax_computations
               WHERE tenant_id = $1 AND engagement_id = $2
               ORDER BY created_at DESC""",
            x_tenant_id, engagement_id,
        )
        items = []
        for comp in comp_rows:
            item = dict(comp)
            diff_rows = await conn.fetch(
                """SELECT * FROM afs_temporary_differences
                   WHERE tenant_id = $1 AND computation_id = $2
                   ORDER BY description""",
                x_tenant_id, comp["computation_id"],
            )
            item["temporary_differences"] = [dict(d) for d in diff_rows]
            items.append(item)
        return {"items": items}


@router.post("/engagements/{engagement_id}/tax/{computation_id}/differences", status_code=201)
async def add_temporary_difference(
    engagement_id: str,
    computation_id: str,
    body: TemporaryDifferenceBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Add a temporary difference to a tax computation."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.diff_type not in VALID_DIFF_TYPES:
        raise HTTPException(400, f"Invalid diff_type '{body.diff_type}'. Must be 'asset' or 'liability'")

    async with tenant_conn(x_tenant_id) as conn:
        comp = await conn.fetchrow(
            "SELECT * FROM afs_tax_computations WHERE tenant_id = $1 AND computation_id = $2 AND engagement_id = $3",
            x_tenant_id, computation_id, engagement_id,
        )
        if not comp:
            raise HTTPException(404, f"Tax computation {computation_id} not found")

        difference = round(body.carrying_amount - body.tax_base, 2)
        deferred_tax_effect = round(difference * float(comp["statutory_rate"]), 2)

        did = _temp_difference_id()
        row = await conn.fetchrow(
            """INSERT INTO afs_temporary_differences
               (tenant_id, difference_id, computation_id, description,
                carrying_amount, tax_base, difference, deferred_tax_effect, diff_type)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               RETURNING *""",
            x_tenant_id, did, computation_id, body.description,
            body.carrying_amount, body.tax_base, difference, deferred_tax_effect, body.diff_type,
        )

        # Update deferred_tax_json totals on the computation
        all_diffs = await conn.fetch(
            "SELECT * FROM afs_temporary_differences WHERE tenant_id = $1 AND computation_id = $2",
            x_tenant_id, computation_id,
        )
        total_assets = sum(float(d["deferred_tax_effect"]) for d in all_diffs if d["diff_type"] == "asset")
        total_liabilities = sum(float(d["deferred_tax_effect"]) for d in all_diffs if d["diff_type"] == "liability")
        deferred_json = {
            "total_deferred_tax_asset": round(total_assets, 2),
            "total_deferred_tax_liability": round(total_liabilities, 2),
            "net_deferred_tax": round(total_assets - total_liabilities, 2),
        }
        await conn.execute(
            "UPDATE afs_tax_computations SET deferred_tax_json = $1::jsonb, updated_at = now() WHERE tenant_id = $2 AND computation_id = $3",
            json.dumps(deferred_json), x_tenant_id, computation_id,
        )

        return dict(row)


@router.post("/engagements/{engagement_id}/tax/{computation_id}/generate-note")
async def generate_tax_note(
    engagement_id: str,
    computation_id: str,
    body: GenerateTaxNoteBody | None = None,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Generate an AI-drafted tax note for a computation."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        # Load computation
        comp = await conn.fetchrow(
            "SELECT * FROM afs_tax_computations WHERE tenant_id = $1 AND computation_id = $2 AND engagement_id = $3",
            x_tenant_id, computation_id, engagement_id,
        )
        if not comp:
            raise HTTPException(404, f"Tax computation {computation_id} not found")

        # Load engagement + framework
        eng = await conn.fetchrow(
            """SELECT e.*, f.name AS framework_name, f.standard
               FROM afs_engagements e
               JOIN afs_frameworks f ON e.tenant_id = f.tenant_id AND e.framework_id = f.framework_id
               WHERE e.tenant_id = $1 AND e.engagement_id = $2""",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        # Load temporary differences
        diff_rows = await conn.fetch(
            "SELECT * FROM afs_temporary_differences WHERE tenant_id = $1 AND computation_id = $2 ORDER BY description",
            x_tenant_id, computation_id,
        )
        differences = [dict(d) for d in diff_rows]

        # Import and call AI drafter
        from apps.api.app.services.afs.tax_note_drafter import draft_tax_note

        nl_instruction = body.nl_instruction if body else None
        llm_result = await draft_tax_note(
            llm_router=llm,
            tenant_id=x_tenant_id,
            framework_name=eng["framework_name"],
            standard=eng["standard"],
            computation=dict(comp),
            differences=differences,
            nl_instruction=nl_instruction,
        )

        tax_note = {**llm_result.content}

        # Save to computation
        row = await conn.fetchrow(
            """UPDATE afs_tax_computations
               SET tax_note_json = $1::jsonb, updated_at = now()
               WHERE tenant_id = $2 AND computation_id = $3
               RETURNING *""",
            json.dumps(tax_note), x_tenant_id, computation_id,
        )
        result = dict(row)
        result["temporary_differences"] = differences
        result["llm_cost_usd"] = llm_result.cost_estimate_usd
        result["llm_tokens"] = llm_result.tokens.total_tokens
        return result
