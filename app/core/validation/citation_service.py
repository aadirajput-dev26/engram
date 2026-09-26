"""
Citation service — formats final citations for API responses.
Per docs/09_DATA_MODELS.md §11.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)


def build_citations(
    answer: str,
    evidence_chunks: List[Dict[str, Any]],
    evidence_facts: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Extract and format citations from the LLM answer.

    Args:
        answer: The LLM's response text containing citation references.
        evidence_chunks: The evidence chunks (C1, C2, ...).
        evidence_facts: The evidence facts (F1, F2, ...).

    Returns:
        List of Citation dicts per docs/09_DATA_MODELS.md §11.
    """
    # Find all citation references in the answer
    cited_ids = set(re.findall(r"\[([CF]\d+)\]", answer))

    citations = []

    for cit_id in sorted(cited_ids):
        if cit_id.startswith("C"):
            idx = int(cit_id[1:]) - 1
            if 0 <= idx < len(evidence_chunks):
                chunk = evidence_chunks[idx]
                citations.append({
                    "citation_id": cit_id,
                    "source_type": "chunk",
                    "document_id": chunk.get("document_id", ""),
                    "document_name": chunk.get("document_name", ""),
                    "page_number": chunk.get("page_start"),
                    "section_path": chunk.get("section_path"),
                    "chunk_id": chunk.get("chunk_id"),
                    "fact_id": None,
                })

        elif cit_id.startswith("F") and evidence_facts:
            idx = int(cit_id[1:]) - 1
            if 0 <= idx < len(evidence_facts):
                fact = evidence_facts[idx]
                citations.append({
                    "citation_id": cit_id,
                    "source_type": "fact",
                    "document_id": fact.get("document_id", ""),
                    "document_name": fact.get("document_name", ""),
                    "page_number": fact.get("page_number"),
                    "section_path": fact.get("section_path"),
                    "chunk_id": None,
                    "fact_id": fact.get("fact_id") or fact.get("id"),
                })

    logger.debug("Built %d citations from answer", len(citations))
    return citations
