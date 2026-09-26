"""
Search endpoint — retrieval-only, no LLM generation.
Per docs/08_API_CONTRACTS.md §5.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.rerank.reranker_service import rerank
from app.core.retrieval.fusion import reciprocal_rank_fusion
from app.core.retrieval.keyword import keyword_search
from app.core.retrieval.semantic import semantic_search
from app.core.security.auth import require_api_key
from app.db.session import get_db
from app.schemas.common import RetrievalResult
from app.schemas.query import SearchRequest, SearchResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    _key: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieval-only search — returns ranked chunks without LLM generation.
    Useful for search UI and retrieval debugging.
    """
    start_time = time.perf_counter()
    settings = get_settings()
    top_k = request.top_k or settings.RETRIEVAL_TOP_K_FINAL
    document_ids = [str(d) for d in request.scope.document_ids] if request.scope.document_ids else None

    # Semantic search
    semantic_results = semantic_search(
        query_text=request.query_text,
        org_id=str(request.scope.org_id),
        workspace_id=str(request.scope.workspace_id),
        top_n=settings.RETRIEVAL_TOP_N_SEMANTIC,
        document_ids=document_ids,
    )

    # Keyword search
    keyword_results = await keyword_search(
        db=db,
        query_text=request.query_text,
        org_id=str(request.scope.org_id),
        workspace_id=str(request.scope.workspace_id),
        top_n=settings.RETRIEVAL_TOP_N_KEYWORD,
        document_ids=document_ids,
    )

    # RRF fusion
    fused = reciprocal_rank_fusion(semantic_results, keyword_results)

    # Reranking
    reranked = rerank(query=request.query_text, candidates=fused, top_k=top_k)

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    # Fetch document names from DB if missing in payload
    doc_ids_needed = set(r.get("document_id") for r in reranked if r.get("document_id") and not r.get("document_name"))
    doc_name_map = {}
    if doc_ids_needed:
        from uuid import UUID
        from sqlalchemy import select
        from app.models.document import Document

        uuids = [UUID(d) for d in doc_ids_needed if d]
        stmt = select(Document.id, Document.filename).where(Document.id.in_(uuids))
        res = await db.execute(stmt)
        for d_id, fn in res.all():
            doc_name_map[str(d_id)] = fn

    results = [
        RetrievalResult(
            chunk_id=r.get("chunk_id", ""),
            document_id=r.get("document_id", ""),
            document_name=r.get("document_name") or doc_name_map.get(r.get("document_id", ""), "Document"),
            page_start=r.get("page_start", 0),
            page_end=r.get("page_end", 0),
            section_path=r.get("section_path"),
            snippet=r.get("text", "")[:300],
            semantic_score=round(float(r.get("semantic_score", 0.0) or 0.0), 4),
            keyword_score=round(float(r.get("keyword_score", 0.0) or 0.0), 4),
            fused_score=round(float(r.get("rrf_score", 0.0) or 0.0), 4),
            rerank_score=round(float(r.get("rerank_score", 0.0) or 0.0), 4),
        )
        for r in reranked
    ]

    return SearchResponse(
        results=results,
        total=len(results),
        latency_ms=elapsed_ms,
    )
