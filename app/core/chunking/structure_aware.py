"""
Structure-aware chunking.
Per docs/04_DOCUMENT_PROCESSING_SPEC.md §7.

Rules:
  - Paragraphs within a subsection are merged up to token budget (300-600 tokens).
  - NEVER merge across section boundaries.
  - Tables chunked separately.
  - Each chunk stores document_id, page range, section_path, content_hash.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.logging import get_logger
from app.core.pageindex.mapper import MappedSection

logger = get_logger(__name__)

# Default chunk size limits (in tokens, approximated as words)
DEFAULT_MIN_CHUNK_TOKENS = 100
DEFAULT_MAX_CHUNK_TOKENS = 600
DEFAULT_OVERLAP_RATIO = 0.10  # 10% overlap for split chunks


@dataclass
class ChunkRecord:
    """A chunk ready for embedding and indexing."""
    id: uuid.UUID
    text: str
    chunk_type: str  # "paragraph" | "table" | "heading_context"
    page_start: int
    page_end: int
    section_id: Optional[uuid.UUID] = None
    section_path: Optional[str] = None
    content_hash: str = ""
    char_offset_start: int = 0
    char_offset_end: int = 0


def _estimate_tokens(text: str) -> int:
    """Rough token count estimation (words ≈ tokens * 0.75)."""
    return len(text.split())


def _compute_hash(text: str) -> str:
    """Compute SHA-256 hash of normalized chunk text."""
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def chunk_document(
    pages_text: dict[int, str],
    sections: List[MappedSection],
    tables_text: dict[int, List[str]],
    max_tokens: int = DEFAULT_MAX_CHUNK_TOKENS,
    min_tokens: int = DEFAULT_MIN_CHUNK_TOKENS,
) -> List[ChunkRecord]:
    """
    Create structure-aware chunks from document content.

    Args:
        pages_text: Mapping of page_number (1-indexed) -> page text.
        sections: List of MappedSection records from PageIndex mapper.
        tables_text: Mapping of page_number -> list of table text representations.
        max_tokens: Maximum tokens per chunk.
        min_tokens: Minimum tokens before merging adjacent paragraphs.

    Returns:
        List of ChunkRecord ready for embedding.
    """
    chunks: List[ChunkRecord] = []

    if not sections:
        # Fallback: no sections, chunk by page
        logger.warning("No sections available, falling back to page-level chunking")
        for page_num, text in sorted(pages_text.items()):
            if text.strip():
                page_chunks = _split_text_into_chunks(
                    text, page_num, page_num, None, None, max_tokens
                )
                chunks.extend(page_chunks)
        # Add table chunks
        for page_num, table_texts in sorted(tables_text.items()):
            for tbl_text in table_texts:
                if tbl_text.strip():
                    chunks.append(ChunkRecord(
                        id=uuid.uuid4(),
                        text=tbl_text.strip(),
                        chunk_type="table",
                        page_start=page_num,
                        page_end=page_num,
                        content_hash=_compute_hash(tbl_text),
                    ))
        return chunks

    # Group page text by section
    for section in sections:
        section_text_parts: List[str] = []
        for page_num in range(section.page_start, section.page_end + 1):
            page_text = pages_text.get(page_num, "")
            if page_text.strip():
                section_text_parts.append(page_text.strip())

        combined_text = "\n\n".join(section_text_parts)
        if not combined_text.strip():
            continue

        # Split into paragraphs
        paragraphs = _split_into_paragraphs(combined_text)

        # Merge adjacent paragraphs within this section up to max_tokens
        merged_chunks = _merge_paragraphs(paragraphs, max_tokens, min_tokens)

        for chunk_text in merged_chunks:
            if chunk_text.strip():
                chunks.append(ChunkRecord(
                    id=uuid.uuid4(),
                    text=chunk_text.strip(),
                    chunk_type="paragraph",
                    page_start=section.page_start,
                    page_end=section.page_end,
                    section_id=section.id,
                    section_path=section.section_path,
                    content_hash=_compute_hash(chunk_text),
                ))

    # Add table chunks separately (never merged with paragraph text)
    for page_num, table_texts in sorted(tables_text.items()):
        # Find the section this table belongs to
        from app.core.pageindex.mapper import get_section_for_page
        section = get_section_for_page(sections, page_num)
        for tbl_text in table_texts:
            if tbl_text.strip():
                chunks.append(ChunkRecord(
                    id=uuid.uuid4(),
                    text=tbl_text.strip(),
                    chunk_type="table",
                    page_start=page_num,
                    page_end=page_num,
                    section_id=section.id if section else None,
                    section_path=section.section_path if section else None,
                    content_hash=_compute_hash(tbl_text),
                ))

    logger.info(
        "Created %d chunks (%d paragraph, %d table)",
        len(chunks),
        sum(1 for c in chunks if c.chunk_type == "paragraph"),
        sum(1 for c in chunks if c.chunk_type == "table"),
    )
    return chunks


def _split_into_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs by double newlines or significant whitespace."""
    # Split on double newlines
    raw_parts = re.split(r"\n\s*\n", text)
    paragraphs = [p.strip() for p in raw_parts if p.strip()]
    return paragraphs


def _merge_paragraphs(
    paragraphs: List[str], max_tokens: int, min_tokens: int
) -> List[str]:
    """Merge adjacent short paragraphs up to max_tokens. Never cross section boundaries."""
    if not paragraphs:
        return []

    merged = []
    current = paragraphs[0]

    for para in paragraphs[1:]:
        combined = current + "\n\n" + para
        if _estimate_tokens(combined) <= max_tokens:
            current = combined
        else:
            merged.append(current)
            current = para

    merged.append(current)

    # Split any chunks that exceed max_tokens
    final = []
    for chunk in merged:
        if _estimate_tokens(chunk) > max_tokens:
            final.extend(_split_at_sentences(chunk, max_tokens))
        else:
            final.append(chunk)

    return final


def _split_at_sentences(text: str, max_tokens: int) -> List[str]:
    """Split text at sentence boundaries when it exceeds max_tokens."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""

    for sentence in sentences:
        candidate = (current + " " + sentence).strip() if current else sentence
        if _estimate_tokens(candidate) > max_tokens and current:
            chunks.append(current.strip())
            current = sentence
        else:
            current = candidate

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _split_text_into_chunks(
    text: str,
    page_start: int,
    page_end: int,
    section_id: Optional[uuid.UUID],
    section_path: Optional[str],
    max_tokens: int,
) -> List[ChunkRecord]:
    """Split text into chunks respecting token limits."""
    paragraphs = _split_into_paragraphs(text)
    merged = _merge_paragraphs(paragraphs, max_tokens, DEFAULT_MIN_CHUNK_TOKENS)

    return [
        ChunkRecord(
            id=uuid.uuid4(),
            text=chunk_text.strip(),
            chunk_type="paragraph",
            page_start=page_start,
            page_end=page_end,
            section_id=section_id,
            section_path=section_path,
            content_hash=_compute_hash(chunk_text),
        )
        for chunk_text in merged
        if chunk_text.strip()
    ]
