"""Tests for MCP read and action tool handlers for agentic Excel import.

Pure-function handlers: no async, no DB, no external imports.
"""

from __future__ import annotations

from apps.api.app.services.agent.excel_tools import (
    handle_compare_sheets,
    handle_get_formula_patterns,
    handle_get_sheet_dependencies,
    handle_read_cell_range,
    handle_read_sheet_data,
    handle_search_template_catalog,
    handle_submit_classification,
    handle_submit_mapping,
    handle_validate_mapping,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_SHEETS: dict[str, dict] = {
    "P&L": {
        "name": "P&L",
        "headers": ["Account", "Q1", "Q2", "Q3"],
        "sample_rows": [
            ["Revenue", 100_000, 120_000, 140_000],
            ["COGS", -40_000, -48_000, -56_000],
            ["Gross Profit", 60_000, 72_000, 84_000],
            ["OpEx", -20_000, -22_000, -25_000],
            ["Net Income", 40_000, 50_000, 59_000],
        ],
        "row_count": 45,
        "col_count": 4,
        "formula_patterns": [
            {"pattern": "=Revenue-COGS", "count": 3, "description": "Gross profit calc"},
        ],
        "referenced_sheets": ["Assumptions"],
    },
    "Balance Sheet": {
        "name": "Balance Sheet",
        "headers": ["Account", "2024", "2025"],
        "sample_rows": [
            ["Cash", 500_000, 600_000],
            ["Receivables", 80_000, 95_000],
            ["Total Assets", 580_000, 695_000],
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
            ["Growth Rate", 0.15],
            ["Tax Rate", 0.21],
            ["Discount Rate", 0.10],
        ],
        "row_count": 10,
        "col_count": 2,
        "formula_patterns": [],
        "referenced_sheets": [],
    },
}

MOCK_TEMPLATES: list[dict] = [
    {
        "template_id": "tpl_saas_001",
        "label": "SaaS Startup",
        "industry": "software",
        "model_type": "saas",
        "accounts": ["MRR", "Churn", "CAC", "LTV"],
    },
    {
        "template_id": "tpl_mfg_001",
        "label": "Manufacturing Co",
        "industry": "manufacturing",
        "model_type": "manufacturing",
        "accounts": ["Units Produced", "COGS per Unit", "Inventory"],
    },
]


# ===================================================================
# Task 2 — Read Tools
# ===================================================================


class TestHandleReadSheetData:
    """handle_read_sheet_data: returns sheet metadata + sample rows."""

    def test_returns_sheet_data(self):
        result = handle_read_sheet_data(MOCK_SHEETS, {"sheet_name": "P&L"})
        assert result["headers"] == ["Account", "Q1", "Q2", "Q3"]
        assert result["row_count"] == 45
        assert result["col_count"] == 4
        assert len(result["sample_rows"]) == 5  # all rows returned (< default max)

    def test_max_rows_limits_output(self):
        result = handle_read_sheet_data(MOCK_SHEETS, {"sheet_name": "P&L", "max_rows": 2})
        assert len(result["sample_rows"]) == 2
        assert result["sample_rows"][0][0] == "Revenue"

    def test_unknown_sheet_returns_error(self):
        result = handle_read_sheet_data(MOCK_SHEETS, {"sheet_name": "Missing"})
        assert "error" in result
        assert "Missing" in result["error"]


class TestHandleReadCellRange:
    """handle_read_cell_range: returns sliced sub-range of sample rows."""

    def test_full_range(self):
        result = handle_read_cell_range(
            MOCK_SHEETS,
            {"sheet_name": "P&L", "start_row": 0, "end_row": 2, "start_col": 0, "end_col": 2},
        )
        assert len(result["data"]) == 2
        assert result["data"][0] == ["Revenue", 100_000]

    def test_single_cell(self):
        # Row 1 = COGS row, col 1 = Q1 value (-40_000)
        result = handle_read_cell_range(
            MOCK_SHEETS,
            {"sheet_name": "P&L", "start_row": 1, "end_row": 2, "start_col": 1, "end_col": 2},
        )
        assert result["data"] == [[-40_000]]

    def test_defaults_to_full_range(self):
        result = handle_read_cell_range(MOCK_SHEETS, {"sheet_name": "Assumptions"})
        assert len(result["data"]) == 3
        assert result["data"][0] == ["Growth Rate", 0.15]

    def test_unknown_sheet_returns_error(self):
        result = handle_read_cell_range(MOCK_SHEETS, {"sheet_name": "Nope"})
        assert "error" in result


class TestHandleGetFormulaPatterns:
    """handle_get_formula_patterns: returns formulas + cross-sheet refs."""

    def test_sheet_with_formulas(self):
        result = handle_get_formula_patterns(MOCK_SHEETS, {"sheet_name": "P&L"})
        assert len(result["formula_patterns"]) == 1
        assert result["formula_patterns"][0]["pattern"] == "=Revenue-COGS"
        assert result["referenced_sheets"] == ["Assumptions"]

    def test_sheet_without_formulas(self):
        result = handle_get_formula_patterns(MOCK_SHEETS, {"sheet_name": "Assumptions"})
        assert result["formula_patterns"] == []
        assert result["referenced_sheets"] == []

    def test_unknown_sheet_returns_error(self):
        result = handle_get_formula_patterns(MOCK_SHEETS, {"sheet_name": "Ghost"})
        assert "error" in result


class TestHandleGetSheetDependencies:
    """handle_get_sheet_dependencies: returns adjacency dict of all sheets."""

    def test_dependency_graph(self):
        result = handle_get_sheet_dependencies(MOCK_SHEETS, {})
        assert result["dependencies"]["P&L"] == ["Assumptions"]
        assert result["dependencies"]["Balance Sheet"] == ["P&L"]
        assert result["dependencies"]["Assumptions"] == []

    def test_all_sheets_present(self):
        result = handle_get_sheet_dependencies(MOCK_SHEETS, {})
        assert set(result["dependencies"].keys()) == {"P&L", "Balance Sheet", "Assumptions"}


class TestHandleCompareSheets:
    """handle_compare_sheets: structural comparison between two sheets."""

    def test_compare_pl_vs_balance_sheet(self):
        result = handle_compare_sheets(
            MOCK_SHEETS, {"sheet_a": "P&L", "sheet_b": "Balance Sheet"}
        )
        assert result["sheet_a"]["row_count"] == 45
        assert result["sheet_b"]["row_count"] == 32
        assert result["sheet_a"]["col_count"] == 4
        assert result["sheet_b"]["col_count"] == 3
        # "Account" is in both header lists
        assert "Account" in result["shared_headers"]
        # "Q1" is only in P&L
        assert "Q1" in result["only_in_a"]
        # "2024" is only in Balance Sheet
        assert "2024" in result["only_in_b"]

    def test_compare_identical_sheets(self):
        result = handle_compare_sheets(
            MOCK_SHEETS, {"sheet_a": "P&L", "sheet_b": "P&L"}
        )
        assert result["only_in_a"] == []
        assert result["only_in_b"] == []
        assert set(result["shared_headers"]) == {"Account", "Q1", "Q2", "Q3"}

    def test_unknown_sheet_a(self):
        result = handle_compare_sheets(
            MOCK_SHEETS, {"sheet_a": "Nope", "sheet_b": "P&L"}
        )
        assert "error" in result

    def test_unknown_sheet_b(self):
        result = handle_compare_sheets(
            MOCK_SHEETS, {"sheet_a": "P&L", "sheet_b": "Nope"}
        )
        assert "error" in result


# ===================================================================
# Task 3 — Action Tools
# ===================================================================


class TestHandleSearchTemplateCatalog:
    """handle_search_template_catalog: filter templates by industry/model_type."""

    def test_filter_by_industry(self):
        result = handle_search_template_catalog(MOCK_TEMPLATES, {"industry": "software"})
        assert len(result["matches"]) == 1
        assert result["matches"][0]["template_id"] == "tpl_saas_001"

    def test_filter_by_model_type(self):
        result = handle_search_template_catalog(MOCK_TEMPLATES, {"model_type": "manufacturing"})
        assert len(result["matches"]) == 1
        assert result["matches"][0]["template_id"] == "tpl_mfg_001"

    def test_filter_by_both(self):
        result = handle_search_template_catalog(
            MOCK_TEMPLATES, {"industry": "software", "model_type": "saas"}
        )
        assert len(result["matches"]) == 1

    def test_no_match(self):
        result = handle_search_template_catalog(MOCK_TEMPLATES, {"industry": "healthcare"})
        assert len(result["matches"]) == 0

    def test_no_filter_returns_all(self):
        result = handle_search_template_catalog(MOCK_TEMPLATES, {})
        assert len(result["matches"]) == 2

    def test_returned_fields(self):
        result = handle_search_template_catalog(MOCK_TEMPLATES, {"industry": "software"})
        match = result["matches"][0]
        assert "template_id" in match
        assert "label" in match
        assert "industry" in match
        assert "accounts" in match


class TestHandleValidateMapping:
    """handle_validate_mapping: validates mapping dict structure."""

    @staticmethod
    def _valid_mapping() -> dict:
        return {
            "metadata": {
                "entity_name": "Acme Corp",
                "currency": "USD",
                "country_iso": "US",
                "start_date": "2026-01-01",
                "horizon_months": 36,
            },
            "revenue_streams": [{"label": "Product Sales"}],
            "cost_items": [{"label": "COGS"}],
            "capex_items": [],
            "working_capital": {"ar_days": 30, "ap_days": 45, "inventory_days": 15},
            "funding": {},
            "unmapped_items": [],
            "questions": [],
        }

    def test_valid_mapping(self):
        result = handle_validate_mapping(self._valid_mapping())
        assert result["valid"] is True
        assert result["errors"] == []

    def test_missing_top_level_key(self):
        m = self._valid_mapping()
        del m["revenue_streams"]
        result = handle_validate_mapping(m)
        assert result["valid"] is False
        assert any("revenue_streams" in e for e in result["errors"])

    def test_missing_metadata_field(self):
        m = self._valid_mapping()
        del m["metadata"]["currency"]
        result = handle_validate_mapping(m)
        assert result["valid"] is False
        assert any("currency" in e for e in result["errors"])

    def test_missing_metadata_entirely(self):
        m = self._valid_mapping()
        del m["metadata"]
        result = handle_validate_mapping(m)
        assert result["valid"] is False
        assert any("metadata" in e for e in result["errors"])

    def test_coverage_pct(self):
        result = handle_validate_mapping(self._valid_mapping())
        assert isinstance(result["coverage_pct"], (int, float))
        assert 0 <= result["coverage_pct"] <= 100

    def test_empty_mapping_has_low_coverage(self):
        m = self._valid_mapping()
        m["revenue_streams"] = []
        m["cost_items"] = []
        m["capex_items"] = []
        result = handle_validate_mapping(m)
        # Still valid structure, but lower coverage
        assert result["valid"] is True
        assert result["coverage_pct"] < 100

    def test_warnings_for_empty_sections(self):
        m = self._valid_mapping()
        m["revenue_streams"] = []
        m["cost_items"] = []
        result = handle_validate_mapping(m)
        assert len(result["warnings"]) > 0


class TestHandleSubmitClassification:
    """handle_submit_classification: stores classification in mutable state."""

    def test_stores_classification(self):
        state: dict = {}
        classification = {
            "sheets": [
                {"name": "P&L", "type": "income_statement", "confidence": "high"},
            ],
            "model_summary": {"entity_name": "Acme", "industry": "software"},
        }
        result = handle_submit_classification(state, classification)
        assert result["stored"] is True
        assert state["classification"] == classification

    def test_overwrites_previous(self):
        state: dict = {"classification": {"old": True}}
        new_classification = {"sheets": [], "model_summary": {}}
        handle_submit_classification(state, new_classification)
        assert state["classification"] == new_classification
        assert "old" not in state["classification"]


class TestHandleSubmitMapping:
    """handle_submit_mapping: stores mapping in mutable state with counts."""

    def test_stores_mapping(self):
        state: dict = {}
        mapping = {
            "metadata": {"entity_name": "Test"},
            "revenue_streams": [{"label": "A"}, {"label": "B"}],
            "cost_items": [{"label": "C"}],
            "capex_items": [],
            "working_capital": {},
            "funding": {},
            "unmapped_items": [{"label": "X"}],
            "questions": [{"text": "What is this?"}],
        }
        result = handle_submit_mapping(state, mapping)
        assert result["stored"] is True
        assert result["revenue_stream_count"] == 2
        assert result["cost_item_count"] == 1
        assert result["capex_item_count"] == 0
        assert result["unmapped_count"] == 1
        assert result["question_count"] == 1
        assert state["mapping"] == mapping

    def test_overwrites_previous(self):
        state: dict = {"mapping": {"old": True}}
        new_mapping = {
            "metadata": {},
            "revenue_streams": [],
            "cost_items": [],
            "capex_items": [],
            "working_capital": {},
            "funding": {},
            "unmapped_items": [],
            "questions": [],
        }
        handle_submit_mapping(state, new_mapping)
        assert state["mapping"] == new_mapping
