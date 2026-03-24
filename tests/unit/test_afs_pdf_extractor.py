"""Unit tests for AFS PDF extractor."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from apps.api.app.services.afs.pdf_extractor import (
    PDFExtractResult,
    PDFSection,
    _detect_sections,
    extract_pdf,
    sections_to_json,
)


# ---------------------------------------------------------------------------
# sections_to_json
# ---------------------------------------------------------------------------


def test_sections_to_json_empty() -> None:
    """Empty list returns empty list."""
    assert sections_to_json([]) == []


def test_sections_to_json_single_section() -> None:
    """Single PDFSection converts to expected dict shape."""
    sec = PDFSection(
        title="Notes to Financial Statements",
        page_start=1,
        page_end=3,
        text="some text",
        tables=[],
    )
    result = sections_to_json([sec])
    assert len(result) == 1
    assert result[0]["title"] == "Notes to Financial Statements"
    assert result[0]["page_start"] == 1
    assert result[0]["page_end"] == 3
    assert result[0]["text"] == "some text"
    assert result[0]["tables"] == []


def test_sections_to_json_with_tables() -> None:
    """Tables are preserved in the JSON output."""
    tables = [[["Header1", "Header2"], ["Val1", "Val2"]]]
    sec = PDFSection(title="Balance Sheet", page_start=0, page_end=0, text="", tables=tables)
    result = sections_to_json([sec])
    assert result[0]["tables"] == tables


def test_sections_to_json_multiple_sections() -> None:
    """Multiple sections all serialise correctly."""
    sections = [
        PDFSection(title=f"Section {i}", page_start=i, page_end=i, text=f"text {i}", tables=[])
        for i in range(3)
    ]
    result = sections_to_json(sections)
    assert len(result) == 3
    for i, item in enumerate(result):
        assert item["title"] == f"Section {i}"
        assert item["page_start"] == i


# ---------------------------------------------------------------------------
# _detect_sections (internal, tested directly)
# ---------------------------------------------------------------------------


def test_detect_sections_empty_pages() -> None:
    """Empty page list returns empty sections list."""
    assert _detect_sections([]) == []


def test_detect_sections_no_headings_single_preamble() -> None:
    """Pages with no recognised headings produce a single Preamble section."""
    pages = ["Just some text\nMore text on same page"]
    sections = _detect_sections(pages)
    assert len(sections) == 1
    assert sections[0].title == "Preamble"
    assert sections[0].page_start == 0
    assert sections[0].page_end == 0


def test_detect_sections_known_heading_notes() -> None:
    """Page containing 'Notes to Financial Statements' triggers a new section."""
    pages = [
        "Intro text",
        "Notes to Financial Statements\nThe entity is incorporated in South Africa.",
    ]
    sections = _detect_sections(pages)
    titles = [s.title for s in sections]
    assert any("Notes to Financial Statements" in t for t in titles)


def test_detect_sections_statement_of_financial_position() -> None:
    """'Statement of Financial Position' heading creates a new section."""
    pages = ["Statement of Financial Position\nAssets: 100"]
    sections = _detect_sections(pages)
    titles = [s.title for s in sections]
    assert any("Statement of Financial Position" in t for t in titles)


def test_detect_sections_multi_page_multiple_headings() -> None:
    """Multiple pages each with a heading produce multiple sections."""
    pages = [
        "Directors' Report\nBoard met quarterly",
        "Auditor's Report\nWe have audited",
        "Statement of Cash Flows\nOperating activities",
    ]
    sections = _detect_sections(pages)
    assert len(sections) >= 2


def test_detect_sections_section_text_content() -> None:
    """Text between headings is captured in the preceding section."""
    pages = ["Preamble content line 1\nPreamble content line 2"]
    sections = _detect_sections(pages)
    assert len(sections) == 1
    assert "Preamble content line 1" in sections[0].text


def test_detect_sections_page_boundaries() -> None:
    """Sections track correct page_start and page_end indices."""
    pages = [
        "Statement of Financial Position\nLine A",
        "Income Statement\nLine B",
    ]
    sections = _detect_sections(pages)
    titles = [s.title for s in sections]
    sfp_idx = next(i for i, t in enumerate(titles) if "Financial Position" in t)
    # Statement of Financial Position detected on page 0 or starts at 0
    assert sections[sfp_idx].page_start == 0


# ---------------------------------------------------------------------------
# extract_pdf — no PDF library installed
# ---------------------------------------------------------------------------


def test_extract_pdf_no_library_returns_empty_result() -> None:
    """When neither pdfplumber nor pypdf is available, returns empty PDFExtractResult with warning."""
    with patch.dict(sys.modules, {"pdfplumber": None, "pypdf": None}):
        result = extract_pdf(b"")

    assert isinstance(result, PDFExtractResult)
    assert result.page_count == 0
    assert result.full_text == ""
    assert result.sections == []
    assert result.all_tables == []
    assert len(result.warnings) > 0
    warning_text = " ".join(result.warnings).lower()
    assert any(w in warning_text for w in ["pdf", "library", "pdfplumber", "available"])


def test_extract_pdf_pdfplumber_exception_returns_empty_with_warning() -> None:
    """When pdfplumber raises during open, result has warning and zero pages."""
    mock_pdfplumber = MagicMock()
    mock_pdfplumber.open.side_effect = Exception("corrupted PDF")

    with patch.dict(sys.modules, {"pdfplumber": mock_pdfplumber}):
        result = extract_pdf(b"\x00invalid")

    assert isinstance(result, PDFExtractResult)
    assert result.page_count == 0
    assert len(result.warnings) > 0


# ---------------------------------------------------------------------------
# extract_pdf — pdfplumber happy path (mocked)
# ---------------------------------------------------------------------------


def test_extract_pdf_pdfplumber_happy_path() -> None:
    """When pdfplumber returns pages with text, sections are detected and page count is correct."""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Statement of Financial Position\nAssets: 1000"
    mock_page.extract_tables.return_value = []

    mock_pdf_obj = MagicMock()
    mock_pdf_obj.pages = [mock_page]

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_pdf_obj)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    mock_pdfplumber = MagicMock()
    mock_pdfplumber.open.return_value = mock_ctx

    with patch.dict(sys.modules, {"pdfplumber": mock_pdfplumber}):
        result = extract_pdf(b"fake_pdf_bytes")

    assert result.page_count == 1
    assert "Statement of Financial Position" in result.full_text
    assert len(result.sections) >= 1
    assert result.warnings == []


def test_extract_pdf_pdfplumber_extracts_tables() -> None:
    """Tables extracted by pdfplumber are included in all_tables."""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Some text"
    mock_page.extract_tables.return_value = [[["Col A", "Col B"], ["1", "2"]]]

    mock_pdf_obj = MagicMock()
    mock_pdf_obj.pages = [mock_page]

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_pdf_obj)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    mock_pdfplumber = MagicMock()
    mock_pdfplumber.open.return_value = mock_ctx

    with patch.dict(sys.modules, {"pdfplumber": mock_pdfplumber}):
        result = extract_pdf(b"fake_pdf_bytes")

    assert len(result.all_tables) == 1
    assert result.all_tables[0][0] == ["Col A", "Col B"]
