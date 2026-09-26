"""
PDF parsing using PyMuPDF (fitz).
Handles native text extraction, page classification (digital vs scanned),
table detection, and layout block extraction.

Per docs/04_DOCUMENT_PROCESSING_SPEC.md §1-5.
PyMuPDF is used ONLY for native text extraction — it does NOT perform OCR.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

# Text density threshold: pages with fewer chars/page are classified as "scanned"
_MIN_TEXT_DENSITY = 50  # characters per page


@dataclass
class DetectedTable:
    """A table detected on a page."""
    page_number: int
    row_count: int
    col_count: int
    header_row: Optional[List[str]] = None
    raw_cells: List[List[str]] = field(default_factory=list)


@dataclass
class ParsedPage:
    """Result of parsing a single PDF page."""
    page_number: int  # 1-indexed
    raw_text: str
    source_type: str  # "native" or "scanned" (needs OCR)
    text_density: float  # characters per page
    tables: List[DetectedTable] = field(default_factory=list)
    blocks: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ParsedDocument:
    """Result of parsing an entire PDF."""
    page_count: int
    pages: List[ParsedPage]
    detected_type: str  # "digital_pdf" or "scanned_pdf" or "mixed_pdf"
    tables: List[DetectedTable]


def parse_pdf(file_path: str) -> ParsedDocument:
    """
    Parse a PDF file using PyMuPDF.
    Classifies each page as digital or scanned based on text density.
    Detects tables on digital pages.

    Args:
        file_path: Path to the PDF file.

    Returns:
        ParsedDocument with per-page results.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(file_path)
    pages: List[ParsedPage] = []
    all_tables: List[DetectedTable] = []
    digital_count = 0
    scanned_count = 0

    try:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_number = page_idx + 1  # 1-indexed

            # Extract native text
            raw_text = page.get_text("text") or ""
            text_density = len(raw_text.strip())

            # Classify page
            if text_density >= _MIN_TEXT_DENSITY:
                source_type = "native"
                digital_count += 1
            else:
                source_type = "scanned"
                scanned_count += 1

            # Extract text blocks for layout understanding
            blocks = []
            for block in page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE).get("blocks", []):
                if block.get("type") == 0:  # text block
                    block_text = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            block_text += span.get("text", "")
                        block_text += "\n"
                    blocks.append({
                        "type": "text",
                        "text": block_text.strip(),
                        "bbox": block.get("bbox", []),
                        "font_size": _get_dominant_font_size(block),
                    })

            # Detect tables on digital pages
            page_tables: List[DetectedTable] = []
            if source_type == "native":
                try:
                    tab_finder = page.find_tables()
                    for tab in tab_finder.tables:
                        rows = tab.extract()
                        if rows:
                            header = rows[0] if rows else None
                            dt = DetectedTable(
                                page_number=page_number,
                                row_count=len(rows),
                                col_count=len(rows[0]) if rows else 0,
                                header_row=[str(c) if c else "" for c in header] if header else None,
                                raw_cells=[
                                    [str(c) if c else "" for c in row]
                                    for row in rows
                                ],
                            )
                            page_tables.append(dt)
                            all_tables.append(dt)
                except Exception as e:
                    logger.warning(
                        "Table detection failed on page %d: %s", page_number, e
                    )

            pages.append(ParsedPage(
                page_number=page_number,
                raw_text=raw_text,
                source_type=source_type,
                text_density=text_density,
                tables=page_tables,
                blocks=blocks,
            ))

    finally:
        doc.close()

    # Determine overall document type
    total = digital_count + scanned_count
    if scanned_count == 0:
        detected_type = "digital_pdf"
    elif digital_count == 0:
        detected_type = "scanned_pdf"
    else:
        detected_type = "mixed_pdf"

    logger.info(
        "Parsed PDF: %d pages (%d digital, %d scanned), %d tables detected",
        total, digital_count, scanned_count, len(all_tables),
    )

    return ParsedDocument(
        page_count=total,
        pages=pages,
        detected_type=detected_type,
        tables=all_tables,
    )


def _get_dominant_font_size(block: dict) -> float:
    """Extract the most common font size from a text block."""
    sizes = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            if "size" in span:
                sizes.append(span["size"])
    if not sizes:
        return 0.0
    # Return the most common size
    from collections import Counter
    return Counter(sizes).most_common(1)[0][0]
