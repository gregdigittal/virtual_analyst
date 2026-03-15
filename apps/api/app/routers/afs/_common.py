"""Shared imports, constants, ID generators, and Pydantic models for the AFS router package."""

from __future__ import annotations

import asyncio  # noqa: F401
import base64  # noqa: F401
import json  # noqa: F401
import re  # noqa: F401
import uuid
from pathlib import Path
from typing import Any  # noqa: F401

from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile  # noqa: F401
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn  # noqa: F401
from apps.api.app.deps import get_artifact_store, get_llm_router  # noqa: F401
from apps.api.app.services.afs.analytics_ai import (  # noqa: F401
    assess_going_concern,
    detect_anomalies,
    generate_commentary,
)
from apps.api.app.services.afs.disclosure_drafter import (  # noqa: F401
    draft_section,
    validate_sections,
)
from apps.api.app.services.afs.output_generator import (  # noqa: F401
    generate_docx,
    generate_ixbrl,
    generate_pdf_html,
)
from apps.api.app.services.afs.pdf_extractor import extract_pdf, sections_to_json  # noqa: F401
from apps.api.app.services.afs.ratio_calculator import compute_from_tb  # noqa: F401
from apps.api.app.services.afs.tb_parser import (  # noqa: F401
    parse_csv_tb,
    parse_excel_tb,
    tb_accounts_to_json,
)
from apps.api.app.services.llm.router import LLMRouter  # noqa: F401
from shared.fm_shared.storage import ArtifactStore  # noqa: F401

# ---------------------------------------------------------------------------
# Benchmark & schema file loading
# ---------------------------------------------------------------------------

# _common.py lives at routers/afs/_common.py
# parent        = routers/afs/
# parent.parent = routers/
# parent.parent.parent = app/
_BENCHMARKS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "industry_benchmarks.json"
_BENCHMARKS_CACHE: dict | None = None


def _load_benchmarks() -> dict:
    global _BENCHMARKS_CACHE
    if _BENCHMARKS_CACHE is None:
        with open(_BENCHMARKS_PATH) as f:
            _BENCHMARKS_CACHE = json.load(f)
    return _BENCHMARKS_CACHE


_SCHEMAS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "framework_schemas.json"
_SCHEMAS_CACHE: dict | None = None


def _load_schemas() -> dict:
    global _SCHEMAS_CACHE
    if _SCHEMAS_CACHE is None:
        with open(_SCHEMAS_PATH) as f:
            _SCHEMAS_CACHE = json.load(f)
    return _SCHEMAS_CACHE


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

# Ingestion constants
AFS_ARTIFACT_TYPE = "afs_files"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# Disclosure
VALID_SECTION_TYPES = {"note", "statement", "directors_report", "accounting_policy"}

# Review
VALID_REVIEW_STAGES = {"preparer_review", "manager_review", "partner_signoff"}

# Tax
VALID_DIFF_TYPES = {"asset", "liability"}

# Output
VALID_OUTPUT_FORMATS = {"pdf", "docx", "ixbrl"}

# ---------------------------------------------------------------------------
# ID generators
# ---------------------------------------------------------------------------


def _framework_id() -> str:
    return f"afw_{uuid.uuid4().hex[:14]}"


def _engagement_id() -> str:
    return f"aen_{uuid.uuid4().hex[:14]}"


def _disclosure_item_id() -> str:
    return f"adi_{uuid.uuid4().hex[:14]}"


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


def _consolidation_id() -> str:
    return f"acr_{uuid.uuid4().hex[:14]}"


def _analytics_id() -> str:
    return f"aan_{uuid.uuid4().hex[:14]}"


def _output_id() -> str:
    return f"afo_{uuid.uuid4().hex[:14]}"


# ---------------------------------------------------------------------------
# Pydantic models — frameworks
# ---------------------------------------------------------------------------


class CreateFrameworkBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    standard: str = Field(...)  # ifrs, ifrs_sme, us_gaap, sa_companies_act, custom
    version: str = Field(default="1.0", max_length=32)
    jurisdiction: str | None = Field(default=None, max_length=128)
    disclosure_schema_json: dict | None = None
    statement_templates_json: dict | None = None


class InferFrameworkBody(BaseModel):
    description: str = Field(..., min_length=10, max_length=2000)
    jurisdiction: str | None = None
    entity_type: str | None = None


class CreateDisclosureItemBody(BaseModel):
    section: str = Field(..., min_length=1)
    reference: str | None = None
    description: str = Field(..., min_length=1)
    required: bool = True
    applicable_entity_types: list[str] | None = None


# ---------------------------------------------------------------------------
# Pydantic models — engagements
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Pydantic models — ingestion
# ---------------------------------------------------------------------------


class SetBaseSourceBody(BaseModel):
    base_source: str = Field(...)  # pdf, excel, va_baseline


class ResolveDiscrepancyBody(BaseModel):
    resolution: str = Field(...)  # use_pdf, use_excel, noted
    resolution_note: str = Field(default="", max_length=2000)


class CreateProjectionBody(BaseModel):
    month: str = Field(..., min_length=7, max_length=7)  # YYYY-MM
    basis_description: str = Field(..., min_length=1, max_length=2000)


# ---------------------------------------------------------------------------
# Pydantic models — disclosure
# ---------------------------------------------------------------------------


class DraftSectionBody(BaseModel):
    section_type: str = Field(default="note")
    title: str = Field(..., min_length=1, max_length=500)
    nl_instruction: str = Field(..., min_length=1, max_length=10000)


class UpdateSectionBody(BaseModel):
    nl_instruction: str | None = Field(default=None, max_length=10000)
    content_json: dict | None = None
    title: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Pydantic models — review
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Pydantic models — tax
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Pydantic models — consolidation
# ---------------------------------------------------------------------------


class LinkOrgBody(BaseModel):
    org_id: str = Field(..., min_length=1)
    reporting_currency: str = Field(default="ZAR", pattern=r"^[A-Z]{3}$")
    fx_avg_rates: dict[str, float] = Field(default_factory=dict)
    fx_closing_rates: dict[str, float] | None = None


class ConsolidateBody(BaseModel):
    fx_avg_rates: dict[str, float] | None = None
    fx_closing_rates: dict[str, float] | None = None


# ---------------------------------------------------------------------------
# Pydantic models — outputs
# ---------------------------------------------------------------------------


class GenerateOutputBody(BaseModel):
    format: str = Field(...)  # pdf, docx, ixbrl


# ---------------------------------------------------------------------------
# Pydantic models — analytics
# ---------------------------------------------------------------------------


class ComputeAnalyticsBody(BaseModel):
    industry_segment: str = Field(default="general", pattern=r"^[a-z_]+$")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _validate_engagement(row: Any, engagement_id: str) -> None:
    """Raise 404 if engagement not found."""
    if not row:
        raise HTTPException(404, f"Engagement {engagement_id} not found")
