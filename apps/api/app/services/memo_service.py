"""Memo pack generator (VA-P5-03): template-driven HTML from run data."""

from __future__ import annotations

import html as _html
from typing import Any

MEMO_TYPES = ("investment_committee", "credit_memo", "valuation_note")

SECTION_TITLES: dict[str, list[str]] = {
    "investment_committee": [
        "Executive Summary",
        "Business Overview",
        "Financial Highlights",
        "Key Assumptions",
        "Risk Analysis",
        "Valuation Summary",
        "Recommendation",
    ],
    "credit_memo": [
        "Borrower Overview",
        "Purpose of Facility",
        "Financial Analysis",
        "Ratio Analysis",
        "Covenant Headroom",
        "Security/Collateral",
        "Risk Assessment",
        "Recommendation",
    ],
    "valuation_note": [
        "Executive Summary",
        "Methodology",
        "Assumptions",
        "DCF Analysis",
        "Comparable Analysis",
        "Valuation Range",
        "Sensitivity",
    ],
}


def _format_table(rows: list[dict], period_labels: list[str] | None = None) -> str:
    """Render a list of period dicts as HTML table (first column = line item, rest = periods)."""
    if not rows:
        return "<p>No data</p>"
    keys = [k for k in rows[0].keys() if k != "period_index"]
    n_periods = len(rows)
    labels = period_labels or [f"P{i}" for i in range(n_periods)]
    html = ['<table class="memo-table"><thead><tr><th>Line Item</th>']
    for lbl in labels:
        html.append(f"<th>{_html.escape(str(lbl))}</th>")
    html.append("</tr></thead><tbody>")
    for key in keys:
        html.append(f"<tr><td>{_html.escape(key.replace('_', ' ').title())}</td>")
        for i, row in enumerate(rows):
            val = row.get(key)
            if isinstance(val, (int, float)):
                html.append(f"<td>{val:,.2f}</td>")
            else:
                html.append(f"<td>{_html.escape(str(val) if val is not None else '')}</td>")
        html.append("</tr>")
    html.append("</tbody></table>")
    return "".join(html)


def generate_memo_html(
    memo_type: str,
    statements: dict[str, Any],
    kpis: list[dict[str, Any]] | None = None,
    run_id: str = "",
    title: str | None = None,
) -> str:
    """Generate HTML memo from run statements (and optional KPIs). No LLM; data-only sections."""
    if memo_type not in MEMO_TYPES:
        raise ValueError(f"Unknown memo_type {memo_type!r}; must be one of {list(MEMO_TYPES)}")
    sections_titles = SECTION_TITLES.get(memo_type, SECTION_TITLES["investment_committee"])
    is_list = statements.get("income_statement") or []
    bs_list = statements.get("balance_sheet") or []
    cf_list = statements.get("cash_flow") or []
    periods = statements.get("periods") or [f"P{i}" for i in range(max(len(is_list), len(bs_list), len(cf_list)))]

    sections_html: list[dict[str, Any]] = []
    for i, sec_title in enumerate(sections_titles):
        content = ""
        if "Financial" in sec_title or "Highlights" in sec_title:
            content = _format_table(is_list, periods[: len(is_list)])
        elif "Balance" in sec_title or "Ratio" in sec_title:
            content = _format_table(bs_list, periods[: len(bs_list)])
        elif "Cash" in sec_title or "CF" in sec_title:
            content = _format_table(cf_list, periods[: len(cf_list)])
        elif "Assumption" in sec_title and kpis:
            content = _format_table(kpis, periods[: len(kpis)])
        else:
            content = f"<p>Section content for {_html.escape(sec_title)} (data-driven).</p>"
        sections_html.append({"title": sec_title, "content": content})

    doc_title = title or f"{memo_type.replace('_', ' ').title()} — Run {run_id}"
    safe_title = _html.escape(doc_title)
    html_parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'/><title>",
        safe_title,
        "</title><style>",
        "body{font-family:system-ui,sans-serif;margin:2rem;max-width:900px;}",
        ".memo-table{border-collapse:collapse;width:100%;margin:1rem 0;}",
        ".memo-table th,.memo-table td{border:1px solid #ddd;padding:0.5rem;text-align:right;}",
        ".memo-table th:first-child,.memo-table td:first-child{text-align:left;}",
        "h2{margin-top:2rem;border-bottom:1px solid #eee;}",
        "</style></head><body>",
        f"<h1>{safe_title}</h1>",
    ]
    for sec in sections_html:
        html_parts.append(f"<h2>{_html.escape(sec['title'])}</h2>")
        html_parts.append(sec["content"])
    html_parts.append("</body></html>")
    return "".join(html_parts)
