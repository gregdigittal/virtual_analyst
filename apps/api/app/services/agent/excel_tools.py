"""MCP read and action tool handlers for agentic Excel workbook analysis.

Pure functions — no async, no DB, no external imports beyond the stdlib.
Each handler receives the relevant data (sheets dict, templates list, or
mutable state dict) plus an args dict, and returns a plain dict result.

These handlers are called by the MCP tool server (Task 4) which wraps
them in Agent SDK tool decorators.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Read Tools (Task 2)
# ---------------------------------------------------------------------------


def handle_read_sheet_data(
    sheets: dict[str, dict[str, Any]],
    args: dict[str, Any],
) -> dict[str, Any]:
    """Return headers, sample_rows (limited by max_rows), row_count, col_count.

    Args:
        sheets: parsed workbook — sheet_name -> sheet_data dict.
        args: {"sheet_name": str, "max_rows"?: int}

    Returns:
        Dict with sheet metadata, or {"error": ...} if sheet not found.
    """
    sheet_name: str = args["sheet_name"]
    if sheet_name not in sheets:
        return {"error": f"Sheet '{sheet_name}' not found. Available sheets: {list(sheets.keys())}"}

    sheet = sheets[sheet_name]
    max_rows: int = args.get("max_rows", len(sheet["sample_rows"]))
    return {
        "headers": sheet["headers"],
        "sample_rows": sheet["sample_rows"][:max_rows],
        "row_count": sheet["row_count"],
        "col_count": sheet["col_count"],
    }


def handle_read_cell_range(
    sheets: dict[str, dict[str, Any]],
    args: dict[str, Any],
) -> dict[str, Any]:
    """Return a rectangular slice of sample_rows.

    Args:
        sheets: parsed workbook.
        args: {"sheet_name": str, "start_row"?: int, "end_row"?: int,
               "start_col"?: int, "end_col"?: int}

    Returns:
        Dict with ``data`` (list of lists), or {"error": ...}.
    """
    sheet_name: str = args["sheet_name"]
    if sheet_name not in sheets:
        return {"error": f"Sheet '{sheet_name}' not found. Available sheets: {list(sheets.keys())}"}

    rows = sheets[sheet_name]["sample_rows"]
    start_row: int = args.get("start_row", 0)
    end_row: int = args.get("end_row", len(rows))
    start_col: int = args.get("start_col", 0)
    end_col: int = args.get("end_col", None)  # type: ignore[assignment]

    sliced = [row[start_col:end_col] for row in rows[start_row:end_row]]
    return {"data": sliced}


def handle_get_formula_patterns(
    sheets: dict[str, dict[str, Any]],
    args: dict[str, Any],
) -> dict[str, Any]:
    """Return formula_patterns and referenced_sheets for a single sheet.

    Args:
        sheets: parsed workbook.
        args: {"sheet_name": str}

    Returns:
        Dict with formula_patterns and referenced_sheets, or {"error": ...}.
    """
    sheet_name: str = args["sheet_name"]
    if sheet_name not in sheets:
        return {"error": f"Sheet '{sheet_name}' not found. Available sheets: {list(sheets.keys())}"}

    sheet = sheets[sheet_name]
    return {
        "formula_patterns": sheet["formula_patterns"],
        "referenced_sheets": sheet["referenced_sheets"],
    }


def handle_get_sheet_dependencies(
    sheets: dict[str, dict[str, Any]],
    _args: dict[str, Any],
) -> dict[str, Any]:
    """Return an adjacency dict of all sheets' referenced_sheets.

    Args:
        sheets: parsed workbook.
        _args: ignored (no arguments needed).

    Returns:
        {"dependencies": {sheet_name: [referenced_sheet, ...], ...}}
    """
    dependencies: dict[str, list[str]] = {
        name: sheet["referenced_sheets"] for name, sheet in sheets.items()
    }
    return {"dependencies": dependencies}


def handle_compare_sheets(
    sheets: dict[str, dict[str, Any]],
    args: dict[str, Any],
) -> dict[str, Any]:
    """Compare two sheets: row_count, col_count, shared/unique headers.

    Args:
        sheets: parsed workbook.
        args: {"sheet_a": str, "sheet_b": str}

    Returns:
        Structural comparison dict, or {"error": ...} if either sheet missing.
    """
    name_a: str = args["sheet_a"]
    name_b: str = args["sheet_b"]

    if name_a not in sheets:
        return {"error": f"Sheet '{name_a}' not found. Available sheets: {list(sheets.keys())}"}
    if name_b not in sheets:
        return {"error": f"Sheet '{name_b}' not found. Available sheets: {list(sheets.keys())}"}

    a = sheets[name_a]
    b = sheets[name_b]

    headers_a = set(a["headers"])
    headers_b = set(b["headers"])

    return {
        "sheet_a": {"name": name_a, "row_count": a["row_count"], "col_count": a["col_count"]},
        "sheet_b": {"name": name_b, "row_count": b["row_count"], "col_count": b["col_count"]},
        "shared_headers": sorted(headers_a & headers_b),
        "only_in_a": sorted(headers_a - headers_b),
        "only_in_b": sorted(headers_b - headers_a),
    }


# ---------------------------------------------------------------------------
# Action Tools (Task 3)
# ---------------------------------------------------------------------------

_REQUIRED_MAPPING_KEYS = frozenset({
    "metadata",
    "revenue_streams",
    "cost_items",
    "capex_items",
    "working_capital",
    "funding",
    "unmapped_items",
    "questions",
})

_REQUIRED_METADATA_FIELDS = frozenset({
    "entity_name",
    "currency",
    "country_iso",
    "start_date",
    "horizon_months",
})

# Sections whose item count contributes to coverage calculation.
_COVERAGE_SECTIONS = ("revenue_streams", "cost_items", "capex_items")


def handle_search_template_catalog(
    templates: list[dict[str, Any]],
    args: dict[str, Any],
) -> dict[str, Any]:
    """Filter template catalog by industry and/or model_type.

    Args:
        templates: list of template dicts (template_id, label, industry, model_type, accounts).
        args: {"industry"?: str, "model_type"?: str}

    Returns:
        {"matches": [template_dict, ...]}
    """
    industry: str | None = args.get("industry")
    model_type: str | None = args.get("model_type")

    matches: list[dict[str, Any]] = []
    for tpl in templates:
        if industry and tpl.get("industry") != industry:
            continue
        if model_type and tpl.get("model_type") != model_type:
            continue
        matches.append({
            "template_id": tpl["template_id"],
            "label": tpl["label"],
            "industry": tpl["industry"],
            "model_type": tpl.get("model_type"),
            "accounts": tpl.get("accounts", []),
        })

    return {"matches": matches}


def handle_validate_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    """Validate a mapping dict for required keys and metadata fields.

    Args:
        mapping: the candidate mapping dict to validate.

    Returns:
        {"valid": bool, "errors": list[str], "warnings": list[str], "coverage_pct": float}
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Check required top-level keys.
    present_keys = set(mapping.keys())
    for key in _REQUIRED_MAPPING_KEYS:
        if key not in present_keys:
            errors.append(f"Missing required key: '{key}'")

    # Check required metadata fields (only if metadata exists).
    metadata = mapping.get("metadata")
    if metadata is not None and isinstance(metadata, dict):
        for field in _REQUIRED_METADATA_FIELDS:
            if field not in metadata:
                errors.append(f"Missing required metadata field: '{field}'")
    elif metadata is None and "metadata" not in present_keys:
        pass  # Already caught above as missing required key.

    # Warnings for empty financial sections.
    for section in _COVERAGE_SECTIONS:
        items = mapping.get(section)
        if isinstance(items, list) and len(items) == 0:
            warnings.append(f"Section '{section}' is empty — no items mapped.")

    # Coverage: proportion of non-empty coverage sections.
    filled = 0
    for section in _COVERAGE_SECTIONS:
        items = mapping.get(section)
        if isinstance(items, list) and len(items) > 0:
            filled += 1
    total_sections = len(_COVERAGE_SECTIONS)
    coverage_pct = round((filled / total_sections) * 100, 1) if total_sections else 0.0

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "coverage_pct": coverage_pct,
    }


def handle_submit_classification(
    state: dict[str, Any],
    classification: dict[str, Any],
) -> dict[str, Any]:
    """Store classification in mutable state dict.

    Args:
        state: mutable dict shared across the agent session.
        classification: the classification payload to store.

    Returns:
        {"stored": True}
    """
    state["classification"] = classification
    return {"stored": True}


def handle_submit_mapping(
    state: dict[str, Any],
    mapping: dict[str, Any],
) -> dict[str, Any]:
    """Store mapping in mutable state dict.

    Args:
        state: mutable dict shared across the agent session.
        mapping: the mapping payload to store.

    Returns:
        {"stored": True, "revenue_stream_count": int, "cost_item_count": int,
         "capex_item_count": int, "unmapped_count": int, "question_count": int}
    """
    state["mapping"] = mapping
    return {
        "stored": True,
        "revenue_stream_count": len(mapping.get("revenue_streams", [])),
        "cost_item_count": len(mapping.get("cost_items", [])),
        "capex_item_count": len(mapping.get("capex_items", [])),
        "unmapped_count": len(mapping.get("unmapped_items", [])),
        "question_count": len(mapping.get("questions", [])),
    }
