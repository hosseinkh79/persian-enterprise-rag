"""PyMuPDF-based PDF parser. Fast default; fallback for scanned docs is OCR."""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pymupdf


@dataclass
class ParsedPage:
    page_number: int   # 1-indexed for human readability
    text: str


@dataclass
class ParsedDocument:
    source_path: str
    pages: list[ParsedPage]
    parser_used: str
    total_pages: int
    is_likely_scanned: bool  # True if text extraction yielded almost nothing


class PyMuPDFParser:
    """Extract text page-by-page. Fast, good for born-digital PDFs."""

    # If average chars per page is below this, likely a scanned document
    SCAN_THRESHOLD_CHARS_PER_PAGE = 50

    def parse(self, file_path: Path) -> ParsedDocument:
        doc = pymupdf.open(file_path)
        pages: list[ParsedPage] = []

        for page_num, page in enumerate(doc, start=1):
            # "text" = plain text in reading order (best effort)
            text = page.get_text("text")
            pages.append(ParsedPage(page_number=page_num, text=text))

        doc.close()

        total_chars = sum(len(p.text) for p in pages)
        avg_chars = total_chars / len(pages) if pages else 0

        return ParsedDocument(
            source_path=str(file_path),
            pages=pages,
            parser_used="pymupdf",
            total_pages=len(pages),
            is_likely_scanned=avg_chars < self.SCAN_THRESHOLD_CHARS_PER_PAGE,
        )