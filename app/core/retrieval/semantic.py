"""
Semantic retrieval via Qdrant vector search.
Per docs/05_RETRIEVAL_AND_RERANKING.md.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.embeddings.embedding_service import embed_query
from app.core.logging import get_logger
from app.core.vectorstore.qdrant_service import search_vectors

logger = get_logger(__name__)


def semantic_search(
    query_text: str,
    org_id: str,
    workspace_id: str,
    top_n: int = 30,
    document_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Perform semantic vector search via Qdrant with mandatory tenant filtering.

    Args:
        query_text: The user's query.
        org_id: Organization ID (mandatory filter).
        workspace_id: Workspace ID (mandatory filter).
        top_n: Number of candidates to return.
        document_ids: Optional document ID filter.

    Returns:
        List of results with 'id', 'score', and payload fields.
        Each result includes 'chunk_id', 'document_id', 'page_start', etc.
    """
    logger.debug("Semantic search: query='%s...', top_n=%d", query_text[:50], top_n)

    # Embed the query
    query_vector = embed_query(query_text)
    if not query_vector:
        logger.warning("Empty query embedding produced")
        return []

    # Search Qdrant with mandatory tenant filter
    results = search_vectors(
        query_vector=query_vector,
        org_id=org_id,
        workspace_id=workspace_id,
        top_k=top_n,
        document_ids=document_ids,
    )

    # Add rank information
    for rank, result in enumerate(results, start=1):
        result["semantic_rank"] = rank
        result["semantic_score"] = result.get("score", 0.0)

    logger.debug("Semantic search returned %d results", len(results))
    return results
