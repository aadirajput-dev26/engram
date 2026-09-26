"""
Image parser (PNG / JPG / JPEG / TIFF / BMP / WEBP).

Treats the image as a single-page document with source_type="scanned"
so that the document_service will automatically invoke the OCR engine
(ocr_page_image) on it, consistent with the existing scanned-PDF flow.

No OCR is run here — this module only produces the ParsedDocument shell.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.core.parsing.pdf_parser import ParsedDocument, ParsedPage

logger = get_logger(__name__)

# MIME types handled by this parser
SUPPORTED_IMAGE_MIMES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
    "image/bmp",
    "image/webp",
}


def parse_image(file_path: str) -> ParsedDocument:
    """
    Prepare an image file for OCR-based text extraction.

    Sets source_type="scanned" on the single ParsedPage so that
    document_service.ingest_document will call ocr_page_image()
    on it in the OCR stage, exactly as it does for scanned PDF pages.

    Args:
        file_path: Absolute path to the image file.

    Returns:
        ParsedDocument with one page (source_type="scanned", raw_text="").
    """
    logger.info("Image parser: queuing '%s' for OCR", file_path)

    # We emit a minimal page; the OCR stage will fill raw_text.
    page = ParsedPage(
        page_number=1,
        raw_text="",          # will be filled by OCR stage
        source_type="scanned",
        text_density=0,
        tables=[],
        blocks=[],
    )

    return ParsedDocument(
        page_count=1,
        pages=[page],
        detected_type="image",
        tables=[],
    )
