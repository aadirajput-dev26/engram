"""
Parser factory — unified entry point for all document types.

Routes a file (or URL) to the correct parser based on MIME type / extension.
Returns a ParsedDocument conforming to the interface defined in pdf_parser.py.

Usage:
    from app.core.parsing.parser_factory import parse_document, parse_from_url

    # From a local file:
    parsed = parse_document(file_path, "application/pdf", "report.pdf")

    # From a remote URL (HTML page, remote PDF, etc.):
    parsed, mime_type, filename = parse_from_url("https://gtwy.ai")
"""
from __future__ import annotations

import os

from app.core.logging import get_logger
from app.core.parsing.pdf_parser import ParsedDocument

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# MIME → parser routing table
# ---------------------------------------------------------------------------
_MIME_ROUTES: dict[str, str] = {
    # PDFs
    "application/pdf": "pdf",
    # Word documents
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "docx",
    # Excel spreadsheets
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xlsx",
    # CSV
    "text/csv": "csv",
    "application/csv": "csv",
    # Images
    "image/png": "image",
    "image/jpeg": "image",
    "image/jpg": "image",
    "image/tiff": "image",
    "image/bmp": "image",
    "image/webp": "image",
    "image/gif": "image",
    # HTML (web pages)
    "text/html": "html",
    "application/xhtml+xml": "html",
    # Plain text / markdown / rst
    "text/plain": "text",
    "text/markdown": "text",
    "text/x-rst": "text",
}

# Extension fallback when MIME type is absent or generic
_EXT_ROUTES: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "docx",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".csv": "csv",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tiff": "image",
    ".tif": "image",
    ".bmp": "image",
    ".webp": "image",
    ".gif": "image",
    ".html": "html",
    ".htm": "html",
    ".txt": "text",
    ".md": "text",
    ".rst": "text",
}


def parse_document(
    file_path: str,
    mime_type: str = "",
    filename: str = "",
) -> ParsedDocument:
    """
    Route a local file to the appropriate parser.

    Args:
        file_path: Absolute path to the file on disk.
        mime_type: Declared MIME type (e.g. "application/pdf").
                   If blank, extension-based detection is used as fallback.
        filename:  Original filename (used for extension fallback only).

    Returns:
        ParsedDocument with parsed content.

    Raises:
        ValueError: If the file type is unsupported.
        RuntimeError: On parse failures.
    """
    parser_type = _resolve_parser_type(mime_type, filename or file_path)
    logger.info(
        "parser_factory: routing '%s' (mime=%s) -> %s parser",
        os.path.basename(file_path), mime_type, parser_type,
    )

    if parser_type == "pdf":
        from app.core.parsing.pdf_parser import parse_pdf
        return parse_pdf(file_path)

    elif parser_type == "docx":
        from app.core.parsing.docx_parser import parse_docx
        return parse_docx(file_path)

    elif parser_type == "xlsx":
        from app.core.parsing.spreadsheet_parser import parse_spreadsheet
        return parse_spreadsheet(file_path, is_csv=False)

    elif parser_type == "csv":
        from app.core.parsing.spreadsheet_parser import parse_spreadsheet
        return parse_spreadsheet(file_path, is_csv=True)

    elif parser_type == "image":
        from app.core.parsing.image_parser import parse_image
        return parse_image(file_path)

    elif parser_type == "html":
        from app.core.parsing.html_parser import parse_html_file
        return parse_html_file(file_path)

    elif parser_type == "text":
        from app.core.parsing.text_parser import parse_text
        return parse_text(file_path)

    else:
        raise ValueError(
            f"Unsupported file type: mime='{mime_type}', "
            f"file='{os.path.basename(file_path)}'. "
            f"Supported types: PDF, DOCX, XLSX, CSV, images (PNG/JPG/TIFF/BMP/WebP), HTML, plain text."
        )


def parse_from_url(url: str) -> tuple[ParsedDocument, str, str]:
    """
    Fetch a remote URL and parse it.

    Downloads the URL to a temporary file, detects the MIME type, then
    routes to the correct parser. The temp file is cleaned up after parsing.

    For HTML pages (https://gtwy.ai, etc.) the HTML parser is used directly
    without saving to disk to avoid unnecessary I/O.

    Args:
        url: HTTP/HTTPS URL to fetch and ingest.

    Returns:
        Tuple of (ParsedDocument, resolved_mime_type, suggested_filename).

    Raises:
        RuntimeError: On network or parse failures.
    """
    from app.core.parsing.url_fetcher import fetch_url_to_tempfile

    fetched = fetch_url_to_tempfile(url)
    tmp_path = fetched.local_path

    try:
        # For HTML pages, use the in-memory fetcher path (avoids double download)
        if fetched.mime_type == "text/html":
            from app.core.parsing.html_parser import parse_html_from_url
            parsed = parse_html_from_url(url)
        else:
            parsed = parse_document(tmp_path, fetched.mime_type, fetched.filename)
    finally:
        # Always clean up the temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return parsed, fetched.mime_type, fetched.filename


def _resolve_parser_type(mime_type: str, filename: str) -> str:
    """Determine the parser type from mime_type, falling back to extension."""
    # Try MIME type first (normalise to lowercase, strip params)
    if mime_type:
        base_mime = mime_type.split(";")[0].strip().lower()
        if base_mime in _MIME_ROUTES:
            return _MIME_ROUTES[base_mime]
        # image/* wildcard
        if base_mime.startswith("image/"):
            return "image"

    # Fallback: file extension
    ext = os.path.splitext(filename)[1].lower()
    if ext in _EXT_ROUTES:
        return _EXT_ROUTES[ext]

    return "unknown"
