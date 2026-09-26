"""
Reciprocal Rank Fusion (RRF) for combining semantic and keyword search results.
Per docs/05_RETRIEVAL_AND_RERANKING.md §4.

Formula: RRF(chunk) = Σ 1/(k + rank_r(chunk)) for r in {semantic, keyword}
Default k=60.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def reciprocal_rank_fusion(
    semantic_results: List[Dict[str, Any]],
    keyword_results: List[Dict[str, Any]],
    k: int | None = None,
    top_m: int | None = None,
) -> List[Dict[str, Any]]:
    """
    Fuse semantic and keyword search results using Reciprocal Rank Fusion.

    Args:
        semantic_results: Results from Qdrant semantic search.
        keyword_results: Results from PostgreSQL FTS.
        k: RRF constant (default from settings, typically 60).
        top_m: Number of fused results to return (default from settings).

    Returns:
        Fused and deduplicated results sorted by RRF score, top-M.
    """
    settings = get_settings()
    k = k or settings.RRF_K_CONSTANT
    top_m = top_m or settings.RETRIEVAL_TOP_M_FUSED

    # Build a map of chunk_id -> aggregated result
    fused: Dict[str, Dict[str, Any]] = {}

    # Process semantic results
    for result in semantic_results:
        chunk_id = result.get("chunk_id") or result.get("id", "")
        rank = result.get("semantic_rank", len(semantic_results) + 1)
        rrf_score = 1.0 / (k + rank)

        if chunk_id not in fused:
            fused[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": result.get("document_id", ""),
                "text": result.get("text", ""),
                "page_start": result.get("page_start", 0),
                "page_end": result.get("page_end", 0),
                "section_path": result.get("section_path"),
                "chunk_type": result.get("chunk_type", "paragraph"),
                "semantic_score": result.get("semantic_score", 0.0),
                "keyword_score": None,
                "rrf_score": 0.0,
            }

        fused[chunk_id]["rrf_score"] += rrf_score
        fused[chunk_id]["semantic_score"] = result.get("semantic_score", 0.0)

    # Process keyword results
    for result in keyword_results:
        chunk_id = result.get("chunk_id", "")
        rank = result.get("keyword_rank", len(keyword_results) + 1)
        rrf_score = 1.0 / (k + rank)

        if chunk_id not in fused:
            fused[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": result.get("document_id", ""),
                "text": result.get("text", ""),
                "page_start": result.get("page_start", 0),
                "page_end": result.get("page_end", 0),
                "section_path": result.get("section_path"),
                "chunk_type": result.get("chunk_type", "paragraph"),
                "semantic_score": None,
                "keyword_score": 0.0,
                "rrf_score": 0.0,
            }

        fused[chunk_id]["rrf_score"] += rrf_score
        fused[chunk_id]["keyword_score"] = result.get("keyword_score", 0.0)

    # Sort by RRF score descending and return top-M
    sorted_results = sorted(
        fused.values(), key=lambda x: x["rrf_score"], reverse=True
    )[:top_m]

    logger.info(
        "RRF fusion: %d semantic + %d keyword -> %d fused (k=%d, top_m=%d)",
        len(semantic_results), len(keyword_results), len(sorted_results), k, top_m,
    )

    return sorted_results
