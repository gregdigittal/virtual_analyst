"""Extract text and tables from PDF AFS documents."""

from __future__ import annotations

import io
import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PDFSection:
    """A detected section in the PDF AFS."""
    title: str
    page_start: int
    page_end: int
    text: str
    tables: list[list[list[str]]]


@dataclass
class PDFExtractResult:
    """Result of extracting a PDF AFS."""
    page_count: int
    full_text: str
    sections: list[PDFSection]
    all_tables: list[list[list[str]]]
    warnings: list[str]


_SECTION_PATTERNS = [
    r"(?:note[s]?\s+(?:to\s+)?(?:the\s+)?financial\s+statements?)",
    r"(?:directors?['\u2019]?\s+report)",
    r"(?:audit(?:or[s]?)?['\u2019]?\s+report)",
    r"(?:statement\s+of\s+financial\s+position)",
    r"(?:(?:consolidated\s+)?balance\s+sheet)",
    r"(?:statement\s+of\s+(?:comprehensive\s+)?(?:profit\s+(?:or|and)\s+loss|income))",
    r"(?:income\s+statement)",
    r"(?:statement\s+of\s+cash\s*flows?)",
    r"(?:statement\s+of\s+changes\s+in\s+equity)",
    r"(?:accounting\s+policies?)",
    r"(?:note\s+\d+)",
    r"(?:\d+\.\s+[A-Z][a-z])",
]
_SECTION_RE = re.compile("|".join(f"({p})" for p in _SECTION_PATTERNS), re.IGNORECASE)


def extract_pdf(file_bytes: bytes) -> PDFExtractResult:
    """Extract text and tables from a PDF file."""
    try:
        import pdfplumber
    except ImportError:
        return _extract_fallback(file_bytes)

    warnings: list[str] = []
    pages_text: list[str] = []
    all_tables: list[list[list[str]]] = []

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages_text.append(text)

                tables = page.extract_tables()
                for table in tables:
                    cleaned = [[str(cell) if cell is not None else "" for cell in row] for row in table]
                    all_tables.append(cleaned)
    except Exception as e:
        warnings.append(f"PDF extraction error: {str(e)[:200]}")
        return PDFExtractResult(page_count=0, full_text="", sections=[], all_tables=[], warnings=warnings)

    full_text = "\n\n".join(pages_text)
    sections = _detect_sections(pages_text)

    return PDFExtractResult(
        page_count=page_count,
        full_text=full_text,
        sections=sections,
        all_tables=all_tables,
        warnings=warnings,
    )


def _detect_sections(pages_text: list[str]) -> list[PDFSection]:
    """Detect AFS sections from page text using heading heuristics."""
    sections: list[PDFSection] = []
    current_title = "Preamble"
    current_start = 0
    current_lines: list[str] = []

    for page_idx, page_text in enumerate(pages_text):
        for line in page_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                current_lines.append("")
                continue

            match = _SECTION_RE.search(stripped)
            if match and len(stripped) < 120:
                if current_lines:
                    sections.append(PDFSection(
                        title=current_title,
                        page_start=current_start,
                        page_end=page_idx,
                        text="\n".join(current_lines).strip(),
                        tables=[],
                    ))
                current_title = stripped
                current_start = page_idx
                current_lines = []
            else:
                current_lines.append(stripped)

    if current_lines:
        sections.append(PDFSection(
            title=current_title,
            page_start=current_start,
            page_end=len(pages_text) - 1,
            text="\n".join(current_lines).strip(),
            tables=[],
        ))

    return sections


def _extract_fallback(file_bytes: bytes) -> PDFExtractResult:
    """Fallback extraction using pypdf if pdfplumber is not available."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        full_text = "\n\n".join(pages_text)
        sections = _detect_sections(pages_text)
        return PDFExtractResult(
            page_count=len(reader.pages),
            full_text=full_text,
            sections=sections,
            all_tables=[],
            warnings=["pdfplumber not available; tables not extracted"],
        )
    except ImportError:
        return PDFExtractResult(
            page_count=0,
            full_text="",
            sections=[],
            all_tables=[],
            warnings=["No PDF library available (install pdfplumber or pypdf)"],
        )


def sections_to_json(sections: list[PDFSection]) -> list[dict[str, Any]]:
    """Convert sections to JSON-serialisable list."""
    return [asdict(s) for s in sections]
