"""MCP tool-server factory for the agentic Excel import agent.

Produces a dict of tool definitions that the session manager (Task 6)
can wire into ``create_sdk_mcp_server``.  Keeping the factory free of
Agent SDK imports makes it fully testable without the optional
``claude-agent-sdk`` package.

Usage (in session manager)::

    from apps.api.app.services.agent.excel_mcp_server import create_excel_mcp_server

    server_spec = create_excel_mcp_server(sheets, templates, state)
    for defn in server_spec["tool_definitions"]:
        mcp.tool(name=defn["name"], description=defn["description"])(defn["handler"])
"""

from __future__ import annotations

import json
from typing import Any, Callable

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

# Sentinel returned by ask_user_question so the session manager knows
# to pause the agent loop and wait for user input.
ASK_USER_SENTINEL = "__ASK_USER_QUESTION__"

EXPECTED_TOOL_COUNT = 10


def create_excel_mcp_server(
    sheets: dict[str, Any],
    templates: list[dict[str, Any]],
    state: dict[str, Any],
) -> dict[str, Any]:
    """Build tool definitions for the Excel import agent.

    Parameters
    ----------
    sheets:
        Parsed workbook data — ``{sheet_name: sheet_data_dict}``.
    templates:
        Template catalog entries (list of dicts).
    state:
        Mutable session state dict shared across the agent turn loop.
        Used by ``submit_classification``, ``submit_mapping``, and
        ``ask_user_question`` to persist results.

    Returns
    -------
    dict with keys:
        ``tool_definitions`` — list of tool definition dicts, each with
            ``name``, ``description``, ``input_schema``, ``handler``.
        ``tool_count`` — integer count of tools (should be 10).
    """

    # ------------------------------------------------------------------
    # Handlers — thin closures that adapt the generic (sheets, args)
    # signatures of excel_tools to single-arg callables suitable for
    # Agent SDK @tool wiring.
    # ------------------------------------------------------------------

    def _read_sheet_data(args: dict[str, Any]) -> dict[str, Any]:
        return handle_read_sheet_data(sheets, args)

    def _read_cell_range(args: dict[str, Any]) -> dict[str, Any]:
        return handle_read_cell_range(sheets, args)

    def _get_formula_patterns(args: dict[str, Any]) -> dict[str, Any]:
        return handle_get_formula_patterns(sheets, args)

    def _get_sheet_dependencies(args: dict[str, Any]) -> dict[str, Any]:
        return handle_get_sheet_dependencies(sheets, args)

    def _compare_sheets(args: dict[str, Any]) -> dict[str, Any]:
        return handle_compare_sheets(sheets, args)

    def _search_template_catalog(args: dict[str, Any]) -> dict[str, Any]:
        return handle_search_template_catalog(templates, args)

    def _validate_mapping(args: dict[str, Any]) -> dict[str, Any]:
        return handle_validate_mapping(args.get("mapping", args))

    def _submit_classification(args: dict[str, Any]) -> dict[str, Any]:
        return handle_submit_classification(state, args.get("classification", args))

    def _submit_mapping(args: dict[str, Any]) -> dict[str, Any]:
        return handle_submit_mapping(state, args.get("mapping", args))

    def _ask_user_question(args: dict[str, Any]) -> str:
        """Store the question in state and return the sentinel value."""
        state["pending_question"] = {
            "question": args["question"],
            "options": args.get("options", []),
        }
        return ASK_USER_SENTINEL

    # ------------------------------------------------------------------
    # Tool definitions
    # ------------------------------------------------------------------

    tool_definitions: list[dict[str, Any]] = [
        {
            "name": "read_sheet_data",
            "description": (
                "Read a single sheet's headers, sample rows (capped by max_rows), "
                "row_count, and col_count."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "sheet_name": {"type": "string", "description": "Name of the sheet to read."},
                    "max_rows": {
                        "type": "integer",
                        "description": "Maximum sample rows to return (default: all).",
                    },
                },
                "required": ["sheet_name"],
            },
            "handler": _read_sheet_data,
        },
        {
            "name": "read_cell_range",
            "description": (
                "Read a rectangular sub-range of a sheet's sample rows. "
                "Specify start_row/end_row and start_col/end_col (0-indexed)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "sheet_name": {"type": "string", "description": "Name of the sheet."},
                    "start_row": {"type": "integer", "description": "First row index (inclusive)."},
                    "end_row": {"type": "integer", "description": "Last row index (exclusive)."},
                    "start_col": {
                        "type": "integer",
                        "description": "First column index (inclusive).",
                    },
                    "end_col": {
                        "type": "integer",
                        "description": "Last column index (exclusive).",
                    },
                },
                "required": ["sheet_name"],
            },
            "handler": _read_cell_range,
        },
        {
            "name": "get_formula_patterns",
            "description": (
                "Return deduplicated formula patterns and referenced sheets for a "
                "given sheet."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "sheet_name": {"type": "string", "description": "Name of the sheet."},
                },
                "required": ["sheet_name"],
            },
            "handler": _get_formula_patterns,
        },
        {
            "name": "get_sheet_dependencies",
            "description": (
                "Return an adjacency dict showing which sheets reference which "
                "other sheets (cross-sheet formula dependencies)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
            },
            "handler": _get_sheet_dependencies,
        },
        {
            "name": "compare_sheets",
            "description": (
                "Structurally compare two sheets: row/col counts, shared headers, "
                "and headers unique to each."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "sheet_a": {"type": "string", "description": "First sheet name."},
                    "sheet_b": {"type": "string", "description": "Second sheet name."},
                },
                "required": ["sheet_a", "sheet_b"],
            },
            "handler": _compare_sheets,
        },
        {
            "name": "search_template_catalog",
            "description": (
                "Search the built-in template catalog by industry and/or model_type. "
                "Returns matching template summaries with account lists."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "industry": {
                        "type": "string",
                        "description": "Filter by industry (e.g. 'software', 'manufacturing').",
                    },
                    "model_type": {
                        "type": "string",
                        "description": "Filter by model type (e.g. 'saas', 'ecommerce').",
                    },
                },
            },
            "handler": _search_template_catalog,
        },
        {
            "name": "validate_mapping",
            "description": (
                "Validate a candidate mapping dict for required keys, metadata "
                "fields, and coverage. Returns errors, warnings, and coverage_pct."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "mapping": {
                        "type": "object",
                        "description": "The mapping dict to validate.",
                    },
                },
                "required": ["mapping"],
            },
            "handler": _validate_mapping,
        },
        {
            "name": "submit_classification",
            "description": (
                "Submit your sheet classification. Include sheets list (name, type, "
                "confidence, is_financial_core) and model_summary."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "classification": {
                        "type": "object",
                        "description": (
                            "Classification payload with 'sheets' and 'model_summary'."
                        ),
                    },
                },
                "required": ["classification"],
            },
            "handler": _submit_classification,
        },
        {
            "name": "submit_mapping",
            "description": (
                "Submit the final mapping with metadata, revenue_streams, "
                "cost_items, capex_items, working_capital, funding, "
                "unmapped_items, and questions."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "mapping": {
                        "type": "object",
                        "description": "The complete mapping dict.",
                    },
                },
                "required": ["mapping"],
            },
            "handler": _submit_mapping,
        },
        {
            "name": "ask_user_question",
            "description": (
                "Ask the user a clarification question. Provide a clear question "
                "and 2-4 option strings. The agent will pause until the user "
                "answers."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask the user.",
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "2-4 answer options for the user to choose from.",
                    },
                },
                "required": ["question"],
            },
            "handler": _ask_user_question,
        },
    ]

    assert len(tool_definitions) == EXPECTED_TOOL_COUNT, (
        f"Expected {EXPECTED_TOOL_COUNT} tools, got {len(tool_definitions)}"
    )

    return {
        "tool_definitions": tool_definitions,
        "tool_count": len(tool_definitions),
    }
