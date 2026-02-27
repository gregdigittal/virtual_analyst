# AFS Phase 2 — AI Disclosure Drafter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace Phase 1 stubs with real data extraction (Excel parsing, PDF text extraction, AI-powered reconciliation), add the AI Disclosure Drafter (section-by-section NL drafting with LLM), and build the Section Editor frontend page.

**Architecture:** Extend the existing AFS router (`apps/api/app/routers/afs.py`) with new services for Excel TB parsing, PDF text extraction, and AI disclosure drafting. Use the existing `LLMRouter` for provider-agnostic LLM calls with structured output schemas. Add two new DB tables (`afs_sections`, `afs_section_history`) and a new migration. Frontend adds a Section Editor page at `/afs/[id]/sections`.

**Tech Stack:** Python 3.11+ / FastAPI / asyncpg / openpyxl (Excel parsing) / pdfplumber (PDF extraction) / Anthropic Claude via LLMRouter / Next.js 14 App Router / TypeScript / Tailwind CSS with VA design tokens

---

## Task 1: Database Migration — `afs_sections` and `afs_section_history`

**Files:**
- Create: `apps/api/app/db/migrations/0053_afs_sections.sql`

**Step 1: Write the migration**

```sql
-- 0053_afs_sections.sql — AFS Phase 2: sections and section history
-- Tables: afs_sections, afs_section_history

-- ============================================================
-- AFS_SECTIONS (generated statement sections/notes)
-- ============================================================
create table if not exists afs_sections (
  tenant_id text not null references tenants(id) on delete cascade,
  section_id text not null,
  engagement_id text not null,
  section_type text not null check (section_type in ('note','statement','directors_report','accounting_policy')),
  section_number integer not null default 0,
  title text not null,
  content_json jsonb not null default '{}'::jsonb,
  status text not null check (status in ('draft','reviewed','locked')) default 'draft',
  version integer not null default 1,
  created_by text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, section_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_sections_engagement on afs_sections(tenant_id, engagement_id);
create unique index if not exists idx_afs_sections_number on afs_sections(tenant_id, engagement_id, section_number);

-- ============================================================
-- AFS_SECTION_HISTORY (version history per section)
-- ============================================================
create table if not exists afs_section_history (
  tenant_id text not null references tenants(id) on delete cascade,
  history_id text not null,
  section_id text not null,
  version integer not null,
  content_json jsonb not null default '{}'::jsonb,
  nl_instruction text,
  changed_by text references users(id) on delete set null,
  changed_at timestamptz not null default now(),
  primary key (tenant_id, history_id),
  foreign key (tenant_id, section_id) references afs_sections(tenant_id, section_id) on delete cascade
);
create index if not exists idx_afs_section_history_section on afs_section_history(tenant_id, section_id);

-- ============================================================
-- RLS
-- ============================================================
alter table afs_sections enable row level security;
drop policy if exists "afs_sections_select" on afs_sections;
drop policy if exists "afs_sections_insert" on afs_sections;
drop policy if exists "afs_sections_update" on afs_sections;
drop policy if exists "afs_sections_delete" on afs_sections;
create policy "afs_sections_select" on afs_sections for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_sections_insert" on afs_sections for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_sections_update" on afs_sections for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_sections_delete" on afs_sections for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table afs_section_history enable row level security;
drop policy if exists "afs_section_history_select" on afs_section_history;
drop policy if exists "afs_section_history_insert" on afs_section_history;
drop policy if exists "afs_section_history_update" on afs_section_history;
drop policy if exists "afs_section_history_delete" on afs_section_history;
create policy "afs_section_history_select" on afs_section_history for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_section_history_insert" on afs_section_history for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_section_history_update" on afs_section_history for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_section_history_delete" on afs_section_history for delete using (tenant_id = current_setting('app.tenant_id', true));
```

**Step 2: Verify migration file is valid SQL**

Run: `cd apps/api && python -c "open('app/db/migrations/0053_afs_sections.sql').read(); print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add apps/api/app/db/migrations/0053_afs_sections.sql
git commit -m "feat(afs): add migration 0053 for sections and section_history tables"
```

---

## Task 2: Excel Trial Balance Parser Service

**Files:**
- Create: `apps/api/app/services/afs/__init__.py`
- Create: `apps/api/app/services/afs/tb_parser.py`

**Context:** Phase 1 uploads Excel trial balances but stores `data_json` as empty `[]`. This task creates a service that actually parses the Excel file into structured account data using `openpyxl` (already used by `apps/api/app/services/excel_parser.py`).

**Step 1: Create the `__init__.py`**

Create `apps/api/app/services/afs/__init__.py` — empty file.

**Step 2: Write the trial balance parser**

Create `apps/api/app/services/afs/tb_parser.py`:

```python
"""Parse uploaded Excel/CSV trial balance files into structured account data."""

from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass
from typing import Any

import openpyxl


@dataclass
class TBAccount:
    """A single trial balance line item."""
    gl_code: str
    account_name: str
    debit: float
    credit: float
    net: float  # debit - credit (positive = debit balance)


@dataclass
class TBParseResult:
    """Result of parsing a trial balance file."""
    accounts: list[TBAccount]
    sheet_name: str | None
    row_count: int
    warnings: list[str]


# Heuristic column header patterns (case-insensitive)
_GL_HEADERS = {"gl code", "gl_code", "account code", "account_code", "acc code", "code", "gl", "account number", "acc no"}
_NAME_HEADERS = {"account name", "account_name", "description", "name", "account", "account description", "gl description"}
_DEBIT_HEADERS = {"debit", "dr", "debit amount", "debit_amount"}
_CREDIT_HEADERS = {"credit", "cr", "credit amount", "credit_amount"}
_BALANCE_HEADERS = {"balance", "net", "amount", "total", "net amount", "closing balance"}


def _detect_columns(headers: list[str]) -> dict[str, int | None]:
    """Detect column indices from header row using heuristic matching."""
    lower = [h.strip().lower() if h else "" for h in headers]
    result: dict[str, int | None] = {"gl_code": None, "name": None, "debit": None, "credit": None, "balance": None}

    for i, h in enumerate(lower):
        if h in _GL_HEADERS and result["gl_code"] is None:
            result["gl_code"] = i
        elif h in _NAME_HEADERS and result["name"] is None:
            result["name"] = i
        elif h in _DEBIT_HEADERS and result["debit"] is None:
            result["debit"] = i
        elif h in _CREDIT_HEADERS and result["credit"] is None:
            result["credit"] = i
        elif h in _BALANCE_HEADERS and result["balance"] is None:
            result["balance"] = i

    return result


def _safe_float(val: Any) -> float:
    """Convert a cell value to float, defaulting to 0.0."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        cleaned = str(val).replace(",", "").replace(" ", "").strip()
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        return float(cleaned) if cleaned else 0.0
    except (ValueError, TypeError):
        return 0.0


def parse_excel_tb(file_bytes: bytes, filename: str = "tb.xlsx") -> TBParseResult:
    """Parse an Excel trial balance into structured accounts.

    Heuristics:
    1. Find the first sheet with recognisable TB headers.
    2. Detect GL code, account name, debit, credit (or single balance) columns.
    3. Extract rows, skipping blanks and totals.
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    warnings: list[str] = []

    for sheet in wb.sheetnames:
        ws = wb[sheet]
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            continue

        # Try first 5 rows as potential header rows
        for header_idx in range(min(5, len(rows))):
            headers = [str(c) if c is not None else "" for c in rows[header_idx]]
            cols = _detect_columns(headers)

            if cols["name"] is None:
                continue  # Must at least have account name

            # Parse data rows
            accounts: list[TBAccount] = []
            for row in rows[header_idx + 1:]:
                cells = list(row)
                name_val = cells[cols["name"]] if cols["name"] is not None and cols["name"] < len(cells) else None
                if not name_val or not str(name_val).strip():
                    continue

                name_str = str(name_val).strip()
                # Skip total/subtotal rows
                if name_str.lower().startswith(("total", "sub-total", "subtotal", "grand total")):
                    continue

                gl = ""
                if cols["gl_code"] is not None and cols["gl_code"] < len(cells):
                    gl_val = cells[cols["gl_code"]]
                    gl = str(gl_val).strip() if gl_val is not None else ""

                if cols["debit"] is not None and cols["credit"] is not None:
                    debit = _safe_float(cells[cols["debit"]] if cols["debit"] < len(cells) else None)
                    credit = _safe_float(cells[cols["credit"]] if cols["credit"] < len(cells) else None)
                    net = debit - credit
                elif cols["balance"] is not None:
                    bal = _safe_float(cells[cols["balance"]] if cols["balance"] < len(cells) else None)
                    debit = bal if bal >= 0 else 0.0
                    credit = abs(bal) if bal < 0 else 0.0
                    net = bal
                else:
                    warnings.append(f"Row '{name_str}': no numeric columns detected, skipping")
                    continue

                accounts.append(TBAccount(gl_code=gl, account_name=name_str, debit=debit, credit=credit, net=net))

            if accounts:
                if cols["gl_code"] is None:
                    warnings.append("GL code column not detected; codes will be empty")
                wb.close()
                return TBParseResult(accounts=accounts, sheet_name=sheet, row_count=len(accounts), warnings=warnings)

    wb.close()
    return TBParseResult(accounts=[], sheet_name=None, row_count=0, warnings=["No trial balance data detected in any sheet"])


def parse_csv_tb(file_bytes: bytes) -> TBParseResult:
    """Parse a CSV trial balance into structured accounts."""
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if len(rows) < 2:
        return TBParseResult(accounts=[], sheet_name=None, row_count=0, warnings=["CSV file is empty or has only headers"])

    headers = rows[0]
    cols = _detect_columns(headers)
    if cols["name"] is None:
        return TBParseResult(accounts=[], sheet_name=None, row_count=0, warnings=["No account name column detected in CSV"])

    warnings: list[str] = []
    accounts: list[TBAccount] = []
    for row in rows[1:]:
        if cols["name"] >= len(row):
            continue
        name_str = row[cols["name"]].strip()
        if not name_str or name_str.lower().startswith(("total", "sub-total", "subtotal")):
            continue

        gl = row[cols["gl_code"]].strip() if cols["gl_code"] is not None and cols["gl_code"] < len(row) else ""

        if cols["debit"] is not None and cols["credit"] is not None:
            debit = _safe_float(row[cols["debit"]] if cols["debit"] < len(row) else None)
            credit = _safe_float(row[cols["credit"]] if cols["credit"] < len(row) else None)
            net = debit - credit
        elif cols["balance"] is not None:
            bal = _safe_float(row[cols["balance"]] if cols["balance"] < len(row) else None)
            debit = bal if bal >= 0 else 0.0
            credit = abs(bal) if bal < 0 else 0.0
            net = bal
        else:
            continue

        accounts.append(TBAccount(gl_code=gl, account_name=name_str, debit=debit, credit=credit, net=net))

    if cols["gl_code"] is None:
        warnings.append("GL code column not detected; codes will be empty")

    return TBParseResult(accounts=accounts, sheet_name=None, row_count=len(accounts), warnings=warnings)


def tb_accounts_to_json(accounts: list[TBAccount]) -> list[dict[str, Any]]:
    """Convert parsed accounts to JSON-serialisable list."""
    return [asdict(a) for a in accounts]
```

**Step 3: Verify import**

Run: `cd apps/api && python -c "from apps.api.app.services.afs.tb_parser import parse_excel_tb, parse_csv_tb; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add apps/api/app/services/afs/__init__.py apps/api/app/services/afs/tb_parser.py
git commit -m "feat(afs): add trial balance Excel/CSV parser service"
```

---

## Task 3: PDF Text Extraction Service

**Files:**
- Create: `apps/api/app/services/afs/pdf_extractor.py`

**Context:** Phase 1 uploads PDFs but stores `extracted_json` as `null`. This task creates a service that extracts text and tables from PDF files using `pdfplumber`. The extracted text is structured into sections that the AI Disclosure Drafter can reference.

**Step 1: Write the PDF extraction service**

Create `apps/api/app/services/afs/pdf_extractor.py`:

```python
"""Extract text and tables from PDF AFS documents."""

from __future__ import annotations

import io
import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PDFSection:
    """A detected section in the PDF AFS."""
    title: str
    page_start: int
    page_end: int
    text: str
    tables: list[list[list[str]]]  # list of tables, each table is rows of cells


@dataclass
class PDFExtractResult:
    """Result of extracting a PDF AFS."""
    page_count: int
    full_text: str
    sections: list[PDFSection]
    all_tables: list[list[list[str]]]
    warnings: list[str]


# Common AFS section title patterns (case-insensitive)
_SECTION_PATTERNS = [
    r"(?:note[s]?\s+(?:to\s+)?(?:the\s+)?financial\s+statements?)",
    r"(?:directors?['\u2019]?\s+report)",
    r"(?:audit(?:or[s]?)?['\u2019]?\s+report)",
    r"(?:statement\s+of\s+financial\s+position)",
    r"(?:(?:consolidated\s+)?balance\s+sheet)",
    r"(?:statement\s+of\s+(?:comprehensive\s+)?(?:profit\s+(?:or|and)\s+loss|income))",
    r"(?:income\s+statement)",
    r"(?:statement\s+of\s+cash\s*flows?)",
    r"(?:statement\s+of\s+changes\s+in\s+equity)",
    r"(?:accounting\s+policies?)",
    r"(?:note\s+\d+)",
    r"(?:\d+\.\s+[A-Z][a-z])",
]
_SECTION_RE = re.compile("|".join(f"({p})" for p in _SECTION_PATTERNS), re.IGNORECASE)


def extract_pdf(file_bytes: bytes) -> PDFExtractResult:
    """Extract text and tables from a PDF file.

    Uses pdfplumber for text/table extraction.
    Falls back to basic text if pdfplumber is not available.
    """
    try:
        import pdfplumber
    except ImportError:
        return _extract_fallback(file_bytes)

    warnings: list[str] = []
    pages_text: list[str] = []
    all_tables: list[list[list[str]]] = []

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages_text.append(text)

                tables = page.extract_tables()
                for table in tables:
                    cleaned = [[str(cell) if cell is not None else "" for cell in row] for row in table]
                    all_tables.append(cleaned)
    except Exception as e:
        warnings.append(f"PDF extraction error: {str(e)[:200]}")
        return PDFExtractResult(page_count=0, full_text="", sections=[], all_tables=[], warnings=warnings)

    full_text = "\n\n".join(pages_text)

    # Detect sections by scanning for known heading patterns
    sections = _detect_sections(pages_text)

    return PDFExtractResult(
        page_count=page_count,
        full_text=full_text,
        sections=sections,
        all_tables=all_tables,
        warnings=warnings,
    )


def _detect_sections(pages_text: list[str]) -> list[PDFSection]:
    """Detect AFS sections from page text using heading heuristics."""
    sections: list[PDFSection] = []
    current_title = "Preamble"
    current_start = 0
    current_lines: list[str] = []

    for page_idx, page_text in enumerate(pages_text):
        for line in page_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                current_lines.append("")
                continue

            match = _SECTION_RE.search(stripped)
            # Only treat as heading if line is short (likely a title, not body text)
            if match and len(stripped) < 120:
                # Save previous section
                if current_lines:
                    sections.append(PDFSection(
                        title=current_title,
                        page_start=current_start,
                        page_end=page_idx,
                        text="\n".join(current_lines).strip(),
                        tables=[],
                    ))
                current_title = stripped
                current_start = page_idx
                current_lines = []
            else:
                current_lines.append(stripped)

    # Save last section
    if current_lines:
        sections.append(PDFSection(
            title=current_title,
            page_start=current_start,
            page_end=len(pages_text) - 1,
            text="\n".join(current_lines).strip(),
            tables=[],
        ))

    return sections


def _extract_fallback(file_bytes: bytes) -> PDFExtractResult:
    """Fallback extraction using pypdf if pdfplumber is not available."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        full_text = "\n\n".join(pages_text)
        sections = _detect_sections(pages_text)
        return PDFExtractResult(
            page_count=len(reader.pages),
            full_text=full_text,
            sections=sections,
            all_tables=[],
            warnings=["pdfplumber not available; tables not extracted"],
        )
    except ImportError:
        return PDFExtractResult(
            page_count=0,
            full_text="",
            sections=[],
            all_tables=[],
            warnings=["No PDF library available (install pdfplumber or pypdf)"],
        )


def sections_to_json(sections: list[PDFSection]) -> list[dict[str, Any]]:
    """Convert sections to JSON-serialisable list."""
    return [asdict(s) for s in sections]
```

**Step 2: Verify import**

Run: `cd apps/api && python -c "from apps.api.app.services.afs.pdf_extractor import extract_pdf; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add apps/api/app/services/afs/pdf_extractor.py
git commit -m "feat(afs): add PDF text and table extraction service"
```

---

## Task 4: AI Disclosure Drafter Service

**Files:**
- Create: `apps/api/app/services/afs/disclosure_drafter.py`

**Context:** This is the core AI module. It takes an engagement's financial data (trial balance, prior AFS sections), a user's NL instruction, and the applicable accounting framework, then calls the LLM via `LLMRouter.complete_with_routing()` to generate disclosure text. The output is structured JSON with paragraphs and optional tables.

**Step 1: Write the disclosure drafter service**

Create `apps/api/app/services/afs/disclosure_drafter.py`:

```python
"""AI Disclosure Drafter — generates AFS note/section content from NL instructions."""

from __future__ import annotations

import json
from typing import Any

from apps.api.app.services.llm.provider import LLMResponse, Message
from apps.api.app.services.llm.router import LLMRouter

# Task label for LLM routing policy
TASK_LABEL = "afs_disclosure_draft"

# JSON schema for structured draft output
DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Section/note title"},
        "paragraphs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["text", "table", "heading"]},
                    "content": {"type": "string", "description": "Paragraph text or markdown table"},
                },
                "required": ["type", "content"],
                "additionalProperties": False,
            },
            "description": "Ordered list of content blocks",
        },
        "references": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Standard references cited (e.g. 'IAS 16.73', 'IFRS 15.113')",
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Any compliance warnings or items needing attention",
        },
    },
    "required": ["title", "paragraphs", "references", "warnings"],
    "additionalProperties": False,
}

# Validation schema for compliance check output
VALIDATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "compliant": {"type": "boolean"},
        "missing_disclosures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "reference": {"type": "string"},
                    "description": {"type": "string"},
                    "severity": {"type": "string", "enum": ["critical", "important", "minor"]},
                },
                "required": ["reference", "description", "severity"],
                "additionalProperties": False,
            },
        },
        "suggestions": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["compliant", "missing_disclosures", "suggestions"],
    "additionalProperties": False,
}


def _build_system_prompt(
    framework_name: str,
    standard: str,
    period_start: str,
    period_end: str,
    entity_name: str,
) -> str:
    """Build the system prompt for disclosure drafting."""
    return f"""You are an expert financial reporting assistant specialising in {framework_name} ({standard}).

You are preparing the Annual Financial Statements for {entity_name} for the period {period_start} to {period_end}.

Rules:
1. All financial figures in disclosures MUST come from the trial balance data provided — never invent numbers.
2. Follow the disclosure requirements of the applicable standard precisely.
3. Use formal financial reporting language appropriate for published annual financial statements.
4. Where the standard requires specific wording, use it exactly.
5. Include standard references (e.g. "IAS 16.73") in your references array.
6. Flag any areas where additional information from the preparer is needed in the warnings array.
7. If prior-year comparatives are available, include them.
8. Output structured content as paragraphs of type "text", "table" (markdown table format), or "heading"."""


def _build_draft_prompt(
    section_title: str,
    nl_instruction: str,
    trial_balance_summary: str,
    prior_afs_context: str,
    existing_draft: str | None,
) -> str:
    """Build the user prompt for drafting or re-drafting a section."""
    parts = [f"## Section: {section_title}\n"]

    if existing_draft:
        parts.append(f"### Current Draft\n{existing_draft}\n")
        parts.append(f"### User Feedback / Instruction\n{nl_instruction}\n")
        parts.append("Please revise the draft based on the user's feedback above. Keep what's good, fix what's flagged.\n")
    else:
        parts.append(f"### Instruction\n{nl_instruction}\n")
        parts.append("Please draft this section from scratch based on the instruction above.\n")

    parts.append(f"### Trial Balance Data\n{trial_balance_summary}\n")

    if prior_afs_context:
        parts.append(f"### Prior Year AFS Reference\n{prior_afs_context}\n")

    return "\n".join(parts)


async def draft_section(
    llm_router: LLMRouter,
    tenant_id: str,
    *,
    framework_name: str,
    standard: str,
    period_start: str,
    period_end: str,
    entity_name: str,
    section_title: str,
    nl_instruction: str,
    trial_balance_summary: str,
    prior_afs_context: str = "",
    existing_draft: str | None = None,
) -> LLMResponse:
    """Generate or re-draft a disclosure section using the LLM.

    Returns an LLMResponse whose `.content` matches DRAFT_SCHEMA.
    """
    system = _build_system_prompt(framework_name, standard, period_start, period_end, entity_name)
    user = _build_draft_prompt(section_title, nl_instruction, trial_balance_summary, prior_afs_context, existing_draft)

    messages: list[Message] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    return await llm_router.complete_with_routing(
        tenant_id=tenant_id,
        messages=messages,
        response_schema=DRAFT_SCHEMA,
        task_label=TASK_LABEL,
        max_tokens=8192,
        temperature=0.3,
    )


async def validate_sections(
    llm_router: LLMRouter,
    tenant_id: str,
    *,
    framework_name: str,
    standard: str,
    sections_summary: str,
    checklist_items: str,
) -> LLMResponse:
    """Validate generated sections against the disclosure checklist.

    Returns an LLMResponse whose `.content` matches VALIDATION_SCHEMA.
    """
    messages: list[Message] = [
        {
            "role": "system",
            "content": f"You are a financial reporting compliance reviewer for {framework_name} ({standard}). "
            "Compare the generated disclosure sections against the required disclosure checklist. "
            "Identify any missing or incomplete disclosures.",
        },
        {
            "role": "user",
            "content": f"## Generated Sections\n{sections_summary}\n\n## Disclosure Checklist\n{checklist_items}\n\n"
            "Please validate completeness and flag any missing required disclosures.",
        },
    ]

    return await llm_router.complete_with_routing(
        tenant_id=tenant_id,
        messages=messages,
        response_schema=VALIDATION_SCHEMA,
        task_label="afs_disclosure_validate",
        max_tokens=4096,
        temperature=0.1,
    )
```

**Step 2: Add task labels to LLM Router default policy**

Modify `apps/api/app/services/llm/router.py` — add two entries to the `DEFAULT_POLICY` list:

```python
{"task_label": "afs_disclosure_draft", "priority": 1, "provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "max_tokens": 8192, "temperature": 0.3},
{"task_label": "afs_disclosure_draft", "priority": 2, "provider": "openai", "model": "gpt-4o", "max_tokens": 8192, "temperature": 0.3},
{"task_label": "afs_disclosure_validate", "priority": 1, "provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "max_tokens": 4096, "temperature": 0.1},
{"task_label": "afs_disclosure_validate", "priority": 2, "provider": "openai", "model": "gpt-4o", "max_tokens": 4096, "temperature": 0.1},
```

**Step 3: Verify import**

Run: `cd apps/api && python -c "from apps.api.app.services.afs.disclosure_drafter import draft_section, validate_sections; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add apps/api/app/services/afs/disclosure_drafter.py apps/api/app/services/llm/router.py
git commit -m "feat(afs): add AI disclosure drafter service with LLM routing"
```

---

## Task 5: Backend API — Replace Stubs + Add Section Endpoints

**Files:**
- Modify: `apps/api/app/routers/afs.py`

**Context:** This task:
1. Replaces the mock reconciliation stub with real TB parsing + PDF extraction + comparison.
2. Updates the trial balance upload to actually parse files.
3. Updates the prior AFS upload to extract text from PDFs.
4. Adds 6 new section endpoints: list, create-draft (AI), get, update (re-draft), lock, validate.

**Step 1: Add imports and ID generator at top of `afs.py`**

Add these imports after the existing imports (after line 12):

```python
from apps.api.app.deps import get_llm_router
from apps.api.app.services.afs.tb_parser import parse_excel_tb, parse_csv_tb, tb_accounts_to_json
from apps.api.app.services.afs.pdf_extractor import extract_pdf, sections_to_json
from apps.api.app.services.afs.disclosure_drafter import draft_section, validate_sections
from apps.api.app.services.llm.router import LLMRouter
```

Add new ID generators after existing ones (after line ~48):

```python
def _section_id() -> str:
    return f"asc_{uuid.uuid4().hex[:14]}"

def _history_id() -> str:
    return f"ash_{uuid.uuid4().hex[:14]}"
```

Add new request models after existing ones (after line ~77):

```python
class DraftSectionBody(BaseModel):
    section_type: str = Field(default="note")  # note, statement, directors_report, accounting_policy
    title: str = Field(..., min_length=1, max_length=500)
    nl_instruction: str = Field(..., min_length=1, max_length=10000)

class UpdateSectionBody(BaseModel):
    nl_instruction: str | None = Field(default=None, max_length=10000)
    content_json: dict | None = None
    title: str | None = Field(default=None, max_length=500)
```

**Step 2: Update `upload_trial_balance` to parse the file**

Replace the INSERT query in `upload_trial_balance` that inserts `'[]'::jsonb` — instead parse the file and store the actual data:

```python
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

    # Parse the file into structured data
    if filename.lower().endswith(".csv"):
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
    return dict(row)
```

**Step 3: Update `upload_prior_afs` to extract PDF text**

Replace the INSERT in `upload_prior_afs` to run PDF extraction when `source_type == "pdf"`:

```python
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

    # Extract structured data from the file
    extracted = None
    if source_type == "pdf":
        result = extract_pdf(content)
        extracted = json.dumps({
            "page_count": result.page_count,
            "sections": sections_to_json(result.sections),
            "table_count": len(result.all_tables),
            "warnings": result.warnings,
        })
    elif source_type == "excel":
        parse_result = parse_excel_tb(content, filename)
        extracted = json.dumps({
            "accounts": tb_accounts_to_json(parse_result.accounts),
            "row_count": parse_result.row_count,
            "warnings": parse_result.warnings,
        })

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
            x_tenant_id, pa_id, engagement_id, filename, len(content), source_type, extracted,
        )

    store.save(x_tenant_id, AFS_ARTIFACT_TYPE, pa_id, {
        "b64": base64.b64encode(content).decode("ascii"),
        "content_type": content_type,
        "filename": filename,
    })
    return dict(row)
```

**Step 4: Replace the mock reconcile endpoint with real comparison**

Replace the `reconcile_prior_afs` function body. Instead of mock data, compare extracted PDF values with Excel values:

```python
@router.post("/engagements/{engagement_id}/prior-afs/reconcile")
async def reconcile_prior_afs(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Reconcile prior AFS sources — compare PDF-extracted vs Excel-extracted figures."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT engagement_id FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        # Get extracted data from both sources
        pdf_rows = await conn.fetch(
            "SELECT extracted_json FROM afs_prior_afs WHERE tenant_id = $1 AND engagement_id = $2 AND source_type = 'pdf'",
            x_tenant_id, engagement_id,
        )
        excel_rows = await conn.fetch(
            "SELECT extracted_json FROM afs_prior_afs WHERE tenant_id = $1 AND engagement_id = $2 AND source_type = 'excel'",
            x_tenant_id, engagement_id,
        )

        if not pdf_rows or not excel_rows:
            return {"discrepancies": [], "message": "Both PDF and Excel sources required for reconciliation"}

        # Build lookup of Excel accounts by name (case-insensitive)
        excel_accounts: dict[str, float] = {}
        for row in excel_rows:
            ej = row["extracted_json"]
            if ej and isinstance(ej, dict):
                for acct in ej.get("accounts", []):
                    name = acct.get("account_name", "").strip().lower()
                    if name:
                        excel_accounts[name] = acct.get("net", 0.0)

        # Build lookup of PDF sections — extract any numeric table data as line items
        pdf_line_items: dict[str, float] = {}
        for row in pdf_rows:
            pj = row["extracted_json"]
            if pj and isinstance(pj, dict):
                for section in pj.get("sections", []):
                    # Try to extract line items from section text (simple pattern: "Label  1,234,567")
                    text = section.get("text", "")
                    for line in text.split("\n"):
                        parts = line.rsplit(None, 1)
                        if len(parts) == 2:
                            label = parts[0].strip().lower()
                            try:
                                val = float(parts[1].replace(",", "").replace(" ", ""))
                                pdf_line_items[label] = val
                            except (ValueError, TypeError):
                                pass

        # Clear existing discrepancies for this engagement
        await conn.execute(
            "DELETE FROM afs_source_discrepancies WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )

        # Compare: for each Excel account, check if there's a matching PDF line item
        created = []
        for name, excel_val in excel_accounts.items():
            if name in pdf_line_items:
                pdf_val = pdf_line_items[name]
                diff = abs(pdf_val - excel_val)
                if diff > 0.01:  # Only flag material differences
                    d_id = _discrepancy_id()
                    row = await conn.fetchrow(
                        """INSERT INTO afs_source_discrepancies
                           (tenant_id, discrepancy_id, engagement_id, line_item, pdf_value, excel_value, difference)
                           VALUES ($1, $2, $3, $4, $5, $6, $7)
                           RETURNING *""",
                        x_tenant_id, d_id, engagement_id,
                        name.title(), pdf_val, excel_val, diff,
                    )
                    created.append(dict(row))

        return {"discrepancies": created, "message": f"Found {len(created)} discrepancies"}
```

**Step 5: Add section endpoints at end of `afs.py`**

Append after the projections section:

```python
# ===========================================================================
# Sections — AI Disclosure Drafting
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
            "SELECT * FROM afs_sections WHERE tenant_id = $1 AND engagement_id = $2 ORDER BY section_number, created_at",
            x_tenant_id, engagement_id,
        )
        return {"items": [dict(r) for r in rows]}


@router.post("/engagements/{engagement_id}/sections/draft", status_code=201)
async def draft_new_section(
    engagement_id: str,
    body: DraftSectionBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm_router: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Generate a new section draft using AI from a natural-language instruction."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.section_type not in {"note", "statement", "directors_report", "accounting_policy"}:
        raise HTTPException(400, "section_type must be one of: note, statement, directors_report, accounting_policy")

    async with tenant_conn(x_tenant_id) as conn:
        # Load engagement + framework
        eng = await conn.fetchrow(
            "SELECT * FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        fw = await conn.fetchrow(
            "SELECT * FROM afs_frameworks WHERE tenant_id = $1 AND framework_id = $2",
            x_tenant_id, eng["framework_id"],
        )

        # Load trial balance data
        tb_rows = await conn.fetch(
            "SELECT data_json FROM afs_trial_balances WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        tb_summary = ""
        for r in tb_rows:
            dj = r["data_json"]
            if dj and isinstance(dj, list):
                lines = [f"{a.get('gl_code', '')} {a['account_name']}: Dr {a.get('debit', 0):.2f} Cr {a.get('credit', 0):.2f}" for a in dj[:100]]
                tb_summary += "\n".join(lines)

        # Load prior AFS context
        prior_rows = await conn.fetch(
            "SELECT extracted_json, source_type FROM afs_prior_afs WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        prior_context = ""
        for r in prior_rows:
            ej = r["extracted_json"]
            if ej and isinstance(ej, dict) and r["source_type"] == "pdf":
                for section in ej.get("sections", []):
                    prior_context += f"\n### {section.get('title', 'Untitled')}\n{section.get('text', '')[:2000]}\n"

        # Call AI disclosure drafter
        llm_response = await draft_section(
            llm_router,
            x_tenant_id,
            framework_name=fw["name"] if fw else "Unknown",
            standard=fw["standard"] if fw else "ifrs",
            period_start=str(eng["period_start"]),
            period_end=str(eng["period_end"]),
            entity_name=eng["entity_name"],
            section_title=body.title,
            nl_instruction=body.nl_instruction,
            trial_balance_summary=tb_summary or "No trial balance data available",
            prior_afs_context=prior_context,
        )

        # Determine next section number
        max_num = await conn.fetchval(
            "SELECT COALESCE(MAX(section_number), 0) FROM afs_sections WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )

        sid = _section_id()
        content_json = json.dumps(llm_response.content)

        row = await conn.fetchrow(
            """INSERT INTO afs_sections
               (tenant_id, section_id, engagement_id, section_type, section_number, title,
                content_json, status, version, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, 'draft', 1, $8)
               RETURNING *""",
            x_tenant_id, sid, engagement_id, body.section_type,
            max_num + 1, body.title, content_json, x_user_id or None,
        )

        # Record history
        hid = _history_id()
        await conn.execute(
            """INSERT INTO afs_section_history
               (tenant_id, history_id, section_id, version, content_json, nl_instruction, changed_by)
               VALUES ($1, $2, $3, 1, $4::jsonb, $5, $6)""",
            x_tenant_id, hid, sid, content_json, body.nl_instruction, x_user_id or None,
        )

        result = dict(row)
        result["llm_cost_usd"] = llm_response.cost_estimate_usd
        result["llm_tokens"] = llm_response.tokens.total_tokens
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
            "SELECT * FROM afs_sections WHERE tenant_id = $1 AND section_id = $2 AND engagement_id = $3",
            x_tenant_id, section_id, engagement_id,
        )
        if not row:
            raise HTTPException(404, "Section not found")
        return dict(row)


@router.patch("/engagements/{engagement_id}/sections/{section_id}")
async def update_section(
    engagement_id: str,
    section_id: str,
    body: UpdateSectionBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm_router: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Update a section — either manual edit (content_json) or AI re-draft (nl_instruction)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM afs_sections WHERE tenant_id = $1 AND section_id = $2 AND engagement_id = $3",
            x_tenant_id, section_id, engagement_id,
        )
        if not existing:
            raise HTTPException(404, "Section not found")
        if existing["status"] == "locked":
            raise HTTPException(409, "Section is locked; unlock before editing")

        new_version = existing["version"] + 1
        content_json = existing["content_json"]
        nl_used = body.nl_instruction

        if body.nl_instruction and not body.content_json:
            # AI re-draft: pass existing content + new instruction
            eng = await conn.fetchrow(
                "SELECT * FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
                x_tenant_id, engagement_id,
            )
            fw = await conn.fetchrow(
                "SELECT * FROM afs_frameworks WHERE tenant_id = $1 AND framework_id = $2",
                x_tenant_id, eng["framework_id"],
            )
            tb_rows = await conn.fetch(
                "SELECT data_json FROM afs_trial_balances WHERE tenant_id = $1 AND engagement_id = $2",
                x_tenant_id, engagement_id,
            )
            tb_summary = ""
            for r in tb_rows:
                dj = r["data_json"]
                if dj and isinstance(dj, list):
                    lines = [f"{a.get('gl_code', '')} {a['account_name']}: Dr {a.get('debit', 0):.2f} Cr {a.get('credit', 0):.2f}" for a in dj[:100]]
                    tb_summary += "\n".join(lines)

            # Serialize existing draft for context
            existing_content = existing["content_json"]
            existing_text = ""
            if isinstance(existing_content, dict):
                for p in existing_content.get("paragraphs", []):
                    existing_text += p.get("content", "") + "\n"

            llm_response = await draft_section(
                llm_router,
                x_tenant_id,
                framework_name=fw["name"] if fw else "Unknown",
                standard=fw["standard"] if fw else "ifrs",
                period_start=str(eng["period_start"]),
                period_end=str(eng["period_end"]),
                entity_name=eng["entity_name"],
                section_title=existing["title"],
                nl_instruction=body.nl_instruction,
                trial_balance_summary=tb_summary or "No trial balance data available",
                existing_draft=existing_text,
            )
            content_json = llm_response.content
        elif body.content_json:
            # Manual edit
            content_json = body.content_json
            nl_used = "Manual edit"

        title = body.title or existing["title"]
        cj_str = json.dumps(content_json) if isinstance(content_json, dict) else content_json

        row = await conn.fetchrow(
            """UPDATE afs_sections
               SET content_json = $4::jsonb, version = $5, title = $6, updated_at = now()
               WHERE tenant_id = $1 AND section_id = $2 AND engagement_id = $3
               RETURNING *""",
            x_tenant_id, section_id, engagement_id, cj_str, new_version, title,
        )

        hid = _history_id()
        await conn.execute(
            """INSERT INTO afs_section_history
               (tenant_id, history_id, section_id, version, content_json, nl_instruction, changed_by)
               VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)""",
            x_tenant_id, hid, section_id, new_version, cj_str, nl_used, x_user_id or None,
        )

        return dict(row)


@router.post("/engagements/{engagement_id}/sections/{section_id}/lock")
async def lock_section(
    engagement_id: str,
    section_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Lock a section (mark as finalised)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """UPDATE afs_sections
               SET status = 'locked', updated_at = now()
               WHERE tenant_id = $1 AND section_id = $2 AND engagement_id = $3
               RETURNING *""",
            x_tenant_id, section_id, engagement_id,
        )
        if not row:
            raise HTTPException(404, "Section not found")
        return dict(row)


@router.post("/engagements/{engagement_id}/sections/{section_id}/unlock")
async def unlock_section(
    engagement_id: str,
    section_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Unlock a locked section for further editing."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """UPDATE afs_sections
               SET status = 'draft', updated_at = now()
               WHERE tenant_id = $1 AND section_id = $2 AND engagement_id = $3
               RETURNING *""",
            x_tenant_id, section_id, engagement_id,
        )
        if not row:
            raise HTTPException(404, "Section not found")
        return dict(row)


@router.post("/engagements/{engagement_id}/validate")
async def validate_engagement_sections(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    llm_router: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Validate all sections against the disclosure checklist using AI."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT * FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        fw = await conn.fetchrow(
            "SELECT * FROM afs_frameworks WHERE tenant_id = $1 AND framework_id = $2",
            x_tenant_id, eng["framework_id"],
        )

        # Load all sections
        sections = await conn.fetch(
            "SELECT * FROM afs_sections WHERE tenant_id = $1 AND engagement_id = $2 ORDER BY section_number",
            x_tenant_id, engagement_id,
        )
        sections_summary = ""
        for s in sections:
            cj = s["content_json"]
            text = ""
            if isinstance(cj, dict):
                for p in cj.get("paragraphs", []):
                    text += p.get("content", "") + "\n"
            sections_summary += f"\n## {s['title']}\n{text[:2000]}\n"

        # Load checklist
        checklist_rows = await conn.fetch(
            "SELECT * FROM afs_disclosure_items WHERE tenant_id = $1 AND framework_id = $2 ORDER BY section, reference",
            x_tenant_id, eng["framework_id"],
        )
        checklist_text = "\n".join(
            f"- [{r['reference'] or 'N/A'}] {r['description']} (required: {r['required']})"
            for r in checklist_rows
        )

        if not checklist_text:
            return {"compliant": True, "missing_disclosures": [], "suggestions": ["No disclosure checklist items defined for this framework"]}

        llm_response = await validate_sections(
            llm_router,
            x_tenant_id,
            framework_name=fw["name"] if fw else "Unknown",
            standard=fw["standard"] if fw else "ifrs",
            sections_summary=sections_summary or "No sections drafted yet",
            checklist_items=checklist_text,
        )

        return llm_response.content
```

**Step 6: Verify syntax**

Run: `cd apps/api && python -c "from apps.api.app.routers import afs; print('OK')"`
Expected: `OK`

**Step 7: Commit**

```bash
git add apps/api/app/routers/afs.py
git commit -m "feat(afs): replace stubs with real parsing + add AI section drafting endpoints"
```

---

## Task 6: Frontend API Client — Add Section Interfaces + Methods

**Files:**
- Modify: `apps/web/lib/api.ts`

**Step 1: Add TypeScript interfaces**

After the existing `AFSProjection` interface (~line 1953), add:

```typescript
export interface AFSSection {
  section_id: string;
  engagement_id: string;
  section_type: string;
  section_number: number;
  title: string;
  content_json: {
    title: string;
    paragraphs: { type: "text" | "table" | "heading"; content: string }[];
    references: string[];
    warnings: string[];
  } | null;
  status: string;
  version: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  llm_cost_usd?: number;
  llm_tokens?: number;
}

export interface AFSSectionHistory {
  history_id: string;
  section_id: string;
  version: number;
  content_json: Record<string, unknown>;
  nl_instruction: string | null;
  changed_by: string | null;
  changed_at: string;
}

export interface AFSValidationResult {
  compliant: boolean;
  missing_disclosures: { reference: string; description: string; severity: string }[];
  suggestions: string[];
}
```

**Step 2: Add section methods to the `afs` namespace**

After the existing `listProjections` method (~line 1458), add:

```typescript
    // Sections
    listSections: (tenantId: string, engagementId: string) =>
      request<{ items: AFSSection[] }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/sections`, { tenantId }),
    draftSection: (tenantId: string, engagementId: string, body: { section_type: string; title: string; nl_instruction: string }) =>
      request<AFSSection>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/sections/draft`, { tenantId, method: "POST", body }),
    getSection: (tenantId: string, engagementId: string, sectionId: string) =>
      request<AFSSection>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/sections/${encodeURIComponent(sectionId)}`, { tenantId }),
    updateSection: (tenantId: string, engagementId: string, sectionId: string, body: { nl_instruction?: string; content_json?: Record<string, unknown>; title?: string }) =>
      request<AFSSection>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/sections/${encodeURIComponent(sectionId)}`, { tenantId, method: "PATCH", body }),
    lockSection: (tenantId: string, engagementId: string, sectionId: string) =>
      request<AFSSection>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/sections/${encodeURIComponent(sectionId)}/lock`, { tenantId, method: "POST" }),
    unlockSection: (tenantId: string, engagementId: string, sectionId: string) =>
      request<AFSSection>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/sections/${encodeURIComponent(sectionId)}/unlock`, { tenantId, method: "POST" }),
    validateSections: (tenantId: string, engagementId: string) =>
      request<AFSValidationResult>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/validate`, { tenantId, method: "POST" }),
```

**Step 3: Commit**

```bash
git add apps/web/lib/api.ts
git commit -m "feat(afs): add section drafting interfaces and API methods to frontend client"
```

---

## Task 7: Section Editor Frontend Page

**Files:**
- Create: `apps/web/app/(app)/afs/[id]/sections/page.tsx`

**Context:** This is the core Phase 2 UI. It shows all sections for an engagement with a split-panel layout: left side has the section list + NL instruction input, right side shows the rendered section content. Users can draft new sections, iterate with feedback, and lock finalised sections.

**Step 1: Create the Section Editor page**

Create `apps/web/app/(app)/afs/[id]/sections/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, AFSSection, AFSEngagement, AFSValidationResult } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";
import { VAButton } from "@/components/ui/VAButton";
import { VACard } from "@/components/ui/VACard";
import { VAInput } from "@/components/ui/VAInput";
import { VABadge } from "@/components/ui/VABadge";
import { VASpinner } from "@/components/ui/VASpinner";
import { VAEmptyState } from "@/components/ui/VAEmptyState";

const SECTION_TYPES = [
  { value: "note", label: "Note" },
  { value: "statement", label: "Statement" },
  { value: "directors_report", label: "Directors' Report" },
  { value: "accounting_policy", label: "Accounting Policy" },
];

export default function SectionEditorPage() {
  const params = useParams();
  const router = useRouter();
  const toast = useToast();
  const engagementId = params.id as string;
  const tenantId = typeof window !== "undefined" ? localStorage.getItem("tenantId") || "" : "";

  const [engagement, setEngagement] = useState<AFSEngagement | null>(null);
  const [sections, setSections] = useState<AFSSection[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [drafting, setDrafting] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<AFSValidationResult | null>(null);

  // New section form
  const [showNewForm, setShowNewForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newType, setNewType] = useState("note");
  const [newInstruction, setNewInstruction] = useState("");

  // Re-draft form
  const [feedbackText, setFeedbackText] = useState("");

  useEffect(() => {
    if (!tenantId || !engagementId) return;
    (async () => {
      try {
        const [eng, secs] = await Promise.all([
          api.afs.getEngagement(tenantId, engagementId),
          api.afs.listSections(tenantId, engagementId),
        ]);
        setEngagement(eng);
        setSections(secs.items);
        if (secs.items.length > 0 && !selectedId) {
          setSelectedId(secs.items[0].section_id);
        }
      } catch {
        toast.error("Failed to load engagement");
      } finally {
        setLoading(false);
      }
    })();
  }, [tenantId, engagementId]);

  const selectedSection = sections.find((s) => s.section_id === selectedId) || null;

  async function handleDraftNew() {
    if (!newTitle.trim() || !newInstruction.trim()) return;
    setDrafting(true);
    try {
      const section = await api.afs.draftSection(tenantId, engagementId, {
        section_type: newType,
        title: newTitle,
        nl_instruction: newInstruction,
      });
      setSections((prev) => [...prev, section]);
      setSelectedId(section.section_id);
      setShowNewForm(false);
      setNewTitle("");
      setNewInstruction("");
      toast.success("Section drafted successfully");
    } catch {
      toast.error("Failed to draft section");
    } finally {
      setDrafting(false);
    }
  }

  async function handleRedraft() {
    if (!selectedSection || !feedbackText.trim()) return;
    setDrafting(true);
    try {
      const updated = await api.afs.updateSection(tenantId, engagementId, selectedSection.section_id, {
        nl_instruction: feedbackText,
      });
      setSections((prev) => prev.map((s) => (s.section_id === updated.section_id ? updated : s)));
      setFeedbackText("");
      toast.success("Section re-drafted");
    } catch {
      toast.error("Failed to re-draft section");
    } finally {
      setDrafting(false);
    }
  }

  async function handleLock(sectionId: string) {
    try {
      const updated = await api.afs.lockSection(tenantId, engagementId, sectionId);
      setSections((prev) => prev.map((s) => (s.section_id === updated.section_id ? updated : s)));
      toast.success("Section locked");
    } catch {
      toast.error("Failed to lock section");
    }
  }

  async function handleUnlock(sectionId: string) {
    try {
      const updated = await api.afs.unlockSection(tenantId, engagementId, sectionId);
      setSections((prev) => prev.map((s) => (s.section_id === updated.section_id ? updated : s)));
      toast.success("Section unlocked");
    } catch {
      toast.error("Failed to unlock section");
    }
  }

  async function handleValidate() {
    setValidating(true);
    try {
      const result = await api.afs.validateSections(tenantId, engagementId);
      setValidationResult(result);
      if (result.compliant) {
        toast.success("All disclosures are compliant");
      } else {
        toast.error(`${result.missing_disclosures.length} missing disclosure(s) found`);
      }
    } catch {
      toast.error("Validation failed");
    } finally {
      setValidating(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <VASpinner />
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-va-border px-6 py-3">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push(`/afs/${engagementId}/setup`)} className="text-va-text2 hover:text-va-text">
            &larr;
          </button>
          <h1 className="text-lg font-semibold text-va-text">
            {engagement?.entity_name} — Section Editor
          </h1>
        </div>
        <div className="flex gap-2">
          <VAButton variant="secondary" onClick={handleValidate} disabled={validating || sections.length === 0}>
            {validating ? "Validating..." : "Validate Disclosures"}
          </VAButton>
          <VAButton variant="primary" onClick={() => setShowNewForm(true)}>
            + New Section
          </VAButton>
        </div>
      </div>

      {/* Split panel */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Section list */}
        <div className="w-80 flex-shrink-0 overflow-y-auto border-r border-va-border bg-va-surface p-4">
          {sections.length === 0 ? (
            <VAEmptyState
              icon="file-text"
              title="No sections yet"
              description="Draft your first section using AI"
              actionLabel="New Section"
              onAction={() => setShowNewForm(true)}
            />
          ) : (
            <div className="space-y-2">
              {sections.map((s) => (
                <button
                  key={s.section_id}
                  onClick={() => setSelectedId(s.section_id)}
                  className={`w-full rounded-va-sm border p-3 text-left transition-colors ${
                    selectedId === s.section_id
                      ? "border-va-blue bg-va-blue/10"
                      : "border-va-border bg-va-panel hover:border-va-text2"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-va-text">{s.title}</span>
                    <VABadge variant={s.status === "locked" ? "success" : s.status === "reviewed" ? "violet" : "default"}>
                      {s.status}
                    </VABadge>
                  </div>
                  <span className="mt-1 block text-xs text-va-text2">
                    {s.section_type} · v{s.version}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right: Content + feedback */}
        <div className="flex flex-1 flex-col overflow-y-auto p-6">
          {showNewForm ? (
            <VACard className="mx-auto max-w-2xl p-6">
              <h2 className="text-lg font-semibold text-va-text">Draft New Section</h2>
              <div className="mt-4 space-y-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-va-text">Section Type</label>
                  <select
                    value={newType}
                    onChange={(e) => setNewType(e.target.value)}
                    className="w-full rounded-va-sm border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text"
                  >
                    {SECTION_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-va-text">Title</label>
                  <VAInput
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    placeholder="e.g. Revenue Recognition"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-va-text">Instruction (natural language)</label>
                  <textarea
                    value={newInstruction}
                    onChange={(e) => setNewInstruction(e.target.value)}
                    placeholder="Describe what this section should contain. E.g. 'Revenue increased 15% due to new mining contracts. We adopted IFRS 15 this year.'"
                    rows={5}
                    className="w-full rounded-va-sm border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text placeholder:text-va-muted"
                  />
                </div>
                <div className="flex justify-end gap-3">
                  <VAButton variant="secondary" onClick={() => setShowNewForm(false)}>Cancel</VAButton>
                  <VAButton variant="primary" onClick={handleDraftNew} disabled={drafting || !newTitle.trim() || !newInstruction.trim()}>
                    {drafting ? "Drafting with AI..." : "Generate Draft"}
                  </VAButton>
                </div>
              </div>
            </VACard>
          ) : selectedSection ? (
            <>
              {/* Section content */}
              <div className="mb-6">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-xl font-semibold text-va-text">{selectedSection.title}</h2>
                  <div className="flex gap-2">
                    {selectedSection.status === "locked" ? (
                      <VAButton variant="secondary" onClick={() => handleUnlock(selectedSection.section_id)}>
                        Unlock
                      </VAButton>
                    ) : (
                      <VAButton variant="primary" onClick={() => handleLock(selectedSection.section_id)}>
                        Lock Section
                      </VAButton>
                    )}
                  </div>
                </div>

                {selectedSection.content_json?.warnings && selectedSection.content_json.warnings.length > 0 && (
                  <div className="mb-4 rounded-va-sm border border-yellow-500/30 bg-yellow-500/10 p-3">
                    <p className="text-sm font-medium text-yellow-400">Warnings:</p>
                    <ul className="mt-1 list-disc pl-5 text-sm text-yellow-300/80">
                      {selectedSection.content_json.warnings.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <VACard className="p-6">
                  {selectedSection.content_json?.paragraphs?.map((p, i) => (
                    <div key={i} className="mb-4">
                      {p.type === "heading" ? (
                        <h3 className="text-lg font-semibold text-va-text">{p.content}</h3>
                      ) : p.type === "table" ? (
                        <div className="overflow-x-auto">
                          <pre className="whitespace-pre-wrap text-sm text-va-text2">{p.content}</pre>
                        </div>
                      ) : (
                        <p className="text-sm leading-relaxed text-va-text2">{p.content}</p>
                      )}
                    </div>
                  ))}
                </VACard>

                {selectedSection.content_json?.references && selectedSection.content_json.references.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {selectedSection.content_json.references.map((ref, i) => (
                      <VABadge key={i} variant="violet">{ref}</VABadge>
                    ))}
                  </div>
                )}

                <p className="mt-2 text-xs text-va-muted">
                  Version {selectedSection.version} · {selectedSection.section_type}
                </p>
              </div>

              {/* Feedback / re-draft */}
              {selectedSection.status !== "locked" && (
                <div className="border-t border-va-border pt-4">
                  <h3 className="mb-2 text-sm font-medium text-va-text">Provide Feedback (AI will re-draft)</h3>
                  <div className="flex gap-3">
                    <textarea
                      value={feedbackText}
                      onChange={(e) => setFeedbackText(e.target.value)}
                      placeholder="E.g. 'Add more detail about the lease modifications' or 'The revenue figure should be R1.2m not R1.5m'"
                      rows={3}
                      className="flex-1 rounded-va-sm border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text placeholder:text-va-muted"
                    />
                    <VAButton
                      variant="primary"
                      onClick={handleRedraft}
                      disabled={drafting || !feedbackText.trim()}
                      className="self-end"
                    >
                      {drafting ? "Re-drafting..." : "Re-draft"}
                    </VAButton>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex h-full items-center justify-center">
              <p className="text-va-muted">Select a section from the list or create a new one</p>
            </div>
          )}

          {/* Validation results */}
          {validationResult && (
            <div className="mt-6 border-t border-va-border pt-4">
              <h3 className="mb-3 text-sm font-semibold text-va-text">
                Disclosure Validation {validationResult.compliant ? "✓" : "!"}
              </h3>
              {validationResult.missing_disclosures.length > 0 && (
                <div className="space-y-2">
                  {validationResult.missing_disclosures.map((d, i) => (
                    <div key={i} className="rounded-va-sm border border-va-border bg-va-panel p-3">
                      <div className="flex items-center gap-2">
                        <VABadge variant={d.severity === "critical" ? "danger" : d.severity === "important" ? "warning" : "default"}>
                          {d.severity}
                        </VABadge>
                        <span className="text-sm font-medium text-va-text">{d.reference}</span>
                      </div>
                      <p className="mt-1 text-sm text-va-text2">{d.description}</p>
                    </div>
                  ))}
                </div>
              )}
              {validationResult.suggestions.length > 0 && (
                <div className="mt-3">
                  <p className="text-sm font-medium text-va-text">Suggestions:</p>
                  <ul className="mt-1 list-disc pl-5 text-sm text-va-text2">
                    {validationResult.suggestions.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add apps/web/app/\(app\)/afs/\[id\]/sections/page.tsx
git commit -m "feat(afs): add Section Editor page with AI drafting and validation UI"
```

---

## Task 8: Wire Section Editor into Engagement Flow

**Files:**
- Modify: `apps/web/app/(app)/afs/[id]/setup/page.tsx`
- Modify: `apps/web/app/(app)/afs/page.tsx`

**Step 1: Add navigation to Section Editor from setup wizard completion**

In `apps/web/app/(app)/afs/[id]/setup/page.tsx`, find the final step's "Complete Setup" button handler. After it updates status to `"ingestion"`, add a navigation to the section editor. Change the router.push target from `/afs` to `/afs/${engagementId}/sections`.

Specifically, find `router.push("/afs")` in the completion handler and change to:
```typescript
router.push(`/afs/${engagementId}/sections`);
```

**Step 2: Add "Edit Sections" link to engagement cards on dashboard**

In `apps/web/app/(app)/afs/page.tsx`, add a secondary link on each engagement card. When engagement status is not `"setup"`, show an "Edit Sections" button that links to `/afs/${engagement.engagement_id}/sections`.

Find the engagement card render and add after the existing link:

```tsx
{eng.status !== "setup" && (
  <a
    href={`/afs/${eng.engagement_id}/sections`}
    className="text-xs text-va-blue hover:underline"
  >
    Edit Sections →
  </a>
)}
```

**Step 3: Commit**

```bash
git add apps/web/app/\(app\)/afs/\[id\]/setup/page.tsx apps/web/app/\(app\)/afs/page.tsx
git commit -m "feat(afs): wire Section Editor navigation from setup wizard and dashboard"
```

---

## Task 9: Build Verification

**Step 1: Run Next.js build**

Run: `cd apps/web && npx next build`
Expected: Build succeeds with no type errors. Pages `/afs`, `/afs/[id]/setup`, `/afs/[id]/sections` all listed.

**Step 2: Run frontend tests**

Run: `cd apps/web && npx vitest run`
Expected: All existing tests pass (140/140).

**Step 3: Verify Python imports**

Run: `cd apps/api && python -c "from apps.api.app.routers import afs; from apps.api.app.services.afs.tb_parser import parse_excel_tb; from apps.api.app.services.afs.pdf_extractor import extract_pdf; from apps.api.app.services.afs.disclosure_drafter import draft_section; print('ALL OK')"`
Expected: `ALL OK`

**Step 4: Commit (if any fixes needed)**

Fix any issues and commit.

---

## Execution Order

```
Task 1 (Migration)           ─── standalone
Task 2 (TB Parser)           ─── standalone
Task 3 (PDF Extractor)       ─── standalone
Task 4 (Disclosure Drafter)  ─── depends on LLM Router (minor edit)
Task 5 (Backend Endpoints)   ─── depends on Tasks 2, 3, 4
Task 6 (Frontend API)        ─── standalone (interfaces only)
Task 7 (Section Editor UI)   ─── depends on Task 6
Task 8 (Wire Navigation)     ─── depends on Task 7
Task 9 (Verification)        ─── depends on all above
```

Tasks 1, 2, 3, 6 can run in parallel. Task 4 needs LLM Router edit. Task 5 needs 2+3+4. Tasks 7→8→9 are sequential.

---

## Verification Checklist

1. `cd apps/web && npx next build` — no type errors
2. `cd apps/web && npx vitest run` — all tests pass
3. Python imports work for all new services
4. Visit `/afs` — dashboard shows "Edit Sections" link on non-setup engagements
5. Visit `/afs/{id}/setup` — complete setup navigates to Section Editor
6. Visit `/afs/{id}/sections` — empty state shows, "New Section" button works
7. Draft a section with NL instruction — AI generates structured content
8. Provide feedback — AI re-drafts the section with changes
9. Lock/unlock a section — status badge updates
10. "Validate Disclosures" — calls AI to check completeness against checklist
11. Upload Excel TB — `data_json` is populated with parsed accounts (not empty `[]`)
12. Upload PDF AFS — `extracted_json` is populated with sections and text
13. Reconcile with both sources — real discrepancies generated (not mock data)
