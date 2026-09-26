"""
URL fetcher utility.

Downloads a remote URL to local storage and detects what kind of content
it is (PDF, HTML, image, etc.) so the parser factory can route it correctly.

Supports:
  - Remote PDFs:   https://example.com/report.pdf
  - Static HTML:   https://gtwy.ai, https://example.com/page
  - Remote images: https://example.com/scan.png

Does NOT require any paid API — uses httpx + content-type sniffing only.
"""
from __future__ import annotations

import os
import tempfile
import urllib.parse
from dataclasses import dataclass

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

# Timeout for the initial HEAD probe and the full download
_HEAD_TIMEOUT = 10.0
_DOWNLOAD_TIMEOUT = 60.0

# Map of content-type prefixes → declared_mime_type sent to parser factory
_CONTENT_TYPE_MAP: dict[str, str] = {
    "application/pdf": "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
    "text/csv": "text/csv",
    "text/html": "text/html",
    "text/plain": "text/plain",
    "image/png": "image/png",
    "image/jpeg": "image/jpeg",
    "image/tiff": "image/tiff",
    "image/webp": "image/webp",
    "image/bmp": "image/bmp",
}

# Extension → MIME fallback when Content-Type header is missing/wrong
_EXT_MIME_MAP: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".md": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".html": "text/html",
    ".htm": "text/html",
}


@dataclass
class FetchedURL:
    """Result of fetching a remote URL to local storage."""
    local_path: str      # absolute path to the downloaded temp file
    mime_type: str       # resolved MIME type
    filename: str        # suggested filename for document records
    content_bytes: bytes # raw content


def fetch_url_to_tempfile(url: str) -> FetchedURL:
    """
    Download a URL to a temporary file and return metadata about it.

    The caller is responsible for cleaning up the temp file when done.

    Args:
        url: HTTP/HTTPS URL to fetch.

    Returns:
        FetchedURL with local_path, mime_type, filename, content_bytes.

    Raises:
        RuntimeError: On network errors or unsupported content types.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; RAGBot/1.0)",
        "Accept": "*/*",
    }

    # 1. Try a HEAD request to sniff content type without downloading
    mime_type: str = ""
    try:
        with httpx.Client(follow_redirects=True, timeout=_HEAD_TIMEOUT) as client:
            head_resp = client.head(url, headers=headers)
            ct = head_resp.headers.get("content-type", "")
            mime_type = _parse_content_type(ct)
            logger.debug("HEAD %s → content-type: %s → mime: %s", url, ct, mime_type)
    except Exception as e:
        logger.debug("HEAD request failed (%s), will fall back to extension/GET", e)

    # 2. Fall back to extension sniff from the URL path
    if not mime_type:
        parsed = urllib.parse.urlparse(url)
        ext = os.path.splitext(parsed.path)[1].lower()
        mime_type = _EXT_MIME_MAP.get(ext, "")

    # 3. Download the content
    logger.info("Downloading URL: %s (mime=%s)", url, mime_type or "unknown")
    try:
        with httpx.Client(follow_redirects=True, timeout=_DOWNLOAD_TIMEOUT) as client:
            response = client.get(url, headers=headers)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"HTTP {e.response.status_code} fetching {url}")
    except Exception as e:
        raise RuntimeError(f"Failed to download {url}: {e}")

    content = response.content

    # 4. If still no mime, try from GET response Content-Type header
    if not mime_type:
        ct = response.headers.get("content-type", "text/html")
        mime_type = _parse_content_type(ct) or "text/html"

    # 5. Determine a sensible filename
    filename = _derive_filename(url, mime_type)

    # 6. Write to a temp file with the right extension
    ext = _mime_to_ext(mime_type)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(content)
    except Exception:
        os.close(tmp_fd)
        raise

    logger.info(
        "Fetched '%s' → %s (%d bytes, mime=%s)",
        url, tmp_path, len(content), mime_type,
    )
    return FetchedURL(
        local_path=tmp_path,
        mime_type=mime_type,
        filename=filename,
        content_bytes=content,
    )


def _parse_content_type(content_type: str) -> str:
    """Extract and normalise the MIME type from a Content-Type header value."""
    if not content_type:
        return ""
    # Strip params like charset: "text/html; charset=utf-8" → "text/html"
    base = content_type.split(";")[0].strip().lower()
    # Match against known types
    for prefix, mime in _CONTENT_TYPE_MAP.items():
        if base.startswith(prefix):
            return mime
    return base  # return raw base if unknown


def _derive_filename(url: str, mime_type: str) -> str:
    """Derive a human-readable filename from a URL and MIME type."""
    parsed = urllib.parse.urlparse(url)
    path_part = parsed.path.rstrip("/")
    basename = os.path.basename(path_part) if path_part else ""
    if basename and "." in basename:
        return urllib.parse.unquote(basename)
    # Construct from host + extension
    host = parsed.netloc.replace("www.", "")
    ext = _mime_to_ext(mime_type)
    safe_host = host.replace(".", "_")
    return f"{safe_host}{ext}" if safe_host else f"document{ext}"


def _mime_to_ext(mime_type: str) -> str:
    """Return a file extension for a given MIME type."""
    mapping = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "text/csv": ".csv",
        "text/html": ".html",
        "text/plain": ".txt",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/tiff": ".tiff",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
    }
    return mapping.get(mime_type, ".bin")
