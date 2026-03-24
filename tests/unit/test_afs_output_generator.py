"""Unit tests for AFS Output Generator.

Bug coverage (RED):
  - entity_name containing '<script>' must be HTML-escaped in output
  - Section title containing HTML tags must be escaped in TOC and section heading
"""

from __future__ import annotations

import pytest

from apps.api.app.services.afs.output_generator import (
    _build_html,
    _md_table_to_html,
    generate_ixbrl,
    generate_pdf_html,
)


# ---------------------------------------------------------------------------
# _md_table_to_html
# ---------------------------------------------------------------------------


def test_md_table_to_html_basic() -> None:
    """Simple two-column table produces correct HTML structure."""
    md = "| Name | Value |\n|---|---|\n| Revenue | 1000 |"
    html = _md_table_to_html(md)
    assert "<table" in html
    assert "<thead>" in html
    assert "<th>" in html
    assert "Revenue" in html
    assert "1000" in html


def test_md_table_to_html_fewer_than_two_lines_returns_pre() -> None:
    """A single-line 'table' falls back to a <pre> block."""
    md = "Not a real table"
    html = _md_table_to_html(md)
    assert html.startswith("<pre>")


def test_md_table_to_html_no_body_rows() -> None:
    """Header-only table (no body rows) still produces valid <thead> without crashing."""
    md = "| Col1 | Col2 |\n|---|---|"
    html = _md_table_to_html(md)
    assert "<thead>" in html
    assert "<tbody>" in html


def test_md_table_to_html_multiple_rows() -> None:
    """Multiple body rows all appear in the output."""
    md = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
    html = _md_table_to_html(md)
    assert html.count("<tr>") >= 3  # 1 header + 2 body


# ---------------------------------------------------------------------------
# generate_pdf_html — structure and content
# ---------------------------------------------------------------------------


def test_generate_pdf_html_returns_bytes() -> None:
    """generate_pdf_html returns bytes (UTF-8 encoded HTML)."""
    result = generate_pdf_html("Acme Ltd", "2025-01-01", "2025-12-31", "IFRS", [])
    assert isinstance(result, bytes)
    assert result.startswith(b"<!DOCTYPE html>")


def test_generate_pdf_html_contains_entity_name() -> None:
    """Entity name appears in the generated HTML."""
    result = generate_pdf_html("Test Corp", "2025-01-01", "2025-12-31", "IFRS", [])
    assert b"Test Corp" in result


def test_generate_pdf_html_contains_period_dates() -> None:
    """Period start and end dates appear in the generated HTML."""
    result = generate_pdf_html("Acme", "2025-01-01", "2025-12-31", "IFRS", [])
    html = result.decode("utf-8")
    assert "2025-01-01" in html
    assert "2025-12-31" in html


def test_generate_pdf_html_contains_framework_name() -> None:
    """Framework name appears in the generated HTML."""
    result = generate_pdf_html("Acme", "2025-01-01", "2025-12-31", "IFRS for SMEs", [])
    assert b"IFRS for SMEs" in result


def test_generate_pdf_html_empty_sections_still_valid_html() -> None:
    """Empty sections list still produces valid HTML with cover and TOC."""
    result = generate_pdf_html("Acme", "2025-01-01", "2025-12-31", "IFRS", [])
    html = result.decode("utf-8")
    assert "<html" in html
    assert "</html>" in html
    assert "Table of Contents" in html


def test_generate_pdf_html_section_with_text_paragraph() -> None:
    """A text paragraph in a section produces a <p> tag."""
    sections = [
        {
            "title": "Revenue",
            "content_json": {
                "title": "Revenue",
                "paragraphs": [{"type": "text", "content": "Revenue is recognised at a point in time."}],
                "references": [],
                "warnings": [],
            },
        }
    ]
    result = generate_pdf_html("Acme", "2025-01-01", "2025-12-31", "IFRS", sections)
    html = result.decode("utf-8")
    assert "<p>" in html
    assert "Revenue is recognised at a point in time." in html


def test_generate_pdf_html_section_with_heading_paragraph() -> None:
    """A heading paragraph type produces an <h3> tag."""
    sections = [
        {
            "title": "PPE",
            "content_json": {
                "title": "PPE",
                "paragraphs": [{"type": "heading", "content": "Measurement Policy"}],
                "references": [],
                "warnings": [],
            },
        }
    ]
    result = generate_pdf_html("Acme", "2025-01-01", "2025-12-31", "IFRS", sections)
    html = result.decode("utf-8")
    assert "<h3>" in html
    assert "Measurement Policy" in html


def test_generate_pdf_html_section_with_table_paragraph() -> None:
    """A table paragraph type invokes _md_table_to_html (produces <table> tag)."""
    md_table = "| Item | Amount |\n|---|---|\n| Revenue | 1,000,000 |"
    sections = [
        {
            "title": "Financial Summary",
            "content_json": {
                "title": "Financial Summary",
                "paragraphs": [{"type": "table", "content": md_table}],
                "references": [],
                "warnings": [],
            },
        }
    ]
    result = generate_pdf_html("Acme", "2025-01-01", "2025-12-31", "IFRS", sections)
    html = result.decode("utf-8")
    assert "<table" in html


def test_generate_pdf_html_section_references_appear() -> None:
    """References in content_json appear in the output."""
    sections = [
        {
            "title": "Leases",
            "content_json": {
                "title": "Leases",
                "paragraphs": [],
                "references": ["IFRS 16.47", "IFRS 16.51"],
                "warnings": [],
            },
        }
    ]
    result = generate_pdf_html("Acme", "2025-01-01", "2025-12-31", "IFRS", sections)
    html = result.decode("utf-8")
    assert "IFRS 16.47" in html
    assert "IFRS 16.51" in html


def test_generate_pdf_html_section_warnings_appear() -> None:
    """Warnings in content_json appear in the output."""
    sections = [
        {
            "title": "Contingencies",
            "content_json": {
                "title": "Contingencies",
                "paragraphs": [],
                "references": [],
                "warnings": ["Legal case outcome uncertain — additional disclosure may be required"],
            },
        }
    ]
    result = generate_pdf_html("Acme", "2025-01-01", "2025-12-31", "IFRS", sections)
    html = result.decode("utf-8")
    assert "Legal case outcome uncertain" in html


# ---------------------------------------------------------------------------
# generate_pdf_html — XSS / HTML injection bug tests (RED before fix)
# ---------------------------------------------------------------------------


def test_generate_pdf_html_entity_name_xss_escaped() -> None:
    """[BUG] entity_name containing a <script> tag must be HTML-escaped.

    Before fix: '<script>alert(1)</script>' appears verbatim in output.
    After fix: it is escaped to '&lt;script&gt;alert(1)&lt;/script&gt;'.
    """
    result = generate_pdf_html(
        "<script>alert(1)</script>",
        "2025-01-01",
        "2025-12-31",
        "IFRS",
        [],
    )
    html = result.decode("utf-8")
    # The raw <script> tag must NOT appear unescaped
    assert "<script>alert(1)</script>" not in html
    # The escaped form must be present
    assert "&lt;script&gt;" in html


def test_generate_pdf_html_framework_name_xss_escaped() -> None:
    """[BUG] framework_name containing HTML must be escaped."""
    result = generate_pdf_html(
        "Acme Ltd",
        "2025-01-01",
        "2025-12-31",
        '<b onclick="evil()">IFRS</b>',
        [],
    )
    html = result.decode("utf-8")
    assert '<b onclick="evil()">IFRS</b>' not in html
    assert "&lt;b" in html or "onclick" not in html


def test_generate_pdf_html_section_title_xss_in_toc() -> None:
    """[BUG] Section title with HTML tags must be escaped in the TOC."""
    sections = [
        {
            "title": "<b>inject</b>",
            "content_json": {
                "title": "<b>inject</b>",
                "paragraphs": [],
                "references": [],
                "warnings": [],
            },
        }
    ]
    result = generate_pdf_html("Acme", "2025-01-01", "2025-12-31", "IFRS", sections)
    html = result.decode("utf-8")
    # The raw tag must not appear as-is in the TOC or section heading
    assert "<b>inject</b>" not in html
    assert "&lt;b&gt;inject&lt;/b&gt;" in html


def test_generate_pdf_html_paragraph_content_xss_escaped() -> None:
    """[BUG] Paragraph text content with XSS payload must be escaped."""
    sections = [
        {
            "title": "Notes",
            "content_json": {
                "title": "Notes",
                "paragraphs": [{"type": "text", "content": "<img src=x onerror=alert(1)>"}],
                "references": [],
                "warnings": [],
            },
        }
    ]
    result = generate_pdf_html("Acme", "2025-01-01", "2025-12-31", "IFRS", sections)
    html = result.decode("utf-8")
    assert "<img src=x onerror=alert(1)>" not in html
    assert "&lt;img" in html


# ---------------------------------------------------------------------------
# generate_ixbrl
# ---------------------------------------------------------------------------


def test_generate_ixbrl_returns_bytes() -> None:
    """generate_ixbrl returns bytes."""
    result = generate_ixbrl("Acme", "2025-01-01", "2025-12-31", "IFRS", "ifrs", [])
    assert isinstance(result, bytes)


def test_generate_ixbrl_contains_xbrl_namespace() -> None:
    """iXBRL output contains the ix:header and XBRL namespace attributes."""
    result = generate_ixbrl("Acme", "2025-01-01", "2025-12-31", "IFRS", "ifrs", [])
    html = result.decode("utf-8")
    assert "ix:header" in html
    assert "xmlns:ix=" in html


def test_generate_ixbrl_ifrs_taxonomy_url() -> None:
    """IFRS standard produces the IFRS taxonomy schema reference."""
    result = generate_ixbrl("Acme", "2025-01-01", "2025-12-31", "IFRS", "ifrs", [])
    html = result.decode("utf-8")
    assert "ifrs" in html.lower()


def test_generate_ixbrl_xss_entity_name_escaped() -> None:
    """[BUG] entity_name XSS in iXBRL context must also be escaped."""
    result = generate_ixbrl(
        "<script>evil()</script>",
        "2025-01-01",
        "2025-12-31",
        "IFRS",
        "ifrs",
        [],
    )
    html = result.decode("utf-8")
    assert "<script>evil()</script>" not in html
