"""Unit tests for memo_service.py — HTML generation and PDF export."""

from __future__ import annotations

import pytest

from apps.api.app.services.memo_service import (
    MEMO_TYPES,
    SECTION_TITLES,
    generate_memo_html,
    html_to_pdf,
)


def _sample_statements() -> dict:
    return {
        "income_statement": [
            {"revenue": 100_000, "cogs": 40_000, "ebitda": 60_000, "net_income": 45_000},
            {"revenue": 110_000, "cogs": 44_000, "ebitda": 66_000, "net_income": 49_500},
        ],
        "balance_sheet": [
            {"total_assets": 500_000, "total_equity": 300_000},
            {"total_assets": 550_000, "total_equity": 345_000},
        ],
        "cash_flow": [
            {"operating_cf": 50_000, "investing_cf": -20_000, "financing_cf": -10_000},
            {"operating_cf": 55_000, "investing_cf": -22_000, "financing_cf": -11_000},
        ],
        "periods": ["Jan 2026", "Feb 2026"],
    }


def test_generate_memo_html_returns_html_for_each_type() -> None:
    """Each memo type should produce valid HTML with correct title and sections."""
    statements = _sample_statements()
    for memo_type in MEMO_TYPES:
        html = generate_memo_html(memo_type, statements, run_id="run_test")
        assert "<!DOCTYPE html>" in html
        assert "run_test" in html
        for sec_title in SECTION_TITLES[memo_type]:
            assert sec_title in html, f"Section '{sec_title}' missing from {memo_type} memo"


def test_generate_memo_html_invalid_type_raises() -> None:
    """Unknown memo type should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown memo_type"):
        generate_memo_html("nonexistent", _sample_statements())


def test_generate_memo_html_empty_statements() -> None:
    """Empty statements should not crash — sections render 'No data'."""
    html = generate_memo_html("investment_committee", {"income_statement": [], "balance_sheet": [], "cash_flow": []})
    assert "No data" in html


def test_generate_memo_html_with_kpis() -> None:
    """KPIs should be rendered in the appropriate section."""
    kpis = [{"gross_margin": 0.60, "net_margin": 0.45, "fcf": 50_000}]
    html = generate_memo_html("investment_committee", _sample_statements(), kpis=kpis)
    assert "50,000" in html or "50000" in html


def test_generate_memo_html_custom_title() -> None:
    """Custom title should override the default."""
    html = generate_memo_html("credit_memo", _sample_statements(), title="Custom Memo Title")
    assert "Custom Memo Title" in html


def test_html_to_pdf_requires_xhtml2pdf() -> None:
    """PDF generation requires xhtml2pdf. If not installed, should raise RuntimeError."""
    html = generate_memo_html("valuation_note", _sample_statements())
    try:
        pdf_bytes = html_to_pdf(html)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b"%PDF"
    except RuntimeError as e:
        assert "xhtml2pdf" in str(e)
