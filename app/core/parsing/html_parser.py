"""
HTML parser for static web pages.

Uses httpx to fetch the page and BeautifulSoup4 to clean it.
Extracts meaningful body text by removing boilerplate elements
(nav, header, footer, scripts, styles, ads, sidebars).

This module handles TWO inputs:
  - A local .html file (from URL fetcher after downloading)
  - A URL string (convenience shortcut: fetches + parses inline)

Content is returned as a single ParsedPage with source_type="native".

Limitations (by design — no paid resources needed):
  - JavaScript-rendered SPAs will produce little/no text.
    Playwright integration is a future enhancement if needed.
  - Respects robots.txt is the caller's responsibility.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.core.parsing.pdf_parser import ParsedDocument, ParsedPage

logger = get_logger(__name__)

# Tags whose entire subtree should be removed before text extraction
_NOISE_TAGS = [
    "script", "style", "noscript", "nav", "header", "footer",
    "aside", "form", "button", "iframe", "svg", "figure",
    "advertisement", "banner",
]
# CSS class / id keywords that signal boilerplate
_NOISE_CLASSES = {
    "nav", "navbar", "menu", "sidebar", "footer", "header",
    "cookie", "advertisement", "ad", "popup", "modal",
    "breadcrumb", "pagination", "social", "share",
}


def parse_html_file(file_path: str) -> ParsedDocument:
    """
    Parse a locally saved HTML file.

    Args:
        file_path: Absolute path to a .html file.

    Returns:
        ParsedDocument with a single page.
    """
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        html_content = f.read()
    return _parse_html_string(html_content, source_label=file_path)


def parse_html_from_url(url: str, timeout: float = 20.0) -> ParsedDocument:
    """
    Fetch a live URL and parse its HTML content.

    Only static HTML is supported — JavaScript-heavy SPAs will return
    minimal text without a headless browser.

    Args:
        url:     HTTP/HTTPS URL to fetch.
        timeout: Request timeout in seconds.

    Returns:
        ParsedDocument with a single page.

    Raises:
        RuntimeError: On network or HTTP errors.
    """
    import httpx

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; RAGBot/1.0; +https://github.com/your-org)"
        ),
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            response = client.get(url, headers=headers)
        response.raise_for_status()
        logger.info(
            "Fetched URL '%s': HTTP %d, %d bytes",
            url, response.status_code, len(response.content),
        )
        return _parse_html_string(response.text, source_label=url)
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"HTTP {e.response.status_code} fetching {url}: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch URL {url}: {e}")


def _parse_html_string(html: str, source_label: str = "") -> ParsedDocument:
    """Core HTML → ParsedDocument conversion using BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError:
        raise RuntimeError(
            "beautifulsoup4 is required for HTML parsing. "
            "Install it with: pip install beautifulsoup4"
        )

    soup = BeautifulSoup(html, "html.parser")

    # --- Remove noise elements ---
    for tag in _NOISE_TAGS:
        for el in soup.find_all(tag):
            el.decompose()

    # Remove elements whose class or id contains noise keywords
    for el in soup.find_all(True):
        el_classes = set(c.lower() for c in (el.get("class") or []))
        el_id = (el.get("id") or "").lower()
        if el_classes & _NOISE_CLASSES or any(k in el_id for k in _NOISE_CLASSES):
            el.decompose()

    # --- Extract title ---
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # --- Extract main content ---
    # Prefer semantic main/article tags; fall back to body
    main_el = (
        soup.find("main")
        or soup.find("article")
        or soup.find(id="content")
        or soup.find(id="main")
        or soup.find("body")
        or soup
    )

    # Walk block-level elements to preserve paragraph structure
    raw_lines: list[str] = []
    if title:
        raw_lines.append(title)
        raw_lines.append("")

    for el in main_el.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "blockquote", "pre"],
        recursive=True,
    ):
        text = el.get_text(separator=" ", strip=True)
        if text and len(text) > 1:
            raw_lines.append(text)

    raw_text = "\n".join(raw_lines).strip()

    # De-duplicate consecutive identical lines (common in nav-heavy pages)
    deduped: list[str] = []
    prev = None
    for line in raw_lines:
        if line != prev:
            deduped.append(line)
        prev = line
    raw_text = "\n".join(deduped).strip()

    logger.info(
        "Parsed HTML from '%s': %d characters extracted",
        source_label, len(raw_text),
    )

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
        detected_type="html",
        tables=[],
    )
