"""
Excel model parser — extracts structure, formulas, values, and dependency graph
from uploaded .xlsx files using openpyxl.

Returns a structured dict suitable for LLM analysis.
"""

from __future__ import annotations

import dataclasses
import re
import time
from io import BytesIO
from typing import Any

import structlog

MAX_SHEETS = 30
MAX_COLS = 500
MAX_ROWS = 10_000
PARSE_TIMEOUT_SEC = 60
SAMPLE_ROWS = 8
MAX_FORMULA_PATTERNS = 20

# Cross-sheet: require sheet name followed by ! and cell ref to avoid FALSE!, TRUE!, etc.
CROSS_SHEET_PATTERN = re.compile(r"(?:'([^'\[\]!]+)'|([A-Za-z_]\w*))![A-Z]+\d+")
# External ref: [1] or [filename.xlsx]
EXTERNAL_REF_PATTERN = re.compile(r"\[[^\]]+\]")


@dataclasses.dataclass
class SheetInfo:
    name: str
    dimensions: str
    row_count: int
    col_count: int
    formula_count: int
    value_count: int
    empty_count: int
    merged_cell_count: int
    cross_sheet_ref_count: int
    external_ref_count: int
    headers: list[str]
    sample_rows: list[list[str | float | None]]
    formula_patterns: list[str]
    referenced_sheets: list[str]


@dataclasses.dataclass
class ExcelParseResult:
    filename: str
    file_size_bytes: int
    sheet_count: int
    sheets: list[SheetInfo]
    total_formulas: int
    total_cross_refs: int
    total_external_refs: int
    has_external_refs: bool
    named_ranges: list[dict[str, str]]
    dependency_graph: dict[str, list[str]]


def _check_timeout(start: float) -> None:
    if time.monotonic() - start > PARSE_TIMEOUT_SEC:
        raise TimeoutError(f"Excel parse exceeded {PARSE_TIMEOUT_SEC}s")


def _cell_value(cell: Any) -> str | float | None:
    v = getattr(cell, "value", None)
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if isinstance(v, float) else int(v)
    return str(v).strip() or None


def _is_formula(cell: Any) -> bool:
    return getattr(cell, "data_type", None) == "f" or (
        isinstance(getattr(cell, "value", None), str) and str(cell.value).strip().startswith("=")
    )


def _formula_text(cell: Any) -> str | None:
    v = getattr(cell, "value", None)
    if isinstance(v, str) and v.strip().startswith("="):
        return v.strip()
    return None


def _count_refs(formula: str) -> tuple[int, int]:
    cross = len(CROSS_SHEET_PATTERN.findall(formula))
    external = len(EXTERNAL_REF_PATTERN.findall(formula))
    return cross, external


def _sheet_refs(formula: str) -> list[str]:
    refs: list[str] = []
    for m in CROSS_SHEET_PATTERN.finditer(formula):
        g = m.group(1) or m.group(2)
        if g and g not in refs:
            refs.append(g)
    return refs


def _extract_named_ranges(wb: Any) -> list[dict[str, str]]:
    """Extract defined names from workbook (call before closing the workbook)."""
    out: list[dict[str, str]] = []
    try:
        dn = getattr(wb, "defined_names", None)
        if dn and hasattr(dn, "items"):
            for name, defn in dn.items():
                attr = getattr(defn, "attr_text", None) or getattr(defn, "value", str(defn))
                if name and attr:
                    out.append({"name": str(name), "sheet": "", "range": str(attr)})
    except Exception as exc:
        structlog.get_logger().warning("named_ranges_extraction_failed", error=str(exc))
    return out


def _first_non_empty_row(ws: Any, max_col: int, max_row: int) -> list[str | float | None]:
    for r in range(1, min(max_row, MAX_ROWS) + 1):
        row_vals = []
        for c in range(1, min(max_col, MAX_COLS) + 1):
            cell = ws.cell(row=r, column=c)
            row_vals.append(_cell_value(cell))
        if any(v is not None and str(v).strip() != "" for v in row_vals):
            return row_vals
    return []


def parse_workbook(file_bytes: bytes, filename: str = "upload.xlsx", max_sheets: int = MAX_SHEETS) -> ExcelParseResult:
    """Parse .xlsx and return structure, formulas, and dependency graph. Raises on timeout or invalid file."""
    start = time.monotonic()
    try:
        wb_formulas = __import__("openpyxl").load_workbook(BytesIO(file_bytes), data_only=False, read_only=True)
    except Exception as e:
        raise ValueError(f"Invalid or corrupt Excel file: {e}") from e

    try:
        try:
            wb_values = __import__("openpyxl").load_workbook(BytesIO(file_bytes), data_only=True, read_only=True)
        except Exception:  # noqa: BLE001 — openpyxl raises varied exceptions on corrupt/protected files
            wb_values = None

        sheet_names = wb_formulas.sheetnames[:max_sheets]
        sheets: list[SheetInfo] = []
        total_formulas = 0
        total_cross_refs = 0
        total_external_refs = 0
        dependency_graph: dict[str, list[str]] = {}

        for sh_name in sheet_names:
            _check_timeout(start)
            ws_f = wb_formulas[sh_name]
            ws_v = wb_values[sh_name] if wb_values else ws_f
            max_row = min(ws_f.max_row or 0, MAX_ROWS)
            max_col = min(ws_f.max_column or 0, MAX_COLS)
            row_count = max_row
            col_count = max_col
            dimensions = f"{row_count}x{col_count}"

            formula_count = 0
            value_count = 0
            empty_count = 0
            cross_sheet_ref_count = 0
            external_ref_count = 0
            formula_patterns_set: set[str] = set()
            referenced_sheets: list[str] = []
            try:
                merged_cell_count = len(ws_f.merged_cells.ranges) if hasattr(ws_f.merged_cells, "ranges") else 0
            except (AttributeError, TypeError):
                merged_cell_count = 0  # read_only mode does not populate merged_cells.ranges

            for row in ws_f.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
                _check_timeout(start)
                for cell in row:
                    if _is_formula(cell):
                        formula_count += 1
                        ft = _formula_text(cell)
                        if ft and len(formula_patterns_set) < MAX_FORMULA_PATTERNS:
                            formula_patterns_set.add(ft[:200])
                        if ft:
                            c, e = _count_refs(ft)
                            cross_sheet_ref_count += c
                            external_ref_count += e
                            for ref in _sheet_refs(ft):
                                if ref not in referenced_sheets:
                                    referenced_sheets.append(ref)
                    elif _cell_value(cell) is not None and str(_cell_value(cell)).strip() != "":
                        value_count += 1
                    else:
                        empty_count += 1

            total_formulas += formula_count
            total_cross_refs += cross_sheet_ref_count
            total_external_refs += external_ref_count
            dependency_graph[sh_name] = referenced_sheets

            headers = _first_non_empty_row(ws_v, max_col, max_row)
            sample_rows = []
            data_start = 2 if headers else 1
            for r in range(data_start, min(data_start + SAMPLE_ROWS, max_row + 1)):
                _check_timeout(start)
                row_vals = []
                for c in range(1, max_col + 1):
                    cell = ws_v.cell(row=r, column=c)
                    row_vals.append(_cell_value(cell))
                sample_rows.append(row_vals)

            sheets.append(
                SheetInfo(
                    name=sh_name,
                    dimensions=dimensions,
                    row_count=row_count,
                    col_count=col_count,
                    formula_count=formula_count,
                    value_count=value_count,
                    empty_count=empty_count,
                    merged_cell_count=merged_cell_count,
                    cross_sheet_ref_count=cross_sheet_ref_count,
                    external_ref_count=external_ref_count,
                    headers=[str(h) if h is not None else "" for h in headers],
                    sample_rows=sample_rows,
                    formula_patterns=sorted(formula_patterns_set)[:MAX_FORMULA_PATTERNS],
                    referenced_sheets=referenced_sheets,
                )
            )

        named_ranges = _extract_named_ranges(wb_formulas)
    finally:
        wb_formulas.close()
        if wb_values is not None:
            wb_values.close()

    return ExcelParseResult(
        filename=filename,
        file_size_bytes=len(file_bytes),
        sheet_count=len(sheets),
        sheets=sheets,
        total_formulas=total_formulas,
        total_cross_refs=total_cross_refs,
        total_external_refs=total_external_refs,
        has_external_refs=total_external_refs > 0,
        named_ranges=named_ranges,
        dependency_graph=dependency_graph,
    )


def classify_sheets(parse_result: ExcelParseResult) -> dict[str, str]:
    """Heuristic pre-classification before LLM. Returns {sheet_name: classification}."""
    result: dict[str, str] = {}
    for sheet in parse_result.sheets:
        total_cells = sheet.formula_count + sheet.value_count + sheet.empty_count or 1
        formula_pct = (sheet.formula_count / total_cells * 100) if total_cells else 0
        non_empty = sheet.value_count + sheet.formula_count
        if non_empty < 5:
            result[sheet.name] = "empty"
            continue
        text_like = sum(1 for h in sheet.headers if h and not str(h).replace(".", "").replace("-", "").isdigit())
        header_text_pct = (text_like / len(sheet.headers) * 100) if sheet.headers else 0
        month_headers = sum(1 for h in sheet.headers if re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|q1|q2|q3|q4|\d{4})", str(h).lower()))
        if formula_pct > 50 and (month_headers >= 2 or len(sheet.headers) >= 6):
            result[sheet.name] = "financial"
            continue
        if header_text_pct > 80 or (sheet.merged_cell_count > 5 and formula_pct < 20):
            result[sheet.name] = "documentation"
            continue
        if any(re.search(r"(task|phase|milestone|start|end|date)", str(h).lower()) for h in sheet.headers[:5]):
            result[sheet.name] = "project_management"
            continue
        if sheet.formula_count > 10 and sheet.cross_sheet_ref_count > 0:
            result[sheet.name] = "data_reference"
            continue
        result[sheet.name] = "unknown"
    return result


def extract_assumption_candidates(sheet: SheetInfo, values_sheet: SheetInfo | None = None) -> list[dict[str, Any]]:
    """For financial sheets: rows that look like assumption inputs (label in A, value in B)."""
    candidates: list[dict[str, Any]] = []
    s = values_sheet or sheet
    if not s.sample_rows and not s.headers:
        return candidates
    for row_idx, row in enumerate(s.sample_rows):
        if len(row) < 2:
            continue
        label = row[0]
        val = row[1] if len(row) > 1 else None
        if label is None or (isinstance(label, str) and not label.strip()):
            continue
        label_str = str(label).strip()
        if val is not None and isinstance(val, (int, float)) and not isinstance(val, bool):
            data_type_guess = "number"
        elif val is not None and isinstance(val, str):
            data_type_guess = "text"
        else:
            data_type_guess = "unknown"
        candidates.append({
            "row_index": row_idx + 2,
            "label": label_str,
            "value": val,
            "column": "B",
            "data_type_guess": data_type_guess,
        })
    return candidates
