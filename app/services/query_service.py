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
from app.domain.query_templates import templates

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
    metric = classification.metrics[0] if classification.metrics else "production"
    period = classification.periods[0] if classification.periods else ""

    if classification.mines:
        return await templates.get_metric_by_mine_and_period(
            session=db,
            org_id=org_id,
            workspace_id=workspace_id,
            metric=metric,
            mine_name=classification.mines[0],
            period_value=period,
            document_ids=document_ids,
        )
    elif classification.subsidiaries:
        return await templates.get_metric_aggregate_by_subsidiary_and_period(
            session=db,
            org_id=org_id,
            workspace_id=workspace_id,
            metric=metric,
            subsidiary_name=classification.subsidiaries[0],
            period_value=period,
            document_ids=document_ids,
        )
    elif classification.comparison and len(classification.periods) > 1:
        entity = classification.mines[0] if classification.mines else (classification.subsidiaries[0] if classification.subsidiaries else None)
        return await templates.compare_metric_across_periods(
            session=db,
            org_id=org_id,
            workspace_id=workspace_id,
            metric=metric,
            entity_name=entity,
            periods=classification.periods,
            document_ids=document_ids,
        )
    else:
        return await templates.get_metric_summary(
            session=db,
            org_id=org_id,
            workspace_id=workspace_id,
            metric=metric,
            period_value=period or None,
            document_ids=document_ids,
        )


async def process_query(
    db: AsyncSession,
    query_text: str,
    org_id: str,
    workspace_id: str,
    document_ids: Optional[List[str]] = None,
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

    # Semantic search (Qdrant)
    semantic_results = semantic_search(
        query_text=query_text,
        org_id=org_id,
        workspace_id=workspace_id,
        top_n=settings.RETRIEVAL_TOP_N_SEMANTIC,
        document_ids=document_ids,
    )

    # Keyword search (PostgreSQL FTS)
    keyword_results = await keyword_search(
        db=db,
        query_text=query_text,
        org_id=org_id,
        workspace_id=workspace_id,
        top_n=settings.RETRIEVAL_TOP_N_KEYWORD,
        document_ids=document_ids,
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
