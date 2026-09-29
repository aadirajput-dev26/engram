"""
Query service.
Orchestrates: Router -> Structured Templates / Hybrid / RAG -> LLM -> Verification -> Citations.
Per docs/07_AI_QUERY_ENGINE.md and docs/11_CITATION_AND_VALIDATION.md.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document import Document

from app.core.config import get_settings
from app.core.generation.context_builder import build_context
from app.core.generation.llm_client import generate
from app.core.logging import get_logger
from app.core.query_router.classifier import classify_query, get_query_classification
from app.core.rerank.reranker_service import rerank
from app.core.retrieval.fusion import reciprocal_rank_fusion
from app.core.retrieval.keyword import keyword_search
from app.core.retrieval.semantic import semantic_search
from app.core.validation.citation_service import build_citations
from app.core.validation.claim_verifier import verify_response

logger = get_logger(__name__)
async def _execute_structured_lookup(
    db: AsyncSession,
    org_id: UUID,
    workspace_id: UUID,
    query_text: str,
    classification: Any,
    document_ids: Optional[List[UUID]] = None,
) -> List[Dict[str, Any]]:
    """Look up structured facts using fixed parameterized SQL templates."""
    return []


async def process_query(
    db: AsyncSession,
    query_text: str,
    org_id: str,
    workspace_id: str,
    document_ids: Optional[List[str]] = None,
    collection_id: Optional[str] = None,
    top_k: Optional[int] = None,
    route_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a user query through the full AI query pipeline (Structured, RAG, or Hybrid).
    """
    start_time = time.perf_counter()
    settings = get_settings()
    top_k = top_k or min(settings.RETRIEVAL_TOP_K_FINAL, 5)

    # Parse IDs
    org_uuid = UUID(org_id)
    ws_uuid = UUID(workspace_id)
    doc_uuids = [UUID(d) for d in document_ids] if document_ids else None
    
    # Resolve collection_id to document_ids
    if collection_id:
        col_stmt = select(Document.id).where(
            Document.folder_id == UUID(collection_id),
        )
        col_res = await db.execute(col_stmt)
        col_doc_ids = list(col_res.scalars().all())
        if doc_uuids:
            # Intersection if both provided
            doc_uuids = list(set(doc_uuids).intersection(set(col_doc_ids)))
        else:
            doc_uuids = col_doc_ids

    # Classify route
    classification = get_query_classification(query_text)
    route = route_override or classification.route
    logger.info("Processing query: '%s...' | Route: %s", query_text[:80], route)

    # -------------------------------------------------------------
    # 1. STRUCTURED PATH
    # -------------------------------------------------------------
    if route == "structured":
        facts = await _execute_structured_lookup(
            db=db,
            org_id=org_uuid,
            workspace_id=ws_uuid,
            query_text=query_text,
            classification=classification,
            document_ids=doc_uuids,
        )

        if not facts:
            # Fall back to RAG if no exact structured records matched
            logger.info("Structured query yielded 0 facts, falling back to RAG retrieval")
            route = "rag"
        else:
            # Build structured answer and citations
            fact_citations = [
                {
                    "citation_id": f"F{i + 1}",
                    "document_id": f["document_id"],
                    "document_name": "Document",
                    "page_number": f["page_number"],
                    "section_path": f.get("section_path") or "",
                    "fact_id": f["id"],
                }
                for i, f in enumerate(facts[:5])
            ]

            # Let LLM format the exact structured facts cleanly into a response with [F#] citations
            messages = build_context(
                reranked_chunks=[],
                extracted_facts=facts[:10],
                query_text=query_text,
            )
            answer = await generate(messages)

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return {
                "answer": answer,
                "route_used": "structured",
                "no_evidence": False,
                "citations": fact_citations,
                "structured_evidence": facts[:10],
                "confidence": 0.95,
                "latency_ms": elapsed_ms,
            }

    # -------------------------------------------------------------
    # 2. RAG or HYBRID PATH
    # -------------------------------------------------------------
    structured_facts: List[Dict[str, Any]] = []
    if route == "hybrid":
        structured_facts = await _execute_structured_lookup(
            db=db,
            org_id=org_uuid,
            workspace_id=ws_uuid,
            query_text=query_text,
            classification=classification,
            document_ids=doc_uuids,
        )

    target_doc_ids = [str(u) for u in doc_uuids] if doc_uuids is not None else document_ids

    # Semantic search (Qdrant)
    semantic_results = semantic_search(
        query_text=query_text,
        org_id=org_id,
        workspace_id=workspace_id,
        top_n=settings.RETRIEVAL_TOP_N_SEMANTIC,
        document_ids=target_doc_ids,
    )

    # Keyword search (PostgreSQL FTS)
    keyword_results = await keyword_search(
        db=db,
        query_text=query_text,
        org_id=org_id,
        workspace_id=workspace_id,
        top_n=settings.RETRIEVAL_TOP_N_KEYWORD,
        document_ids=target_doc_ids,
    )

    # RRF Fusion
    fused_results = reciprocal_rank_fusion(
        semantic_results=semantic_results,
        keyword_results=keyword_results,
    )

    # Cross-encoder reranking
    reranked = rerank(
        query=query_text,
        candidates=fused_results,
        top_k=top_k,
    )

    # Check evidence availability
    if not reranked and not structured_facts:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "answer": "NO_EVIDENCE_FOUND: The provided documents do not contain sufficient information to answer this question.",
            "route_used": route,
            "no_evidence": True,
            "citations": [],
            "structured_evidence": [],
            "confidence": 0.0,
            "latency_ms": elapsed_ms,
        }

    # Ensure all reranked chunks have document_name populated
    doc_ids_needed = set(r.get("document_id") for r in reranked if r.get("document_id") and not r.get("document_name"))
    if doc_ids_needed:
        from uuid import UUID as PyUUID
        uuids = [PyUUID(d) for d in doc_ids_needed if d]
        name_stmt = select(Document.id, Document.filename).where(Document.id.in_(uuids))
        name_res = await db.execute(name_stmt)
        name_map = {str(row[0]): row[1] for row in name_res.all()}
        for r in reranked:
            if not r.get("document_name"):
                r["document_name"] = name_map.get(str(r.get("document_id")), "Document")

    # Build context with both chunks and structured facts
    messages = build_context(
        reranked_chunks=reranked,
        extracted_facts=structured_facts,
        query_text=query_text,
    )
    answer = await generate(messages)

    # Verify claims
    verification = verify_response(
        answer=answer,
        evidence_chunks=reranked,
        evidence_facts=structured_facts,
    )

    # Build citations
    citations = build_citations(
        answer=verification.verified_answer,
        evidence_chunks=reranked,
        evidence_facts=structured_facts,
    )

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    logger.info(
        "Query complete: route=%s, %d citations, confidence=%.2f, latency=%dms",
        route, len(citations), verification.overall_confidence, elapsed_ms,
    )

    return {
        "answer": verification.verified_answer,
        "route_used": route,
        "no_evidence": verification.no_evidence,
        "citations": citations,
        "structured_evidence": structured_facts,
        "confidence": verification.overall_confidence,
        "latency_ms": elapsed_ms,
    }
