"""
Plain-text parser (.txt, .md, .rst).

Reads the file as UTF-8 text and wraps it in a single ParsedPage.
source_type is always "native" — no OCR is needed.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.core.parsing.pdf_parser import ParsedDocument, ParsedPage

logger = get_logger(__name__)


def parse_text(file_path: str) -> ParsedDocument:
    """
    Parse a plain-text file.

    Attempts UTF-8 decoding; falls back to latin-1 if the file is not
    valid UTF-8 (common for legacy text exports).

    Args:
        file_path: Absolute path to the text file.

    Returns:
        ParsedDocument with a single page containing the file content.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except UnicodeDecodeError:
        logger.warning(
            "UTF-8 decode failed for '%s'; retrying with latin-1", file_path
        )
        with open(file_path, "r", encoding="latin-1") as f:
            raw_text = f.read()

    raw_text = raw_text.strip()
    logger.info("Parsed text file: %d characters", len(raw_text))

    page = ParsedPage(
        page_number=1,
        raw_text=raw_text,
        source_type="native",
        text_density=len(raw_text),
        tables=[],
        blocks=[],
    )

    return ParsedDocument(
        page_count=1,
        pages=[page],
        detected_type="text",
        tables=[],
    )
