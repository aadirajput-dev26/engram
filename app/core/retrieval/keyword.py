"""
Keyword retrieval via PostgreSQL full-text search.
Per docs/05_RETRIEVAL_AND_RERANKING.md §2.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)


async def keyword_search(
    db: AsyncSession,
    query_text: str,
    org_id: str,
    workspace_id: str,
    top_n: int = 30,
    document_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Perform full-text search against chunk tsvector with mandatory tenant filter.

    Args:
        db: Async database session.
        query_text: The user's query.
        org_id: Organization ID (mandatory filter).
        workspace_id: Workspace ID (mandatory filter).
        top_n: Number of candidates to return.
        document_ids: Optional document ID filter.

    Returns:
        List of result dicts with chunk_id, document_id, score, text, etc.
    """
    logger.debug("Keyword search: query='%s...', top_n=%d", query_text[:50], top_n)

    import re
    import uuid

    # Extract meaningful keywords for OR fallback if conversational full-sentence query has no exact AND matches
    raw_words = re.findall(r"\w+", query_text)
    stopwords = {
        "what", "is", "the", "in", "and", "or", "for", "to", "of", "a", "an", "on",
        "are", "do", "you", "have", "please", "provide", "all", "can", "tell", "me",
        "about", "show", "give", "with", "from", "at", "by", "this", "that", "these",
    }
    content_terms = [w for w in raw_words if len(w) > 1 and w.lower() not in stopwords]
    or_query = " | ".join(content_terms) if content_terms else ""

    params = {
        "query": query_text,
        "or_query": or_query,
        "has_or": bool(or_query),
        "org_id": uuid.UUID(org_id),
        "workspace_id": uuid.UUID(workspace_id),
        "limit": top_n,
    }

    doc_filter = ""
    if document_ids:
        doc_filter = "AND c.document_id = ANY(:document_ids)"
        params["document_ids"] = [uuid.UUID(d) for d in document_ids]

    sql = sa_text(f"""
        SELECT
            CAST(c.id AS text) AS chunk_id,
            CAST(c.document_id AS text) AS document_id,
            c.text,
            c.page_start,
            c.page_end,
            c.section_path,
            c.chunk_type,
            (
                COALESCE(ts_rank_cd(COALESCE(c.tsv, to_tsvector('english', c.text)), plainto_tsquery('english', :query)), 0.0) * 2.0
                + (CASE WHEN :has_or = true THEN COALESCE(ts_rank_cd(COALESCE(c.tsv, to_tsvector('english', c.text)), to_tsquery('english', :or_query)), 0.0) ELSE 0.0 END)
            ) AS keyword_score
        FROM chunks c
        WHERE
            c.org_id = :org_id
            AND c.workspace_id = :workspace_id
            AND (
                COALESCE(c.tsv, to_tsvector('english', c.text)) @@ plainto_tsquery('english', :query)
                OR (:has_or = true AND COALESCE(c.tsv, to_tsvector('english', c.text)) @@ to_tsquery('english', :or_query))
            )
            {doc_filter}
        ORDER BY keyword_score DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.mappings().all()

    results = []
    for rank, row in enumerate(rows, start=1):
        results.append({
            "chunk_id": row["chunk_id"],
            "document_id": row["document_id"],
            "text": row["text"],
            "page_start": row["page_start"],
            "page_end": row["page_end"],
            "section_path": row["section_path"],
            "chunk_type": row["chunk_type"],
            "keyword_score": float(row["keyword_score"]),
            "keyword_rank": rank,
        })

    logger.debug("Keyword search returned %d results", len(results))
    return results
