"""PIM-7.8: Board pack PE portfolio section unit tests."""
from __future__ import annotations

from apps.api.app.services.board_pack_export import build_board_pack_html


_SECTION_ORDER = ["pe_portfolio"]
_NARRATIVE: dict = {}
_STATEMENTS: dict = {}
_KPI: list = []


def test_pe_section_not_rendered_without_data() -> None:
    """When pe_summary is None the pe_portfolio section is not in the output."""
    html = build_board_pack_html(
        label="Test Pack",
        section_order=_SECTION_ORDER,
        narrative=_NARRATIVE,
        statements=_STATEMENTS,
        kpis=_KPI,
        budget_summary=None,
        branding={},
        pe_summary=None,
    )
    assert "PE Portfolio" not in html


def test_pe_section_empty_when_no_assessments() -> None:
    """pe_summary with zero total renders 'No PE fund assessments on record'."""
    html = build_board_pack_html(
        label="Test Pack",
        section_order=_SECTION_ORDER,
        narrative=_NARRATIVE,
        statements=_STATEMENTS,
        kpis=_KPI,
        budget_summary=None,
        branding={},
        pe_summary={"total_assessments": 0, "assessments_with_irr": 0, "avg_dpi": None, "avg_tvpi": None, "avg_irr": None},
    )
    assert "PE Portfolio" in html
    assert "No PE fund assessments" in html


def test_pe_section_renders_metrics() -> None:
    """pe_summary with data renders DPI, TVPI, IRR rows."""
    html = build_board_pack_html(
        label="Test Pack",
        section_order=_SECTION_ORDER,
        narrative=_NARRATIVE,
        statements=_STATEMENTS,
        kpis=_KPI,
        budget_summary=None,
        branding={},
        pe_summary={
            "total_assessments": 4,
            "assessments_with_irr": 3,
            "avg_dpi": 1.40,
            "avg_tvpi": 1.85,
            "avg_irr": 0.17,
        },
    )
    assert "PE Portfolio" in html
    assert "1.40x" in html
    assert "1.85x" in html
    assert "17.0%" in html
    assert "Total Funds" in html
    assert "Funds with IRR" in html


def test_pe_section_in_toc() -> None:
    """pe_portfolio section appears in the table of contents."""
    html = build_board_pack_html(
        label="Test Pack",
        section_order=_SECTION_ORDER,
        narrative=_NARRATIVE,
        statements=_STATEMENTS,
        kpis=_KPI,
        budget_summary=None,
        branding={},
        pe_summary={"total_assessments": 2, "assessments_with_irr": 1, "avg_dpi": 1.1, "avg_tvpi": None, "avg_irr": None},
    )
    assert "pack-toc" in html
    assert "Pe Portfolio" in html
