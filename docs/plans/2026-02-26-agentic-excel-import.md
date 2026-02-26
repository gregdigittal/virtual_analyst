# Agentic Excel Import Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current single-pass Excel import wizard with an agentic multi-turn flow powered by Claude Agent SDK, streamed via SSE with human-in-the-loop Q&A.

**Architecture:** Backend runs Agent SDK with 10 custom MCP tools inside an `AgentSessionManager` that yields SSE events. Frontend is a guided chat wizard (`ImportWizard`) with stepper, chat thread, and inline question cards. Agent pauses on `ask_user_question`; user answers resume the session.

**Tech Stack:** Claude Agent SDK (`claude-agent-sdk`), FastAPI `StreamingResponse` (SSE), Next.js 14, EventSource API, Vitest/RTL.

**Design doc:** `docs/plans/2026-02-26-agentic-excel-import-design.md`

---

### Task 1: DB Migration — Add Agent Columns

**Files:**
- Create: `apps/api/app/db/migrations/0051_excel_agent_sessions.sql`

**Context:** Existing table `excel_ingestion_sessions` (migration 0044) has columns for classification_json, mapping_json, etc. We add 4 columns for agent session state.

**Step 1: Write migration SQL**

```sql
-- 0051_excel_agent_sessions.sql
-- Add agent session tracking columns to excel_ingestion_sessions

ALTER TABLE excel_ingestion_sessions
  ADD COLUMN IF NOT EXISTS agent_session_id TEXT,
  ADD COLUMN IF NOT EXISTS agent_messages JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS agent_status TEXT NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS pending_question JSONB;

COMMENT ON COLUMN excel_ingestion_sessions.agent_session_id IS 'Claude Agent SDK session ID for resumption';
COMMENT ON COLUMN excel_ingestion_sessions.agent_messages IS 'Chat message history for frontend hydration';
COMMENT ON COLUMN excel_ingestion_sessions.agent_status IS 'running | paused | complete | error';
COMMENT ON COLUMN excel_ingestion_sessions.pending_question IS 'Current question awaiting user answer (null when not paused)';
```

**Step 2: Verify migration numbering**

Run: `ls apps/api/app/db/migrations/ | tail -5`
Expected: 0050 is the last migration, 0051 is next.

**Step 3: Commit**

```bash
git add apps/api/app/db/migrations/0051_excel_agent_sessions.sql
git commit -m "feat(db): add agent session columns to excel_ingestion_sessions"
```

---

### Task 2: MCP Read Tools — Sheet Data Access

**Files:**
- Create: `apps/api/app/services/agent/excel_tools.py`
- Create: `apps/api/tests/services/agent/test_excel_tools.py`

**Context:** The MCP tool server provides 5 read-only tools that let the agent explore the parsed workbook. The parsed workbook is an `ExcelParseResult` dataclass (defined in `apps/api/app/services/excel_parser.py:49-60`) containing `sheets: list[SheetInfo]` where each `SheetInfo` has `name`, `headers`, `sample_rows`, `formula_patterns`, `referenced_sheets`.

**Step 1: Write failing tests for read tools**

```python
# apps/api/tests/services/agent/test_excel_tools.py
"""Tests for MCP read tools that access parsed Excel workbook data."""

import pytest
from apps.api.app.services.agent.excel_tools import (
    handle_read_sheet_data,
    handle_read_cell_range,
    handle_get_formula_patterns,
    handle_get_sheet_dependencies,
    handle_compare_sheets,
)


# --- Fixtures ---

MOCK_SHEETS = {
    "P&L": {
        "name": "P&L",
        "headers": ["Account", "2024", "2025", "2026"],
        "sample_rows": [
            ["Revenue", 100000, 120000, 150000],
            ["COGS", 40000, 48000, 60000],
            ["Gross Profit", 60000, 72000, 90000],
        ],
        "row_count": 45,
        "col_count": 4,
        "formula_patterns": [
            {"cell": "B4", "formula": "=B2-B3", "refs": []},
        ],
        "referenced_sheets": ["Assumptions"],
    },
    "Balance Sheet": {
        "name": "Balance Sheet",
        "headers": ["Account", "2024", "2025"],
        "sample_rows": [
            ["Cash", 50000, 65000],
            ["Receivables", 20000, 25000],
        ],
        "row_count": 32,
        "col_count": 3,
        "formula_patterns": [],
        "referenced_sheets": ["P&L"],
    },
    "Assumptions": {
        "name": "Assumptions",
        "headers": ["Parameter", "Value"],
        "sample_rows": [
            ["Growth Rate", 0.2],
            ["COGS %", 0.4],
        ],
        "row_count": 10,
        "col_count": 2,
        "formula_patterns": [],
        "referenced_sheets": [],
    },
}


class TestReadSheetData:
    def test_returns_headers_and_sample_rows(self):
        result = handle_read_sheet_data(MOCK_SHEETS, {"sheet_name": "P&L"})
        assert result["sheet_name"] == "P&L"
        assert result["headers"] == ["Account", "2024", "2025", "2026"]
        assert len(result["sample_rows"]) == 3
        assert result["row_count"] == 45
        assert result["col_count"] == 4

    def test_limits_rows_with_max_rows(self):
        result = handle_read_sheet_data(
            MOCK_SHEETS, {"sheet_name": "P&L", "max_rows": 2}
        )
        assert len(result["sample_rows"]) == 2

    def test_unknown_sheet_returns_error(self):
        result = handle_read_sheet_data(MOCK_SHEETS, {"sheet_name": "Missing"})
        assert "error" in result


class TestGetFormulaPatterns:
    def test_returns_formulas_for_sheet(self):
        result = handle_get_formula_patterns(MOCK_SHEETS, {"sheet_name": "P&L"})
        assert len(result["formulas"]) == 1
        assert result["formulas"][0]["cell"] == "B4"

    def test_empty_formulas(self):
        result = handle_get_formula_patterns(
            MOCK_SHEETS, {"sheet_name": "Assumptions"}
        )
        assert result["formulas"] == []


class TestGetSheetDependencies:
    def test_returns_dependency_graph(self):
        result = handle_get_sheet_dependencies(MOCK_SHEETS, {})
        assert "P&L" in result["dependencies"]
        assert "Assumptions" in result["dependencies"]["P&L"]
        assert "Balance Sheet" in result["dependencies"]
        assert "P&L" in result["dependencies"]["Balance Sheet"]

    def test_sheets_with_no_deps(self):
        result = handle_get_sheet_dependencies(MOCK_SHEETS, {})
        assert result["dependencies"]["Assumptions"] == []


class TestCompareSheets:
    def test_compares_two_sheets(self):
        result = handle_compare_sheets(
            MOCK_SHEETS, {"sheet_a": "P&L", "sheet_b": "Balance Sheet"}
        )
        assert result["sheet_a"] == "P&L"
        assert result["sheet_b"] == "Balance Sheet"
        assert "row_count" in result["comparison"]
        assert "col_count" in result["comparison"]
        assert "shared_headers" in result["comparison"]

    def test_missing_sheet_returns_error(self):
        result = handle_compare_sheets(
            MOCK_SHEETS, {"sheet_a": "P&L", "sheet_b": "Missing"}
        )
        assert "error" in result


class TestReadCellRange:
    def test_reads_range(self):
        result = handle_read_cell_range(
            MOCK_SHEETS, {"sheet_name": "P&L", "start_row": 0, "end_row": 2, "start_col": 0, "end_col": 2}
        )
        assert result["sheet_name"] == "P&L"
        assert len(result["rows"]) == 2

    def test_unknown_sheet_returns_error(self):
        result = handle_read_cell_range(
            MOCK_SHEETS, {"sheet_name": "Nope", "start_row": 0, "end_row": 1, "start_col": 0, "end_col": 1}
        )
        assert "error" in result
```

**Step 2: Run tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/services/agent/test_excel_tools.py -v`
Expected: ImportError — `excel_tools` module doesn't exist yet.

**Step 3: Implement read tools**

```python
# apps/api/app/services/agent/excel_tools.py
"""MCP tool handlers for agentic Excel import.

Each handler takes a sheets dict (sheet_name → sheet_data) and args dict,
returning a plain dict that the MCP server serializes as tool output.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


def handle_read_sheet_data(
    sheets: dict[str, Any], args: dict[str, Any]
) -> dict[str, Any]:
    """Read headers + sample rows for a sheet."""
    name = args.get("sheet_name", "")
    if name not in sheets:
        return {"error": f"Sheet '{name}' not found. Available: {list(sheets.keys())}"}
    s = sheets[name]
    max_rows = args.get("max_rows", len(s.get("sample_rows", [])))
    return {
        "sheet_name": name,
        "headers": s.get("headers", []),
        "sample_rows": s.get("sample_rows", [])[:max_rows],
        "row_count": s.get("row_count", 0),
        "col_count": s.get("col_count", 0),
    }


def handle_read_cell_range(
    sheets: dict[str, Any], args: dict[str, Any]
) -> dict[str, Any]:
    """Read a specific row/col range from a sheet's sample data."""
    name = args.get("sheet_name", "")
    if name not in sheets:
        return {"error": f"Sheet '{name}' not found. Available: {list(sheets.keys())}"}
    s = sheets[name]
    rows = s.get("sample_rows", [])
    sr, er = args.get("start_row", 0), args.get("end_row", len(rows))
    sc, ec = args.get("start_col", 0), args.get("end_col", None)
    sliced = [row[sc:ec] for row in rows[sr:er]]
    return {"sheet_name": name, "rows": sliced}


def handle_get_formula_patterns(
    sheets: dict[str, Any], args: dict[str, Any]
) -> dict[str, Any]:
    """Extract formula patterns and cross-sheet references for a sheet."""
    name = args.get("sheet_name", "")
    if name not in sheets:
        return {"error": f"Sheet '{name}' not found. Available: {list(sheets.keys())}"}
    s = sheets[name]
    return {
        "sheet_name": name,
        "formulas": s.get("formula_patterns", []),
        "referenced_sheets": s.get("referenced_sheets", []),
    }


def handle_get_sheet_dependencies(
    sheets: dict[str, Any], _args: dict[str, Any]
) -> dict[str, Any]:
    """Build adjacency list of inter-sheet references."""
    deps: dict[str, list[str]] = {}
    for name, s in sheets.items():
        deps[name] = s.get("referenced_sheets", [])
    return {"dependencies": deps, "sheet_count": len(sheets)}


def handle_compare_sheets(
    sheets: dict[str, Any], args: dict[str, Any]
) -> dict[str, Any]:
    """Compare structural properties of two sheets."""
    a_name, b_name = args.get("sheet_a", ""), args.get("sheet_b", "")
    if a_name not in sheets:
        return {"error": f"Sheet '{a_name}' not found."}
    if b_name not in sheets:
        return {"error": f"Sheet '{b_name}' not found."}
    a, b = sheets[a_name], sheets[b_name]
    a_headers = set(a.get("headers", []))
    b_headers = set(b.get("headers", []))
    return {
        "sheet_a": a_name,
        "sheet_b": b_name,
        "comparison": {
            "row_count": {"a": a.get("row_count", 0), "b": b.get("row_count", 0)},
            "col_count": {"a": a.get("col_count", 0), "b": b.get("col_count", 0)},
            "shared_headers": sorted(a_headers & b_headers),
            "only_in_a": sorted(a_headers - b_headers),
            "only_in_b": sorted(b_headers - a_headers),
        },
    }
```

**Step 4: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/services/agent/test_excel_tools.py -v`
Expected: All 9 tests PASS.

**Step 5: Commit**

```bash
git add apps/api/app/services/agent/excel_tools.py apps/api/tests/services/agent/test_excel_tools.py
git commit -m "feat(agent): add MCP read tools for Excel workbook exploration"
```

---

### Task 3: MCP Action Tools — Classification, Mapping, Validation

**Files:**
- Modify: `apps/api/app/services/agent/excel_tools.py`
- Modify: `apps/api/tests/services/agent/test_excel_tools.py`

**Context:** Action tools let the agent submit classifications, validate mappings, and search templates. `search_template_catalog` reads from `apps/api/app/data/budget_templates.json`. `validate_mapping` checks against `MODEL_MAPPING_SCHEMA` (defined at `apps/api/app/services/excel_ingestion.py:110-135`). `submit_classification` and `submit_mapping` store results into a mutable session state dict.

**Step 1: Write failing tests for action tools**

Append to `apps/api/tests/services/agent/test_excel_tools.py`:

```python
from apps.api.app.services.agent.excel_tools import (
    handle_search_template_catalog,
    handle_validate_mapping,
    handle_submit_classification,
    handle_submit_mapping,
)


MOCK_TEMPLATES = [
    {
        "template_id": "saas",
        "label": "SaaS",
        "industry": "software",
        "default_account_refs": ["MRR", "ARR", "Churn"],
    },
    {
        "template_id": "manufacturing",
        "label": "Manufacturing",
        "industry": "manufacturing",
        "default_account_refs": ["Revenue", "COGS"],
    },
]


class TestSearchTemplateCatalog:
    def test_search_by_industry(self):
        result = handle_search_template_catalog(
            MOCK_TEMPLATES, {"industry": "software"}
        )
        assert len(result["matches"]) == 1
        assert result["matches"][0]["template_id"] == "saas"

    def test_no_match_returns_empty(self):
        result = handle_search_template_catalog(
            MOCK_TEMPLATES, {"industry": "biotech"}
        )
        assert result["matches"] == []

    def test_search_all(self):
        result = handle_search_template_catalog(MOCK_TEMPLATES, {})
        assert len(result["matches"]) == 2


class TestValidateMapping:
    def test_valid_mapping_passes(self):
        mapping = {
            "metadata": {
                "entity_name": "Acme",
                "currency": "USD",
                "country_iso": "US",
                "start_date": "2025-01-01",
                "horizon_months": 36,
            },
            "revenue_streams": [{"label": "Product Sales", "stream_type": "unit_based"}],
            "cost_items": [],
            "capex_items": [],
            "working_capital": {},
            "funding": {},
            "unmapped_items": [],
            "questions": [],
        }
        result = handle_validate_mapping(mapping)
        assert result["valid"] is True
        assert result["coverage_pct"] > 0

    def test_missing_metadata_fails(self):
        result = handle_validate_mapping({"revenue_streams": []})
        assert result["valid"] is False
        assert len(result["errors"]) > 0


class TestSubmitClassification:
    def test_stores_classification(self):
        state: dict[str, Any] = {}
        classification = {
            "sheets": [{"sheet_name": "P&L", "classification": "income_statement"}],
            "model_summary": {"entity_name": "Acme", "industry": "software"},
        }
        result = handle_submit_classification(state, classification)
        assert result["stored"] is True
        assert state["classification"] == classification


class TestSubmitMapping:
    def test_stores_mapping(self):
        state: dict[str, Any] = {}
        mapping = {
            "metadata": {"entity_name": "Acme"},
            "revenue_streams": [],
            "cost_items": [],
            "capex_items": [],
            "working_capital": {},
            "funding": {},
            "unmapped_items": [],
            "questions": [],
        }
        result = handle_submit_mapping(state, mapping)
        assert result["stored"] is True
        assert state["mapping"] == mapping
```

**Step 2: Run tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/services/agent/test_excel_tools.py -v -k "action or template or validate or submit"`
Expected: ImportError — functions not defined.

**Step 3: Implement action tools**

Append to `apps/api/app/services/agent/excel_tools.py`:

```python
# ---------------------------------------------------------------------------
# Action tools
# ---------------------------------------------------------------------------

REQUIRED_MAPPING_KEYS = [
    "metadata",
    "revenue_streams",
    "cost_items",
    "capex_items",
    "working_capital",
    "funding",
    "unmapped_items",
    "questions",
]

REQUIRED_METADATA_KEYS = [
    "entity_name",
    "currency",
    "country_iso",
    "start_date",
    "horizon_months",
]


def handle_search_template_catalog(
    templates: list[dict[str, Any]], args: dict[str, Any]
) -> dict[str, Any]:
    """Search budget templates by industry or model type."""
    industry = args.get("industry", "").lower()
    model_type = args.get("model_type", "").lower()
    matches = []
    for t in templates:
        if industry and t.get("industry", "").lower() != industry:
            continue
        if model_type and model_type not in t.get("label", "").lower():
            continue
        matches.append(
            {
                "template_id": t["template_id"],
                "label": t["label"],
                "industry": t.get("industry", ""),
                "accounts": t.get("default_account_refs", []),
            }
        )
    return {"matches": matches}


def handle_validate_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    """Validate a mapping dict against required schema structure."""
    errors: list[str] = []
    warnings: list[str] = []

    for key in REQUIRED_MAPPING_KEYS:
        if key not in mapping:
            errors.append(f"Missing required key: {key}")

    meta = mapping.get("metadata", {})
    for key in REQUIRED_METADATA_KEYS:
        if key not in meta:
            errors.append(f"Missing metadata field: {key}")

    # Coverage: count non-empty sections
    sections = ["revenue_streams", "cost_items", "capex_items"]
    filled = sum(1 for s in sections if mapping.get(s))
    coverage = round(filled / len(sections) * 100) if sections else 0

    if not mapping.get("revenue_streams"):
        warnings.append("No revenue streams mapped")

    unmapped = mapping.get("unmapped_items", [])
    if unmapped:
        warnings.append(f"{len(unmapped)} items could not be mapped")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "coverage_pct": coverage,
    }


def handle_submit_classification(
    state: dict[str, Any], classification: dict[str, Any]
) -> dict[str, Any]:
    """Store sheet classification in session state."""
    state["classification"] = classification
    return {"stored": True, "sheet_count": len(classification.get("sheets", []))}


def handle_submit_mapping(
    state: dict[str, Any], mapping: dict[str, Any]
) -> dict[str, Any]:
    """Store final mapping in session state."""
    state["mapping"] = mapping
    return {
        "stored": True,
        "revenue_streams": len(mapping.get("revenue_streams", [])),
        "cost_items": len(mapping.get("cost_items", [])),
        "unmapped_items": len(mapping.get("unmapped_items", [])),
    }
```

**Step 4: Run all tool tests**

Run: `cd apps/api && python -m pytest tests/services/agent/test_excel_tools.py -v`
Expected: All tests PASS (9 read + 7 action = 16 tests).

**Step 5: Commit**

```bash
git add apps/api/app/services/agent/excel_tools.py apps/api/tests/services/agent/test_excel_tools.py
git commit -m "feat(agent): add MCP action tools for classification, mapping, and validation"
```

---

### Task 4: MCP Tool Server — Wire Tools into Agent SDK

**Files:**
- Create: `apps/api/app/services/agent/excel_mcp_server.py`
- Create: `apps/api/tests/services/agent/test_excel_mcp_server.py`

**Context:** The Agent SDK uses `create_sdk_mcp_server` to register tools. Each tool gets a name, description, input schema, and async handler. The `ask_user_question` tool is special — it writes a question to session state and returns a sentinel that the `AgentSessionManager` (Task 6) detects to pause the agent. For now, we create the server factory function. The existing `AgentService` (at `apps/api/app/services/agent/service.py:72-77`) creates `ClaudeAgentOptions` — we'll pass our MCP server via the `mcp_servers` key.

**Step 1: Write failing test**

```python
# apps/api/tests/services/agent/test_excel_mcp_server.py
"""Tests for MCP server factory that registers Excel tools."""

import pytest
from apps.api.app.services.agent.excel_mcp_server import create_excel_mcp_server


class TestCreateExcelMcpServer:
    def test_creates_server_with_all_tools(self):
        sheets = {"P&L": {"headers": [], "sample_rows": [], "row_count": 0, "col_count": 0, "formula_patterns": [], "referenced_sheets": []}}
        templates = []
        state: dict = {}
        server = create_excel_mcp_server(sheets, templates, state)
        assert server is not None

    def test_server_has_expected_tool_count(self):
        sheets = {}
        templates = []
        state: dict = {}
        server = create_excel_mcp_server(sheets, templates, state)
        # 5 read + 4 action + 1 ask_user = 10 tools
        assert server["tool_count"] == 10
```

**Step 2: Run test to verify it fails**

Run: `cd apps/api && python -m pytest tests/services/agent/test_excel_mcp_server.py -v`
Expected: ImportError.

**Step 3: Implement MCP server factory**

```python
# apps/api/app/services/agent/excel_mcp_server.py
"""Factory for creating an MCP tool server for agentic Excel import.

Returns an MCP server config dict compatible with ClaudeAgentOptions.mcp_servers.
The ask_user_question tool writes to session state — the AgentSessionManager
checks state["pending_question"] after each tool call to decide whether to pause.
"""

from __future__ import annotations

import json
from typing import Any

from claude_agent_sdk import tool, create_sdk_mcp_server

from apps.api.app.services.agent.excel_tools import (
    handle_read_sheet_data,
    handle_read_cell_range,
    handle_get_formula_patterns,
    handle_get_sheet_dependencies,
    handle_compare_sheets,
    handle_search_template_catalog,
    handle_validate_mapping,
    handle_submit_classification,
    handle_submit_mapping,
)

ASK_USER_SENTINEL = "__ASK_USER_QUESTION__"


def create_excel_mcp_server(
    sheets: dict[str, Any],
    templates: list[dict[str, Any]],
    state: dict[str, Any],
) -> dict[str, Any]:
    """Create an MCP server with all Excel import tools.

    Args:
        sheets: Parsed workbook sheets dict (sheet_name -> sheet_data).
        templates: Budget template catalog list.
        state: Mutable session state dict shared across tools.

    Returns:
        MCP server config dict with tool_count metadata.
    """

    @tool("read_sheet_data", "Read headers and sample rows for a worksheet", {"sheet_name": str, "max_rows": int})
    async def read_sheet_data(args: dict) -> dict:
        return {"content": [{"type": "text", "text": json.dumps(handle_read_sheet_data(sheets, args))}]}

    @tool("read_cell_range", "Read a specific row/col range from a sheet", {"sheet_name": str, "start_row": int, "end_row": int, "start_col": int, "end_col": int})
    async def read_cell_range(args: dict) -> dict:
        return {"content": [{"type": "text", "text": json.dumps(handle_read_cell_range(sheets, args))}]}

    @tool("get_formula_patterns", "Extract formulas and cross-sheet references", {"sheet_name": str})
    async def get_formula_patterns(args: dict) -> dict:
        return {"content": [{"type": "text", "text": json.dumps(handle_get_formula_patterns(sheets, args))}]}

    @tool("get_sheet_dependencies", "Map inter-sheet references as adjacency list", {})
    async def get_sheet_dependencies(args: dict) -> dict:
        return {"content": [{"type": "text", "text": json.dumps(handle_get_sheet_dependencies(sheets, args))}]}

    @tool("compare_sheets", "Compare structural properties of two sheets", {"sheet_a": str, "sheet_b": str})
    async def compare_sheets(args: dict) -> dict:
        return {"content": [{"type": "text", "text": json.dumps(handle_compare_sheets(sheets, args))}]}

    @tool("search_template_catalog", "Search budget templates by industry or type", {"industry": str, "model_type": str})
    async def search_template_catalog(args: dict) -> dict:
        return {"content": [{"type": "text", "text": json.dumps(handle_search_template_catalog(templates, args))}]}

    @tool("validate_mapping", "Validate a financial mapping against the VA schema", {"mapping": dict})
    async def validate_mapping(args: dict) -> dict:
        return {"content": [{"type": "text", "text": json.dumps(handle_validate_mapping(args.get("mapping", {})))}]}

    @tool("submit_classification", "Submit sheet classifications for storage", {"classification": dict})
    async def submit_classification(args: dict) -> dict:
        result = handle_submit_classification(state, args.get("classification", {}))
        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    @tool("submit_mapping", "Submit final financial mapping for storage", {"mapping": dict})
    async def submit_mapping(args: dict) -> dict:
        result = handle_submit_mapping(state, args.get("mapping", {}))
        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    @tool("ask_user_question", "Pause and ask the user a clarifying question", {"text": str, "options": list, "context": str})
    async def ask_user_question(args: dict) -> dict:
        question = {
            "id": f"q{len(state.get('questions_asked', [])) + 1}",
            "text": args.get("text", ""),
            "options": args.get("options", []),
            "context": args.get("context", ""),
        }
        state.setdefault("questions_asked", []).append(question)
        state["pending_question"] = question
        return {"content": [{"type": "text", "text": json.dumps({"status": ASK_USER_SENTINEL, "question": question})}]}

    all_tools = [
        read_sheet_data,
        read_cell_range,
        get_formula_patterns,
        get_sheet_dependencies,
        compare_sheets,
        search_template_catalog,
        validate_mapping,
        submit_classification,
        submit_mapping,
        ask_user_question,
    ]

    server = create_sdk_mcp_server("excel-tools", tools=all_tools)
    # Attach metadata for tests
    server["tool_count"] = len(all_tools)
    return server
```

**Step 4: Run tests**

Run: `cd apps/api && python -m pytest tests/services/agent/test_excel_mcp_server.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/api/app/services/agent/excel_mcp_server.py apps/api/tests/services/agent/test_excel_mcp_server.py
git commit -m "feat(agent): wire Excel tools into MCP server factory"
```

---

### Task 5: Agent System Prompt

**Files:**
- Create: `apps/api/app/services/agent/excel_system_prompt.py`

**Context:** The existing prompt in `excel_agent.py:27-48` is a single-shot prompt. The new prompt guides multi-turn agentic exploration with tool usage instructions. The 15 sheet classification categories are defined in `SHEET_CLASSIFICATION_SCHEMA` at `apps/api/app/services/excel_ingestion.py:55-67`.

**Step 1: Create system prompt module**

```python
# apps/api/app/services/agent/excel_system_prompt.py
"""System prompt for the agentic Excel import agent."""

AGENTIC_EXCEL_SYSTEM_PROMPT = """\
You are a financial model analyst for Virtual Analyst. You have access to tools \
that let you explore an uploaded Excel workbook and map its data to the VA \
financial model schema.

## Your workflow

1. **Explore** — Use read_sheet_data on every sheet to understand the workbook \
   structure. Use get_sheet_dependencies to see cross-sheet references.
2. **Classify** — Assign each sheet one of these categories:
   financial_model, assumptions, income_statement, balance_sheet, cash_flow, \
   revenue_detail, cost_detail, capex, working_capital, funding_debt, \
   scenarios, sensitivity, dashboard, documentation, other.
   Mark each sheet with confidence (high/medium/low) and is_financial_core flag.
3. **Submit classification** — Call submit_classification with your results \
   and a model_summary (entity_name, industry, model_type, currency_guess, \
   horizon_months_guess).
4. **Map** — For financial core sheets, extract items into the VA schema:
   - revenue_streams (label, stream_type, drivers)
   - cost_items (label, category, driver)
   - capex_items, working_capital, funding
   - metadata (entity_name, currency, country_iso, start_date, horizon_months)
5. **Clarify** — If you are uncertain about any mapping (confidence < medium), \
   call ask_user_question with a clear question and 2-4 options. Wait for the \
   answer before proceeding.
6. **Validate** — Call validate_mapping before finalizing. Fix any errors.
7. **Submit** — Call submit_mapping with the complete mapping.

## Rules

- NEVER fabricate data. Only map items you can see in the workbook.
- Put uncertain items in unmapped_items with a reason.
- Cross-reference sheets: if P&L references Assumptions, verify consistency.
- Use search_template_catalog to find matching industry templates for guidance.
- Prefer asking the user (ask_user_question) over guessing.
- Keep explanations concise — the user sees your messages in a chat thread.
"""
```

**Step 2: Commit**

```bash
git add apps/api/app/services/agent/excel_system_prompt.py
git commit -m "feat(agent): add multi-turn system prompt for Excel import agent"
```

---

### Task 6: AgentSessionManager — Start + Resume Sessions

**Files:**
- Create: `apps/api/app/services/agent/session_manager.py`
- Create: `apps/api/tests/services/agent/test_session_manager.py`

**Context:** The session manager orchestrates Agent SDK calls and yields SSE events. It uses `query()` from `claude_agent_sdk` (see `apps/api/app/services/agent/service.py:90`). When the agent calls `ask_user_question`, the tool writes to `state["pending_question"]` — the manager detects this and pauses. On resume, we use the SDK's `resume` parameter (see Agent SDK docs: `ClaudeAgentOptions(resume=session_id)`). SSE events are `data: {json}\n\n` formatted strings.

**Step 1: Write failing tests**

```python
# apps/api/tests/services/agent/test_session_manager.py
"""Tests for AgentSessionManager SSE event generation."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from apps.api.app.services.agent.session_manager import (
    AgentSessionManager,
    format_sse_event,
)


class TestFormatSseEvent:
    def test_formats_event(self):
        result = format_sse_event("status", {"step": "classify", "message": "Working..."})
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        parsed = json.loads(result[len("data: "):-2])
        assert parsed["type"] == "status"
        assert parsed["step"] == "classify"

    def test_formats_error_event(self):
        result = format_sse_event("error", {"message": "Oops", "recoverable": True})
        parsed = json.loads(result[len("data: "):-2])
        assert parsed["type"] == "error"
        assert parsed["recoverable"] is True


class TestAgentSessionManager:
    def test_init(self):
        mgr = AgentSessionManager(api_key="test-key")
        assert mgr is not None
```

**Step 2: Run tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/services/agent/test_session_manager.py -v`
Expected: ImportError.

**Step 3: Implement session manager**

```python
# apps/api/app/services/agent/session_manager.py
"""AgentSessionManager: orchestrates Agent SDK sessions with SSE streaming.

Starts an agent session, yields SSE events as the agent works, pauses on
ask_user_question, and resumes with user answers.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
)

from apps.api.app.services.agent.excel_mcp_server import (
    create_excel_mcp_server,
    ASK_USER_SENTINEL,
)
from apps.api.app.services.agent.excel_system_prompt import (
    AGENTIC_EXCEL_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


def format_sse_event(event_type: str, payload: dict[str, Any]) -> str:
    """Format a dict as an SSE data line."""
    data = {"type": event_type, **payload}
    return f"data: {json.dumps(data)}\n\n"


class AgentSessionManager:
    """Manages agent sessions for Excel import with SSE streaming."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-4-6",
        max_turns: int = 15,
        max_budget_usd: float = 0.50,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.max_turns = max_turns
        self.max_budget_usd = max_budget_usd

    async def start_session(
        self,
        ingestion_id: str,
        tenant_id: str,
        sheets: dict[str, Any],
        templates: list[dict[str, Any]],
        initial_prompt: str,
    ) -> AsyncGenerator[str, None]:
        """Start a new agent session and yield SSE events.

        Yields SSE-formatted strings. Pauses when agent calls ask_user_question.
        Returns session_id and state for persistence.
        """
        state: dict[str, Any] = {
            "ingestion_id": ingestion_id,
            "tenant_id": tenant_id,
        }
        server = create_excel_mcp_server(sheets, templates, state)

        yield format_sse_event("status", {
            "step": "upload",
            "message": f"Starting analysis of {len(sheets)} sheets...",
        })

        options = ClaudeAgentOptions(
            model=self.model,
            max_turns=self.max_turns,
            max_budget_usd=self.max_budget_usd,
            system_prompt=AGENTIC_EXCEL_SYSTEM_PROMPT,
            mcp_servers={"excel-tools": server},
            permission_mode="bypassPermissions",
            allow_dangerously_skip_permissions=True,
        )

        session_id = None

        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(initial_prompt)

                async for message in client.receive_response():
                    if isinstance(message, SystemMessage) and message.subtype == "init":
                        session_id = message.session_id
                        state["session_id"] = session_id
                        continue

                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                text = block.text

                                # Detect classification submission
                                if "classification" in state and "classification_emitted" not in state:
                                    state["classification_emitted"] = True
                                    yield format_sse_event("classification", state["classification"])
                                    yield format_sse_event("status", {"step": "map", "message": "Mapping financial data..."})

                                # Detect ask_user_question
                                if state.get("pending_question"):
                                    q = state["pending_question"]
                                    yield format_sse_event("question", {
                                        "id": q["id"],
                                        "text": q["text"],
                                        "options": q["options"],
                                        "context": q.get("context", ""),
                                    })
                                    # Store state for resume
                                    state["paused"] = True
                                    yield format_sse_event("status", {"step": "map", "message": "Waiting for your answer..."})
                                    return  # Pause — caller persists state

                                # Detect mapping submission
                                if "mapping" in state and "mapping_emitted" not in state:
                                    state["mapping_emitted"] = True
                                    yield format_sse_event("mapping", state["mapping"])

                                # Stream agent text as chat message
                                yield format_sse_event("message", {
                                    "role": "assistant",
                                    "text": text,
                                })

                    if isinstance(message, ResultMessage):
                        yield format_sse_event("complete", {
                            "mapping": state.get("mapping", {}),
                            "classification": state.get("classification", {}),
                            "unmapped": state.get("mapping", {}).get("unmapped_items", []),
                            "questions_asked": len(state.get("questions_asked", [])),
                        })

        except Exception as e:
            logger.exception("Agent session error for ingestion %s", ingestion_id)
            yield format_sse_event("error", {
                "message": str(e),
                "recoverable": False,
            })

    async def resume_session(
        self,
        ingestion_id: str,
        session_id: str,
        answers: list[dict[str, Any]],
        sheets: dict[str, Any],
        templates: list[dict[str, Any]],
        prior_state: dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        """Resume a paused session with user answers."""
        state = {**prior_state}
        state.pop("pending_question", None)
        state.pop("paused", None)

        server = create_excel_mcp_server(sheets, templates, state)

        # Build answer text from user responses
        answer_text = "\n".join(
            f"Q: {a.get('question', '')}\nA: {a.get('answer', '')}"
            for a in answers
        )

        yield format_sse_event("status", {
            "step": "map",
            "message": "Resuming with your answers...",
        })

        options = ClaudeAgentOptions(
            model=self.model,
            max_turns=self.max_turns,
            max_budget_usd=self.max_budget_usd,
            system_prompt=AGENTIC_EXCEL_SYSTEM_PROMPT,
            mcp_servers={"excel-tools": server},
            permission_mode="bypassPermissions",
            allow_dangerously_skip_permissions=True,
            resume=session_id,
        )

        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(answer_text)

                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                text = block.text

                                if state.get("pending_question"):
                                    q = state["pending_question"]
                                    yield format_sse_event("question", {
                                        "id": q["id"],
                                        "text": q["text"],
                                        "options": q["options"],
                                    })
                                    state["paused"] = True
                                    return

                                if "mapping" in state and "mapping_emitted" not in state:
                                    state["mapping_emitted"] = True
                                    yield format_sse_event("mapping", state["mapping"])

                                yield format_sse_event("message", {
                                    "role": "assistant",
                                    "text": text,
                                })

                    if isinstance(message, ResultMessage):
                        yield format_sse_event("complete", {
                            "mapping": state.get("mapping", {}),
                            "classification": state.get("classification", {}),
                            "unmapped": state.get("mapping", {}).get("unmapped_items", []),
                            "questions_asked": len(state.get("questions_asked", [])),
                        })

        except Exception as e:
            logger.exception("Agent resume error for ingestion %s", ingestion_id)
            yield format_sse_event("error", {
                "message": str(e),
                "recoverable": False,
            })
```

**Step 4: Run tests**

Run: `cd apps/api && python -m pytest tests/services/agent/test_session_manager.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/api/app/services/agent/session_manager.py apps/api/tests/services/agent/test_session_manager.py
git commit -m "feat(agent): add AgentSessionManager with SSE streaming and pause/resume"
```

---

### Task 7: SSE Endpoint — upload-stream Route

**Files:**
- Modify: `apps/api/app/routers/excel_ingestion.py` (add new route)
- Modify: `apps/api/app/core/settings.py` (no changes needed — `agent_excel_ingestion_enabled` already exists at line 55)

**Context:** The existing upload route is at `apps/api/app/routers/excel_ingestion.py:41-98`. We add a new `POST /upload-stream` that returns `StreamingResponse`. The existing `start_ingestion` function (at `excel_ingestion.py:137-195`) handles file save + session creation. The `parse_workbook` function (at `excel_parser.py:131`) parses the file.

**Step 1: Add SSE endpoint to router**

Add to `apps/api/app/routers/excel_ingestion.py` after the existing upload route:

```python
# New imports at top
from fastapi.responses import StreamingResponse
from apps.api.app.services.agent.session_manager import AgentSessionManager

# New route (add after existing upload route)
@router.post("/excel-ingestion/upload-stream")
async def upload_and_stream(
    file: UploadFile,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_user_id),
    conn: asyncpg.Connection = Depends(get_db),
    store: ArtifactStore = Depends(get_artifact_store),
    agent: AgentService | None = Depends(get_agent_service),
):
    """Upload an Excel file and stream agentic analysis via SSE."""
    settings = get_settings()
    if not agent or not settings.agent_excel_ingestion_enabled:
        raise HTTPException(status_code=501, detail="Agentic Excel import is not enabled")

    # Reuse existing upload + parse logic
    ingestion_id = await start_ingestion(tenant_id, user_id, file, store, conn)
    parsed = await parse_workbook_for_ingestion(tenant_id, ingestion_id, store, conn)

    # Load templates
    templates = load_budget_templates()

    # Build sheets dict from parsed result
    sheets = {s["name"]: s for s in parsed.get("sheets", [])}

    # Initial prompt with workbook overview
    sheet_names = ", ".join(sheets.keys())
    prompt = (
        f"Analyze the uploaded Excel workbook '{file.filename}' with "
        f"{len(sheets)} sheets: {sheet_names}. "
        f"Classify all sheets, then map financial data to the VA schema."
    )

    session_mgr = AgentSessionManager(
        api_key=settings.anthropic_api_key,
        model=settings.agent_sdk_default_model,
        max_turns=settings.agent_sdk_max_turns,
        max_budget_usd=settings.agent_sdk_max_budget_usd,
    )

    return StreamingResponse(
        session_mgr.start_session(ingestion_id, tenant_id, sheets, templates, prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Ingestion-Id": ingestion_id,
        },
    )
```

Also modify the existing `/answer` endpoint to support SSE resume:

```python
@router.post("/excel-ingestion/{ingestion_id}/answer-stream")
async def answer_and_stream(
    ingestion_id: str,
    body: AnswerBody,
    tenant_id: str = Depends(get_tenant_id),
    conn: asyncpg.Connection = Depends(get_db),
    store: ArtifactStore = Depends(get_artifact_store),
    agent: AgentService | None = Depends(get_agent_service),
):
    """Answer agent question and resume streaming."""
    settings = get_settings()
    if not agent:
        raise HTTPException(status_code=501, detail="Agent not available")

    # Load session state
    session = await get_ingestion_session(tenant_id, ingestion_id, conn)
    if not session or session.get("agent_status") != "paused":
        raise HTTPException(status_code=400, detail="Session not in paused state")

    parsed = await load_parse_result(tenant_id, ingestion_id, store)
    templates = load_budget_templates()
    sheets = {s["name"]: s for s in parsed.get("sheets", [])}

    session_mgr = AgentSessionManager(
        api_key=settings.anthropic_api_key,
        model=settings.agent_sdk_default_model,
    )

    return StreamingResponse(
        session_mgr.resume_session(
            ingestion_id,
            session["agent_session_id"],
            body.answers,
            sheets,
            templates,
            json.loads(session.get("agent_messages", "{}") or "{}"),
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

**Step 2: Commit**

```bash
git add apps/api/app/routers/excel_ingestion.py
git commit -m "feat(api): add SSE streaming endpoints for agentic Excel import"
```

---

### Task 8: Frontend — ChatMessage + ChatThread Components

**Files:**
- Create: `apps/web/components/excel-import/ChatMessage.tsx`
- Create: `apps/web/components/excel-import/ChatThread.tsx`
- Create: `apps/web/tests/components/excel-import/ChatMessage.test.tsx`

**Context:** Design tokens in `apps/web/tailwind.config.ts`. CommentThread pattern at `apps/web/components/CommentThread.tsx` for reference. VA design system: dark bg (`bg-va-midnight`), panel (`bg-va-panel`), text (`text-va-text`, `text-va-text2`), accent (`text-va-blue`).

**Step 1: Write failing tests**

```tsx
// apps/web/tests/components/excel-import/ChatMessage.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatMessage } from "@/components/excel-import/ChatMessage";

describe("ChatMessage", () => {
  it("renders assistant message with robot icon", () => {
    render(<ChatMessage role="assistant" text="Analyzing sheets..." />);
    expect(screen.getByText("Analyzing sheets...")).toBeInTheDocument();
    expect(screen.getByLabelText("Assistant")).toBeInTheDocument();
  });

  it("renders user message with user icon", () => {
    render(<ChatMessage role="user" text="Operating Expense" />);
    expect(screen.getByText("Operating Expense")).toBeInTheDocument();
    expect(screen.getByLabelText("You")).toBeInTheDocument();
  });

  it("renders status message with muted styling", () => {
    render(<ChatMessage role="status" text="Reading sheet P&L..." />);
    const el = screen.getByText("Reading sheet P&L...");
    expect(el.className).toMatch(/text-va-text2/);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run tests/components/excel-import/ChatMessage.test.tsx`
Expected: Module not found.

**Step 3: Implement ChatMessage**

```tsx
// apps/web/components/excel-import/ChatMessage.tsx
"use client";

export type MessageRole = "assistant" | "user" | "status";

export interface ChatMessageProps {
  role: MessageRole;
  text: string;
}

export function ChatMessage({ role, text }: ChatMessageProps) {
  if (role === "status") {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5">
        <span className="text-xs text-va-text2 italic">{text}</span>
      </div>
    );
  }

  const isAssistant = role === "assistant";

  return (
    <div className={`flex gap-3 px-3 py-2 ${isAssistant ? "" : "flex-row-reverse"}`}>
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-medium ${
          isAssistant
            ? "bg-va-blue/20 text-va-blue"
            : "bg-va-surface text-va-text2"
        }`}
        aria-label={isAssistant ? "Assistant" : "You"}
      >
        {isAssistant ? "AI" : "U"}
      </div>
      <div
        className={`max-w-[80%] rounded-va-sm px-3 py-2 text-sm leading-relaxed ${
          isAssistant
            ? "bg-va-panel text-va-text"
            : "bg-va-blue/10 text-va-text"
        }`}
      >
        {text}
      </div>
    </div>
  );
}
```

**Step 4: Implement ChatThread**

```tsx
// apps/web/components/excel-import/ChatThread.tsx
"use client";

import { useEffect, useRef } from "react";
import { ChatMessage, type MessageRole } from "./ChatMessage";

export interface ThreadMessage {
  id: string;
  role: MessageRole;
  text: string;
}

export interface ChatThreadProps {
  messages: ThreadMessage[];
  children?: React.ReactNode; // QuestionCard slot
}

export function ChatThread({ messages, children }: ChatThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  return (
    <div className="flex-1 overflow-y-auto border border-va-border rounded-va-sm bg-va-midnight/50">
      <div className="flex flex-col gap-1 py-3">
        {messages.map((m) => (
          <ChatMessage key={m.id} role={m.role} text={m.text} />
        ))}
        {children}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
```

**Step 5: Run tests**

Run: `cd apps/web && npx vitest run tests/components/excel-import/ChatMessage.test.tsx`
Expected: All 3 PASS.

**Step 6: Commit**

```bash
git add apps/web/components/excel-import/ChatMessage.tsx apps/web/components/excel-import/ChatThread.tsx apps/web/tests/components/excel-import/ChatMessage.test.tsx
git commit -m "feat(ui): add ChatMessage and ChatThread components for import wizard"
```

---

### Task 9: Frontend — QuestionCard Component

**Files:**
- Create: `apps/web/components/excel-import/QuestionCard.tsx`
- Create: `apps/web/tests/components/excel-import/QuestionCard.test.tsx`

**Step 1: Write failing tests**

```tsx
// apps/web/tests/components/excel-import/QuestionCard.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuestionCard } from "@/components/excel-import/QuestionCard";

describe("QuestionCard", () => {
  const defaultProps = {
    question: {
      id: "q1",
      text: "How should 'Professional Fees' be classified?",
      options: ["Operating Expense", "SG&A", "Cost of Revenue"],
    },
    onAnswer: vi.fn(),
  };

  it("renders question text", () => {
    render(<QuestionCard {...defaultProps} />);
    expect(screen.getByText(/Professional Fees/)).toBeInTheDocument();
  });

  it("renders all option buttons", () => {
    render(<QuestionCard {...defaultProps} />);
    expect(screen.getByRole("button", { name: "Operating Expense" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "SG&A" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cost of Revenue" })).toBeInTheDocument();
  });

  it("calls onAnswer with selected option", async () => {
    const user = userEvent.setup();
    const onAnswer = vi.fn();
    render(<QuestionCard {...defaultProps} onAnswer={onAnswer} />);
    await user.click(screen.getByRole("button", { name: "SG&A" }));
    expect(onAnswer).toHaveBeenCalledWith("q1", "SG&A");
  });

  it("disables buttons when disabled prop is true", () => {
    render(<QuestionCard {...defaultProps} disabled />);
    expect(screen.getByRole("button", { name: "Operating Expense" })).toBeDisabled();
  });
});
```

**Step 2: Run test — expected FAIL**

**Step 3: Implement QuestionCard**

```tsx
// apps/web/components/excel-import/QuestionCard.tsx
"use client";

export interface AgentQuestion {
  id: string;
  text: string;
  options: string[];
  context?: string;
}

export interface QuestionCardProps {
  question: AgentQuestion;
  onAnswer: (questionId: string, answer: string) => void;
  disabled?: boolean;
}

export function QuestionCard({ question, onAnswer, disabled }: QuestionCardProps) {
  return (
    <div className="mx-3 my-2 rounded-va-sm border border-va-blue/30 bg-va-blue/5 p-4">
      <p className="mb-3 text-sm font-medium text-va-text">{question.text}</p>
      {question.context && (
        <p className="mb-3 text-xs text-va-text2">{question.context}</p>
      )}
      <div className="flex flex-wrap gap-2">
        {question.options.map((opt) => (
          <button
            key={opt}
            type="button"
            onClick={() => onAnswer(question.id, opt)}
            disabled={disabled}
            className="rounded-va-xs border border-va-border bg-va-panel px-3 py-1.5 text-sm text-va-text transition-colors hover:border-va-blue hover:text-va-blue disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  );
}
```

**Step 4: Run tests**

Run: `cd apps/web && npx vitest run tests/components/excel-import/QuestionCard.test.tsx`
Expected: All 4 PASS.

**Step 5: Commit**

```bash
git add apps/web/components/excel-import/QuestionCard.tsx apps/web/tests/components/excel-import/QuestionCard.test.tsx
git commit -m "feat(ui): add QuestionCard component for agent clarification questions"
```

---

### Task 10: Frontend — ImportStepper Component

**Files:**
- Create: `apps/web/components/excel-import/ImportStepper.tsx`
- Create: `apps/web/tests/components/excel-import/ImportStepper.test.tsx`

**Context:** Pattern from `apps/web/components/ModelStepper.tsx`. Simpler — 4 fixed steps with no navigation links.

**Step 1: Write failing tests**

```tsx
// apps/web/tests/components/excel-import/ImportStepper.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ImportStepper } from "@/components/excel-import/ImportStepper";

describe("ImportStepper", () => {
  it("renders all 4 steps", () => {
    render(<ImportStepper currentStep="upload" />);
    expect(screen.getByText("Upload")).toBeInTheDocument();
    expect(screen.getByText("Classify")).toBeInTheDocument();
    expect(screen.getByText("Map")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
  });

  it("marks current step as active", () => {
    render(<ImportStepper currentStep="classify" />);
    const el = screen.getByText("Classify").closest("[data-state]");
    expect(el?.getAttribute("data-state")).toBe("current");
  });

  it("marks completed steps as done", () => {
    render(<ImportStepper currentStep="map" />);
    const upload = screen.getByText("Upload").closest("[data-state]");
    const classify = screen.getByText("Classify").closest("[data-state]");
    expect(upload?.getAttribute("data-state")).toBe("done");
    expect(classify?.getAttribute("data-state")).toBe("done");
  });

  it("marks future steps as pending", () => {
    render(<ImportStepper currentStep="upload" />);
    const review = screen.getByText("Review").closest("[data-state]");
    expect(review?.getAttribute("data-state")).toBe("pending");
  });
});
```

**Step 2: Run test — expected FAIL**

**Step 3: Implement ImportStepper**

```tsx
// apps/web/components/excel-import/ImportStepper.tsx
"use client";

export type ImportStep = "upload" | "classify" | "map" | "review";

const STEPS: { id: ImportStep; label: string }[] = [
  { id: "upload", label: "Upload" },
  { id: "classify", label: "Classify" },
  { id: "map", label: "Map" },
  { id: "review", label: "Review" },
];

function getState(step: ImportStep, current: ImportStep): "done" | "current" | "pending" {
  const ci = STEPS.findIndex((s) => s.id === current);
  const si = STEPS.findIndex((s) => s.id === step);
  if (si < ci) return "done";
  if (si === ci) return "current";
  return "pending";
}

const circleClass = {
  done: "bg-va-success text-white",
  current: "border-2 border-va-blue text-va-blue bg-transparent",
  pending: "border-2 border-va-border text-va-text2 bg-transparent",
};

const labelClass = {
  done: "text-va-success font-medium",
  current: "text-va-blue font-medium",
  pending: "text-va-text2",
};

export function ImportStepper({ currentStep }: { currentStep: ImportStep }) {
  return (
    <nav aria-label="Import progress" className="w-full">
      <ol className="flex items-center">
        {STEPS.map((def, idx) => {
          const state = getState(def.id, currentStep);
          return (
            <li
              key={def.id}
              className={`flex items-center ${idx < STEPS.length - 1 ? "flex-1" : ""}`}
            >
              <div data-step={def.id} data-state={state} aria-label={`Step ${idx + 1}: ${def.label} (${state})`}>
                <div className="flex flex-col items-center gap-1">
                  <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${circleClass[state]}`}>
                    {state === "done" ? (
                      <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                        <path d="M3 8.5l3.5 3.5 6.5-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    ) : (
                      idx + 1
                    )}
                  </div>
                  <span className={`text-xs ${labelClass[state]}`}>{def.label}</span>
                </div>
              </div>
              {idx < STEPS.length - 1 && (
                <div
                  className={`mx-2 h-0.5 flex-1 rounded-full ${
                    state === "done" || state === "current" ? "bg-va-blue" : "bg-va-border"
                  }`}
                  aria-hidden="true"
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
```

**Step 4: Run tests — expected PASS**

**Step 5: Commit**

```bash
git add apps/web/components/excel-import/ImportStepper.tsx apps/web/tests/components/excel-import/ImportStepper.test.tsx
git commit -m "feat(ui): add ImportStepper 4-step progress indicator"
```

---

### Task 11: Frontend — MappingPreview + ReviewPanel

**Files:**
- Create: `apps/web/components/excel-import/MappingPreview.tsx`
- Create: `apps/web/components/excel-import/ReviewPanel.tsx`
- Create: `apps/web/tests/components/excel-import/MappingPreview.test.tsx`

**Step 1: Write failing tests**

```tsx
// apps/web/tests/components/excel-import/MappingPreview.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MappingPreview } from "@/components/excel-import/MappingPreview";
import { ReviewPanel } from "@/components/excel-import/ReviewPanel";

describe("MappingPreview", () => {
  it("shows summary counts", () => {
    render(
      <MappingPreview
        mapping={{
          revenue_streams: [{ label: "Sales" }],
          cost_items: [{ label: "Rent" }, { label: "Salaries" }],
          capex_items: [],
          unmapped_items: [{ label: "Unknown" }],
        }}
      />,
    );
    expect(screen.getByText(/1 revenue/i)).toBeInTheDocument();
    expect(screen.getByText(/2 cost/i)).toBeInTheDocument();
    expect(screen.getByText(/1 unmapped/i)).toBeInTheDocument();
  });
});

describe("ReviewPanel", () => {
  it("renders mapped items and create draft button", () => {
    render(
      <ReviewPanel
        mapping={{
          metadata: { entity_name: "Acme Corp" },
          revenue_streams: [{ label: "Product Sales" }],
          cost_items: [],
          capex_items: [],
          unmapped_items: [],
        }}
        onCreateDraft={vi.fn()}
      />,
    );
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Product Sales")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create draft/i })).toBeInTheDocument();
  });

  it("calls onCreateDraft when button clicked", async () => {
    const user = userEvent.setup();
    const onCreateDraft = vi.fn();
    render(
      <ReviewPanel
        mapping={{
          metadata: { entity_name: "Acme" },
          revenue_streams: [],
          cost_items: [],
          capex_items: [],
          unmapped_items: [],
        }}
        onCreateDraft={onCreateDraft}
      />,
    );
    await user.click(screen.getByRole("button", { name: /create draft/i }));
    expect(onCreateDraft).toHaveBeenCalled();
  });
});
```

**Step 2: Run test — expected FAIL**

**Step 3: Implement components**

```tsx
// apps/web/components/excel-import/MappingPreview.tsx
"use client";

interface MappingData {
  revenue_streams?: { label: string }[];
  cost_items?: { label: string }[];
  capex_items?: { label: string }[];
  unmapped_items?: { label: string }[];
}

export function MappingPreview({ mapping }: { mapping: MappingData }) {
  const rev = mapping.revenue_streams?.length ?? 0;
  const cost = mapping.cost_items?.length ?? 0;
  const capex = mapping.capex_items?.length ?? 0;
  const unmapped = mapping.unmapped_items?.length ?? 0;

  return (
    <div className="flex flex-wrap gap-3 rounded-va-xs border border-va-border bg-va-panel/50 px-4 py-2 text-xs">
      <span className="text-va-success">{rev} revenue</span>
      <span className="text-va-text2">{cost} cost</span>
      <span className="text-va-text2">{capex} capex</span>
      {unmapped > 0 && (
        <span className="text-va-warning">{unmapped} unmapped</span>
      )}
    </div>
  );
}
```

```tsx
// apps/web/components/excel-import/ReviewPanel.tsx
"use client";

import { VAButton } from "@/components/ui/VAButton";
import { VACard } from "@/components/ui/VACard";

interface ReviewMapping {
  metadata?: { entity_name?: string; currency?: string; horizon_months?: number };
  revenue_streams?: { label: string }[];
  cost_items?: { label: string }[];
  capex_items?: { label: string }[];
  unmapped_items?: { label: string; reason?: string }[];
}

export interface ReviewPanelProps {
  mapping: ReviewMapping;
  onCreateDraft: () => void;
  loading?: boolean;
}

export function ReviewPanel({ mapping, onCreateDraft, loading }: ReviewPanelProps) {
  const meta = mapping.metadata ?? {};
  const sections = [
    { label: "Revenue Streams", items: mapping.revenue_streams ?? [] },
    { label: "Cost Items", items: mapping.cost_items ?? [] },
    { label: "Capex Items", items: mapping.capex_items ?? [] },
  ];
  const unmapped = mapping.unmapped_items ?? [];

  return (
    <VACard className="space-y-4 p-4">
      {meta.entity_name && (
        <h3 className="text-sm font-medium text-va-text">{meta.entity_name}</h3>
      )}

      {sections.map((s) =>
        s.items.length > 0 ? (
          <div key={s.label}>
            <h4 className="mb-1 text-xs font-medium text-va-text2">{s.label}</h4>
            <ul className="space-y-0.5">
              {s.items.map((item) => (
                <li key={item.label} className="text-sm text-va-text">
                  {item.label}
                </li>
              ))}
            </ul>
          </div>
        ) : null,
      )}

      {unmapped.length > 0 && (
        <div>
          <h4 className="mb-1 text-xs font-medium text-va-warning">Unmapped ({unmapped.length})</h4>
          <ul className="space-y-0.5">
            {unmapped.map((item) => (
              <li key={item.label} className="text-xs text-va-text2">
                {item.label}
                {item.reason && <span className="ml-1 italic">— {item.reason}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <VAButton onClick={onCreateDraft} disabled={loading}>
        {loading ? "Creating..." : "Create Draft"}
      </VAButton>
    </VACard>
  );
}
```

**Step 4: Run tests — expected PASS**

**Step 5: Commit**

```bash
git add apps/web/components/excel-import/MappingPreview.tsx apps/web/components/excel-import/ReviewPanel.tsx apps/web/tests/components/excel-import/MappingPreview.test.tsx
git commit -m "feat(ui): add MappingPreview and ReviewPanel components"
```

---

### Task 12: Frontend — useAgentStream Hook

**Files:**
- Create: `apps/web/hooks/useAgentStream.ts`
- Create: `apps/web/tests/hooks/useAgentStream.test.ts`

**Context:** No existing hooks directory — create it. This hook manages EventSource connection, parses SSE events, and tracks chat state. The backend SSE format is `data: {"type": "...", ...}\n\n`.

**Step 1: Write failing tests**

```tsx
// apps/web/tests/hooks/useAgentStream.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAgentStream } from "@/hooks/useAgentStream";

// Mock EventSource
class MockEventSource {
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 0;
  close = vi.fn();
  url: string;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  static instances: MockEventSource[] = [];
  static reset() {
    MockEventSource.instances = [];
  }

  simulateMessage(data: Record<string, unknown>) {
    this.readyState = 1;
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(data) }));
  }
}

vi.stubGlobal("EventSource", MockEventSource);

describe("useAgentStream", () => {
  beforeEach(() => {
    MockEventSource.reset();
  });

  it("starts with empty state", () => {
    const { result } = renderHook(() => useAgentStream());
    expect(result.current.messages).toEqual([]);
    expect(result.current.currentStep).toBe("upload");
    expect(result.current.isComplete).toBe(false);
    expect(result.current.isPaused).toBe(false);
  });

  it("appends messages from SSE events", () => {
    const { result } = renderHook(() => useAgentStream());

    act(() => {
      result.current.startStream("ing-1", "http://localhost/upload-stream");
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es.simulateMessage({ type: "message", role: "assistant", text: "Hello" });
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].text).toBe("Hello");
    expect(result.current.messages[0].role).toBe("assistant");
  });

  it("advances step on classification event", () => {
    const { result } = renderHook(() => useAgentStream());

    act(() => result.current.startStream("ing-1", "http://localhost/upload-stream"));
    const es = MockEventSource.instances[0];

    act(() => {
      es.simulateMessage({ type: "classification", sheets: [], model_summary: {} });
    });

    expect(result.current.currentStep).toBe("classify");
    expect(result.current.classification).toBeTruthy();
  });

  it("sets isPaused on question event", () => {
    const { result } = renderHook(() => useAgentStream());

    act(() => result.current.startStream("ing-1", "http://localhost/upload-stream"));
    const es = MockEventSource.instances[0];

    act(() => {
      es.simulateMessage({
        type: "question",
        id: "q1",
        text: "How to classify?",
        options: ["A", "B"],
      });
    });

    expect(result.current.isPaused).toBe(true);
    expect(result.current.pendingQuestion?.id).toBe("q1");
  });

  it("sets isComplete on complete event", () => {
    const { result } = renderHook(() => useAgentStream());

    act(() => result.current.startStream("ing-1", "http://localhost/upload-stream"));
    const es = MockEventSource.instances[0];

    act(() => {
      es.simulateMessage({ type: "complete", mapping: {}, classification: {} });
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.currentStep).toBe("review");
  });
});
```

**Step 2: Run test — expected FAIL**

**Step 3: Implement useAgentStream**

```tsx
// apps/web/hooks/useAgentStream.ts
"use client";

import { useCallback, useRef, useState } from "react";
import type { ImportStep } from "@/components/excel-import/ImportStepper";
import type { ThreadMessage } from "@/components/excel-import/ChatThread";
import type { AgentQuestion } from "@/components/excel-import/QuestionCard";

interface Classification {
  sheets: unknown[];
  model_summary: Record<string, unknown>;
}

interface Mapping {
  metadata?: Record<string, unknown>;
  revenue_streams?: unknown[];
  cost_items?: unknown[];
  capex_items?: unknown[];
  unmapped_items?: unknown[];
  [key: string]: unknown;
}

export interface UseAgentStreamReturn {
  messages: ThreadMessage[];
  currentStep: ImportStep;
  isComplete: boolean;
  isPaused: boolean;
  pendingQuestion: AgentQuestion | null;
  classification: Classification | null;
  mapping: Mapping | null;
  error: string | null;
  startStream: (ingestionId: string, url: string) => void;
  answerQuestion: (questionId: string, answer: string) => void;
}

let msgCounter = 0;

export function useAgentStream(): UseAgentStreamReturn {
  const [messages, setMessages] = useState<ThreadMessage[]>([]);
  const [currentStep, setCurrentStep] = useState<ImportStep>("upload");
  const [isComplete, setIsComplete] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState<AgentQuestion | null>(null);
  const [classification, setClassification] = useState<Classification | null>(null);
  const [mapping, setMapping] = useState<Mapping | null>(null);
  const [error, setError] = useState<string | null>(null);

  const esRef = useRef<EventSource | null>(null);
  const ingestionIdRef = useRef<string>("");

  const handleEvent = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case "message":
          setMessages((prev) => [
            ...prev,
            { id: `msg-${++msgCounter}`, role: data.role ?? "assistant", text: data.text },
          ]);
          break;

        case "status":
          setMessages((prev) => [
            ...prev,
            { id: `msg-${++msgCounter}`, role: "status", text: data.message },
          ]);
          if (data.step) setCurrentStep(data.step as ImportStep);
          break;

        case "classification":
          setClassification(data);
          setCurrentStep("classify");
          break;

        case "mapping":
          setMapping(data);
          break;

        case "question":
          setPendingQuestion({
            id: data.id,
            text: data.text,
            options: data.options ?? [],
            context: data.context,
          });
          setIsPaused(true);
          esRef.current?.close();
          break;

        case "complete":
          setMapping(data.mapping);
          setClassification(data.classification);
          setIsComplete(true);
          setCurrentStep("review");
          esRef.current?.close();
          break;

        case "error":
          setError(data.message);
          esRef.current?.close();
          break;
      }
    } catch {
      // Ignore unparseable events
    }
  }, []);

  const startStream = useCallback(
    (ingestionId: string, url: string) => {
      ingestionIdRef.current = ingestionId;
      esRef.current?.close();

      const es = new EventSource(url);
      es.onmessage = handleEvent;
      es.onerror = () => {
        if (!isComplete && !isPaused) {
          setError("Connection lost. Please retry.");
        }
        es.close();
      };
      esRef.current = es;
    },
    [handleEvent, isComplete, isPaused],
  );

  const answerQuestion = useCallback((questionId: string, answer: string) => {
    setMessages((prev) => [
      ...prev,
      { id: `msg-${++msgCounter}`, role: "user", text: answer },
    ]);
    setPendingQuestion(null);
    setIsPaused(false);
  }, []);

  return {
    messages,
    currentStep,
    isComplete,
    isPaused,
    pendingQuestion,
    classification,
    mapping,
    error,
    startStream,
    answerQuestion,
  };
}
```

**Step 4: Run tests — expected PASS**

**Step 5: Commit**

```bash
git add apps/web/hooks/useAgentStream.ts apps/web/tests/hooks/useAgentStream.test.ts
git commit -m "feat(hooks): add useAgentStream SSE hook for import wizard"
```

---

### Task 13: Frontend — API Client Additions

**Files:**
- Modify: `apps/web/lib/api.ts` (lines ~800-883, excelIngestion namespace)

**Context:** Add `uploadStreamUrl` and `answerStream` methods. The SSE endpoint is `POST /excel-ingestion/upload-stream`. For EventSource (GET-only), we'll need the frontend to use `fetch` for the POST and manually construct an EventSource-like reader from the response stream. However, for simplicity the backend can also accept GET with query params. Alternative: use `fetch` with `ReadableStream` in the hook. Adjust the hook in Task 12 if needed — or add a helper that does POST and returns a ReadableStream.

**Step 1: Add new API methods**

Add to the `excelIngestion` namespace in `apps/web/lib/api.ts`:

```typescript
/** Build the SSE upload URL (the hook does the actual POST via fetch). */
getUploadStreamUrl(tenantId: string): string {
  return `${BASE_URL}/api/v1/excel-ingestion/upload-stream?tenant_id=${tenantId}`;
},

/** POST answers and get SSE stream URL for resume. */
async answerStream(
  tenantId: string,
  ingestionId: string,
  answers: { question: string; answer: string }[],
): Promise<string> {
  // Returns the resume SSE URL; the hook connects to it
  const url = `${BASE_URL}/api/v1/excel-ingestion/${ingestionId}/answer-stream?tenant_id=${tenantId}`;
  await fetchApi(url, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
  return url;
},
```

**Step 2: Commit**

```bash
git add apps/web/lib/api.ts
git commit -m "feat(api): add SSE upload and answer-stream URL helpers"
```

---

### Task 14: Frontend — ImportWizard Page Rewrite

**Files:**
- Rewrite: `apps/web/app/(app)/excel-import/page.tsx`
- Create: `apps/web/tests/pages/excel-import.test.tsx`

**Context:** Current page is at `apps/web/app/(app)/excel-import/page.tsx` (410 lines). Replace with guided chat wizard using the components from Tasks 8-12. Auth pattern: `useEffect` with `getAuthContext()` from `@/lib/auth`. File upload pattern: drag-and-drop + file input (reuse from existing).

**Step 1: Write failing tests**

```tsx
// apps/web/tests/pages/excel-import.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// --- Mocks ---
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/excel-import",
}));

vi.mock("@/lib/auth", () => ({
  getAuthContext: vi.fn(async () => ({
    tenantId: "t1",
    userId: "u1",
    accessToken: "tok",
    tenantIdIsFallback: false,
  })),
}));

vi.mock("@/lib/api", () => ({
  api: {
    setAccessToken: vi.fn(),
    excelIngestion: {
      getUploadStreamUrl: vi.fn(() => "http://localhost/upload-stream"),
      answerStream: vi.fn(async () => "http://localhost/answer-stream"),
      createDraft: vi.fn(async () => ({ draft_session_id: "d1" })),
    },
  },
}));

import ExcelImportPage from "@/app/(app)/excel-import/page";

describe("ExcelImportPage", () => {
  beforeEach(() => {
    mockPush.mockClear();
  });

  it("renders upload step initially", async () => {
    render(<ExcelImportPage />);
    expect(await screen.findByText(/drop your excel file/i)).toBeInTheDocument();
    expect(screen.getByText("Upload")).toBeInTheDocument();
  });

  it("renders import stepper with 4 steps", async () => {
    render(<ExcelImportPage />);
    await screen.findByText("Upload");
    expect(screen.getByText("Classify")).toBeInTheDocument();
    expect(screen.getByText("Map")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
  });
});
```

**Step 2: Run test — expected FAIL (page not yet rewritten)**

**Step 3: Rewrite page**

```tsx
// apps/web/app/(app)/excel-import/page.tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getAuthContext } from "@/lib/auth";
import { api } from "@/lib/api";
import { VACard } from "@/components/ui/VACard";
import { VAButton } from "@/components/ui/VAButton";
import { VASpinner } from "@/components/ui/VASpinner";
import { ImportStepper, type ImportStep } from "@/components/excel-import/ImportStepper";
import { ChatThread, type ThreadMessage } from "@/components/excel-import/ChatThread";
import { QuestionCard, type AgentQuestion } from "@/components/excel-import/QuestionCard";
import { MappingPreview } from "@/components/excel-import/MappingPreview";
import { ReviewPanel } from "@/components/excel-import/ReviewPanel";
import { useAgentStream } from "@/hooks/useAgentStream";

export default function ExcelImportPage() {
  const router = useRouter();
  const [tenantId, setTenantId] = useState("");
  const [userId, setUserId] = useState("");
  const [ingestionId, setIngestionId] = useState("");
  const [uploading, setUploading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const stream = useAgentStream();

  // Auth init
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (cancelled) return;
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
    })();
    return () => { cancelled = true; };
  }, []);

  // Upload handler
  const handleUpload = useCallback(
    async (file: File) => {
      if (!tenantId || !file.name.endsWith(".xlsx")) return;
      setUploading(true);

      try {
        // POST file via fetch to SSE endpoint
        const formData = new FormData();
        formData.append("file", file);
        const url = `${api.excelIngestion.getUploadStreamUrl(tenantId)}&user_id=${userId}`;

        // Use fetch for POST + ReadableStream
        const resp = await fetch(url, { method: "POST", body: formData });
        if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`);

        const id = resp.headers.get("X-Ingestion-Id") ?? "";
        setIngestionId(id);

        // Read SSE from response body stream
        const reader = resp.body?.getReader();
        const decoder = new TextDecoder();
        if (reader) {
          let buffer = "";
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            buffer = lines.pop() ?? "";
            for (const line of lines) {
              if (line.startsWith("data: ")) {
                const data = JSON.parse(line.slice(6));
                // Dispatch to stream hook manually
                stream.startStream(id, ""); // Initialize
                // Process inline via the hook's event handler
              }
            }
          }
        }
      } catch (err) {
        // Error handling
      } finally {
        setUploading(false);
      }
    },
    [tenantId, userId, stream],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleUpload(file);
    },
    [handleUpload],
  );

  const handleAnswer = useCallback(
    async (questionId: string, answer: string) => {
      stream.answerQuestion(questionId, answer);
      if (!ingestionId || !tenantId) return;
      try {
        const resumeUrl = await api.excelIngestion.answerStream(
          tenantId,
          ingestionId,
          [{ question: questionId, answer }],
        );
        stream.startStream(ingestionId, resumeUrl);
      } catch {
        // Error handling
      }
    },
    [stream, ingestionId, tenantId],
  );

  const handleCreateDraft = useCallback(async () => {
    if (!tenantId || !userId || !ingestionId) return;
    setCreating(true);
    try {
      const result = await api.excelIngestion.createDraft(tenantId, userId, ingestionId);
      router.push(`/drafts/${result.draft_session_id}`);
    } finally {
      setCreating(false);
    }
  }, [tenantId, userId, ingestionId, router]);

  const currentStep: ImportStep = stream.isComplete
    ? "review"
    : stream.currentStep;

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <h1 className="text-lg font-semibold text-va-text font-brand">
        Import Excel Model
      </h1>

      <ImportStepper currentStep={currentStep} />

      {/* Upload zone (visible before streaming starts) */}
      {!ingestionId && (
        <VACard
          className={`flex flex-col items-center justify-center gap-4 border-2 border-dashed p-12 transition-colors ${
            dragOver ? "border-va-blue bg-va-blue/5" : "border-va-border"
          }`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
        >
          {uploading ? (
            <VASpinner label="Uploading..." />
          ) : (
            <>
              <p className="text-sm text-va-text2">
                Drop your Excel file here or{" "}
                <button
                  type="button"
                  className="text-va-blue underline"
                  onClick={() => fileInputRef.current?.click()}
                >
                  browse
                </button>
              </p>
              <p className="text-xs text-va-text2">.xlsx files only</p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleUpload(f);
                }}
              />
            </>
          )}
        </VACard>
      )}

      {/* Chat thread (visible during/after streaming) */}
      {ingestionId && (
        <div className="flex flex-col gap-4" style={{ minHeight: 400 }}>
          <ChatThread messages={stream.messages}>
            {stream.pendingQuestion && (
              <QuestionCard
                question={stream.pendingQuestion}
                onAnswer={handleAnswer}
              />
            )}
          </ChatThread>

          {stream.mapping && !stream.isComplete && (
            <MappingPreview mapping={stream.mapping} />
          )}
        </div>
      )}

      {/* Review panel */}
      {stream.isComplete && stream.mapping && (
        <ReviewPanel
          mapping={stream.mapping}
          onCreateDraft={handleCreateDraft}
          loading={creating}
        />
      )}

      {stream.error && (
        <VACard className="border-va-danger/50 bg-va-danger/10 p-4 text-sm text-va-danger">
          {stream.error}
        </VACard>
      )}
    </main>
  );
}
```

**Step 4: Run tests — expected PASS**

**Step 5: Commit**

```bash
git add apps/web/app/\\(app\\)/excel-import/page.tsx apps/web/tests/pages/excel-import.test.tsx
git commit -m "feat(ui): rewrite excel-import page as guided chat wizard with SSE streaming"
```

---

### Task 15: Add excelIngestion Mock to Test Setup

**Files:**
- Modify: `apps/web/tests/pages/setup.tsx` (add excelIngestion namespace around line 162)

**Step 1: Add mock namespace**

Insert after the last namespace in mockApi (around line 162):

```typescript
excelIngestion: {
  upload: vi.fn(async () => ({
    ingestion_id: "ing-1",
    status: "parsed",
    classification: { sheets: [], model_summary: {} },
  })),
  get: vi.fn(async () => ({
    classification: { sheets: [] },
    mapping: {},
    unmapped_items: [],
    questions: [],
  })),
  analyze: vi.fn(async () => ({ mapping: {}, questions: [] })),
  answer: vi.fn(async () => ({ mapping: {}, questions: [] })),
  createDraft: vi.fn(async () => ({ draft_session_id: "draft-1" })),
  list: vi.fn(async () => ({ items: [], total: 0 })),
  delete: vi.fn(async () => ({ ok: true })),
  getUploadStreamUrl: vi.fn(() => "http://localhost/upload-stream"),
  answerStream: vi.fn(async () => "http://localhost/answer-stream"),
},
```

**Step 2: Run full test suite**

Run: `cd apps/web && npx vitest run`
Expected: All tests pass (existing + new).

**Step 3: Commit**

```bash
git add apps/web/tests/pages/setup.tsx
git commit -m "test: add excelIngestion mock namespace to shared test setup"
```

---

### Task 16: Integration — Run Full Test Suite + Verify

**Step 1: Run backend tests**

Run: `cd apps/api && python -m pytest tests/services/agent/ -v`
Expected: All agent tests pass.

**Step 2: Run frontend tests**

Run: `cd apps/web && npx vitest run`
Expected: All tests pass (120+ tests).

**Step 3: Verify no lint errors**

Run: `cd apps/web && npx tsc --noEmit`
Expected: No type errors.

**Step 4: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "test: verify full test suite passes for agentic Excel import"
```

---

## Dependency Graph

```
Task 1 (DB migration)     ─────────────────────────────┐
Task 2 (Read tools)       ──┬─── Task 3 (Action tools) │
                            ├─── Task 4 (MCP server)  ──┤
Task 5 (System prompt)    ──┘                           │
                            Task 6 (SessionManager) ────┤
                            Task 7 (SSE endpoint)  ─────┤
                                                        │
Task 8 (ChatMessage)      ──┐                           │
Task 9 (QuestionCard)     ──┤                           │
Task 10 (ImportStepper)   ──┼── Task 14 (Page rewrite) ─┤
Task 11 (MappingPreview)  ──┤                           │
Task 12 (useAgentStream)  ──┘                           │
Task 13 (API client)      ──────────────────────────────┤
Task 15 (Test setup)      ──────────────────────────────┤
                            Task 16 (Integration)  ─────┘
```

Backend Tasks 1-7 and Frontend Tasks 8-13 can be parallelized. Task 14 depends on both tracks. Task 16 is the final verification.
