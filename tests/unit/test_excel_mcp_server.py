"""Tests for the MCP tool-server factory for agentic Excel import.

Verifies that create_excel_mcp_server produces the correct number of tools,
correct names, and that handlers delegate to the underlying excel_tools
functions.  No Agent SDK imports required.
"""

from __future__ import annotations

from unittest.mock import patch

from apps.api.app.services.agent.excel_mcp_server import (
    ASK_USER_SENTINEL,
    EXPECTED_TOOL_COUNT,
    create_excel_mcp_server,
)

# ---------------------------------------------------------------------------
# Fixtures (reused from test_excel_tools.py — kept local to avoid coupling)
# ---------------------------------------------------------------------------

MOCK_SHEETS: dict[str, dict] = {
    "P&L": {
        "name": "P&L",
        "headers": ["Account", "Q1", "Q2", "Q3"],
        "sample_rows": [
            ["Revenue", 100_000, 120_000, 140_000],
            ["COGS", -40_000, -48_000, -56_000],
            ["Gross Profit", 60_000, 72_000, 84_000],
        ],
        "row_count": 45,
        "col_count": 4,
        "formula_patterns": [
            {"pattern": "=Revenue-COGS", "count": 3, "description": "Gross profit calc"},
        ],
        "referenced_sheets": ["Assumptions"],
    },
    "Assumptions": {
        "name": "Assumptions",
        "headers": ["Parameter", "Value"],
        "sample_rows": [
            ["Growth Rate", 0.15],
            ["Tax Rate", 0.21],
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
]


def _make_server() -> tuple[dict, dict]:
    """Create a fresh server spec and session state."""
    state: dict = {}
    spec = create_excel_mcp_server(MOCK_SHEETS, MOCK_TEMPLATES, state)
    return spec, state


def _get_handler(spec: dict, name: str):
    """Find a tool handler by name."""
    for defn in spec["tool_definitions"]:
        if defn["name"] == name:
            return defn["handler"]
    raise KeyError(f"Tool '{name}' not found in spec")


# ===================================================================
# Factory structure
# ===================================================================


class TestFactoryStructure:
    """create_excel_mcp_server returns a well-formed tool registry."""

    def test_returns_expected_tool_count(self):
        spec, _ = _make_server()
        assert spec["tool_count"] == EXPECTED_TOOL_COUNT

    def test_tool_definitions_length_matches_count(self):
        spec, _ = _make_server()
        assert len(spec["tool_definitions"]) == spec["tool_count"]

    def test_all_tool_names(self):
        spec, _ = _make_server()
        names = {d["name"] for d in spec["tool_definitions"]}
        expected = {
            "read_sheet_data",
            "read_cell_range",
            "get_formula_patterns",
            "get_sheet_dependencies",
            "compare_sheets",
            "search_template_catalog",
            "validate_mapping",
            "submit_classification",
            "submit_mapping",
            "ask_user_question",
        }
        assert names == expected

    def test_every_tool_has_required_keys(self):
        spec, _ = _make_server()
        for defn in spec["tool_definitions"]:
            assert "name" in defn, f"Tool missing 'name': {defn}"
            assert "description" in defn, f"Tool {defn['name']} missing 'description'"
            assert "handler" in defn, f"Tool {defn['name']} missing 'handler'"
            assert "input_schema" in defn, f"Tool {defn['name']} missing 'input_schema'"

    def test_every_tool_has_callable_handler(self):
        spec, _ = _make_server()
        for defn in spec["tool_definitions"]:
            assert callable(defn["handler"]), f"Tool {defn['name']} handler is not callable"

    def test_descriptions_are_non_empty_strings(self):
        spec, _ = _make_server()
        for defn in spec["tool_definitions"]:
            assert isinstance(defn["description"], str)
            assert len(defn["description"]) > 10, (
                f"Tool {defn['name']} description too short: {defn['description']!r}"
            )

    def test_input_schemas_are_objects(self):
        spec, _ = _make_server()
        for defn in spec["tool_definitions"]:
            schema = defn["input_schema"]
            assert isinstance(schema, dict)
            assert schema.get("type") == "object", (
                f"Tool {defn['name']} schema type should be 'object'"
            )


# ===================================================================
# Read tool handlers — delegate to excel_tools
# ===================================================================


class TestReadToolHandlers:
    """Read tools delegate correctly to excel_tools handlers."""

    def test_read_sheet_data_returns_headers(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "read_sheet_data")
        result = handler({"sheet_name": "P&L"})
        assert result["headers"] == ["Account", "Q1", "Q2", "Q3"]
        assert result["row_count"] == 45

    def test_read_sheet_data_missing_sheet(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "read_sheet_data")
        result = handler({"sheet_name": "NoSuchSheet"})
        assert "error" in result

    def test_read_cell_range_returns_slice(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "read_cell_range")
        result = handler({"sheet_name": "P&L", "start_row": 0, "end_row": 1, "start_col": 0, "end_col": 2})
        assert result["data"] == [["Revenue", 100_000]]

    def test_get_formula_patterns_returns_formulas(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "get_formula_patterns")
        result = handler({"sheet_name": "P&L"})
        assert len(result["formula_patterns"]) == 1
        assert result["referenced_sheets"] == ["Assumptions"]

    def test_get_sheet_dependencies_returns_adjacency(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "get_sheet_dependencies")
        result = handler({})
        assert "P&L" in result["dependencies"]
        assert result["dependencies"]["P&L"] == ["Assumptions"]

    def test_compare_sheets_returns_comparison(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "compare_sheets")
        result = handler({"sheet_a": "P&L", "sheet_b": "Assumptions"})
        assert result["sheet_a"]["name"] == "P&L"
        assert result["sheet_b"]["name"] == "Assumptions"
        assert "shared_headers" in result


# ===================================================================
# Action tool handlers
# ===================================================================


class TestActionToolHandlers:
    """Action tools delegate correctly to excel_tools handlers."""

    def test_search_template_catalog_filters(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "search_template_catalog")
        result = handler({"industry": "software"})
        assert len(result["matches"]) == 1
        assert result["matches"][0]["template_id"] == "tpl_saas_001"

    def test_search_template_catalog_no_match(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "search_template_catalog")
        result = handler({"industry": "healthcare"})
        assert len(result["matches"]) == 0

    def test_validate_mapping_valid(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "validate_mapping")
        mapping = {
            "mapping": {
                "metadata": {
                    "entity_name": "Acme",
                    "currency": "USD",
                    "country_iso": "US",
                    "start_date": "2026-01-01",
                    "horizon_months": 36,
                },
                "revenue_streams": [{"label": "Sales"}],
                "cost_items": [{"label": "COGS"}],
                "capex_items": [],
                "working_capital": {},
                "funding": {},
                "unmapped_items": [],
                "questions": [],
            }
        }
        result = handler(mapping)
        assert result["valid"] is True

    def test_validate_mapping_invalid(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "validate_mapping")
        result = handler({"mapping": {"metadata": {}}})
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_submit_classification_stores_in_state(self):
        spec, state = _make_server()
        handler = _get_handler(spec, "submit_classification")
        classification = {
            "classification": {
                "sheets": [{"name": "P&L", "type": "income_statement"}],
                "model_summary": {"entity_name": "Acme"},
            }
        }
        result = handler(classification)
        assert result["stored"] is True
        assert "classification" in state
        assert state["classification"]["sheets"][0]["name"] == "P&L"

    def test_submit_mapping_stores_in_state(self):
        spec, state = _make_server()
        handler = _get_handler(spec, "submit_mapping")
        mapping = {
            "mapping": {
                "metadata": {"entity_name": "Acme"},
                "revenue_streams": [{"label": "A"}],
                "cost_items": [],
                "capex_items": [],
                "working_capital": {},
                "funding": {},
                "unmapped_items": [],
                "questions": [],
            }
        }
        result = handler(mapping)
        assert result["stored"] is True
        assert result["revenue_stream_count"] == 1
        assert "mapping" in state


# ===================================================================
# ask_user_question — special sentinel behavior
# ===================================================================


class TestAskUserQuestion:
    """ask_user_question sets state and returns sentinel."""

    def test_returns_sentinel(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "ask_user_question")
        result = handler({"question": "What currency?", "options": ["USD", "EUR"]})
        assert result == ASK_USER_SENTINEL

    def test_sets_pending_question_in_state(self):
        spec, state = _make_server()
        handler = _get_handler(spec, "ask_user_question")
        handler({"question": "What currency?", "options": ["USD", "EUR"]})
        assert "pending_question" in state
        assert state["pending_question"]["question"] == "What currency?"
        assert state["pending_question"]["options"] == ["USD", "EUR"]

    def test_options_default_to_empty_list(self):
        spec, state = _make_server()
        handler = _get_handler(spec, "ask_user_question")
        handler({"question": "Is this correct?"})
        assert state["pending_question"]["options"] == []

    def test_overwrites_previous_pending_question(self):
        spec, state = _make_server()
        handler = _get_handler(spec, "ask_user_question")
        handler({"question": "First?"})
        handler({"question": "Second?", "options": ["Yes", "No"]})
        assert state["pending_question"]["question"] == "Second?"

    def test_sentinel_is_string(self):
        assert isinstance(ASK_USER_SENTINEL, str)
        assert len(ASK_USER_SENTINEL) > 0


# ===================================================================
# Handler delegation (mock-based)
# ===================================================================


class TestHandlerDelegation:
    """Verify that factory handlers delegate to the correct excel_tools functions."""

    def test_read_sheet_data_calls_handler(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "read_sheet_data")
        with patch(
            "apps.api.app.services.agent.excel_mcp_server.handle_read_sheet_data"
        ) as mock:
            mock.return_value = {"mocked": True}
            result = handler({"sheet_name": "P&L"})
            mock.assert_called_once_with(MOCK_SHEETS, {"sheet_name": "P&L"})
            assert result == {"mocked": True}

    def test_read_cell_range_calls_handler(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "read_cell_range")
        with patch(
            "apps.api.app.services.agent.excel_mcp_server.handle_read_cell_range"
        ) as mock:
            mock.return_value = {"mocked": True}
            args = {"sheet_name": "P&L", "start_row": 0, "end_row": 1}
            result = handler(args)
            mock.assert_called_once_with(MOCK_SHEETS, args)
            assert result == {"mocked": True}

    def test_get_formula_patterns_calls_handler(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "get_formula_patterns")
        with patch(
            "apps.api.app.services.agent.excel_mcp_server.handle_get_formula_patterns"
        ) as mock:
            mock.return_value = {"mocked": True}
            result = handler({"sheet_name": "P&L"})
            mock.assert_called_once_with(MOCK_SHEETS, {"sheet_name": "P&L"})
            assert result == {"mocked": True}

    def test_get_sheet_dependencies_calls_handler(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "get_sheet_dependencies")
        with patch(
            "apps.api.app.services.agent.excel_mcp_server.handle_get_sheet_dependencies"
        ) as mock:
            mock.return_value = {"mocked": True}
            result = handler({})
            mock.assert_called_once_with(MOCK_SHEETS, {})
            assert result == {"mocked": True}

    def test_compare_sheets_calls_handler(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "compare_sheets")
        with patch(
            "apps.api.app.services.agent.excel_mcp_server.handle_compare_sheets"
        ) as mock:
            mock.return_value = {"mocked": True}
            args = {"sheet_a": "P&L", "sheet_b": "Assumptions"}
            result = handler(args)
            mock.assert_called_once_with(MOCK_SHEETS, args)
            assert result == {"mocked": True}

    def test_search_template_catalog_calls_handler(self):
        spec, _ = _make_server()
        handler = _get_handler(spec, "search_template_catalog")
        with patch(
            "apps.api.app.services.agent.excel_mcp_server.handle_search_template_catalog"
        ) as mock:
            mock.return_value = {"mocked": True}
            args = {"industry": "software"}
            result = handler(args)
            mock.assert_called_once_with(MOCK_TEMPLATES, args)
            assert result == {"mocked": True}
