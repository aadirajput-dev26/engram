"""
Query and Search request/response schemas.
Per docs/08_API_CONTRACTS.md §4-5 and docs/09_DATA_MODELS.md §12.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import Citation, RetrievalResult, ScopeFilter


# --- Query ---


class QueryRequest(BaseModel):
    """AI-based query request."""
    query_text: str
    scope: Optional[ScopeFilter] = None
    document_ids: Optional[List[UUID]] = None
    collection_id: Optional[UUID] = None
    route_override: Optional[Literal["structured", "rag", "hybrid"]] = None
    top_k: Optional[int] = None
    conversation_id: Optional[str] = None


class ExtractedFactSummary(BaseModel):
    """Summary of an extracted fact used as structured evidence."""
    fact_id: UUID
    metric: str
    value: float
    unit: str
    mine_name: Optional[str] = None
    period_value: str
    page_number: int


class QueryResponse(BaseModel):
    """AI query response with citations and evidence."""
    answer: str
    route_used: Literal["structured", "rag", "hybrid"]
    no_evidence: bool = False
    citations: List[Citation] = Field(default_factory=list)
    structured_evidence: List[ExtractedFactSummary] = Field(default_factory=list)
    confidence: float = 0.0
    latency_ms: int = 0


# --- Search ---


class SearchRequest(BaseModel):
    """Retrieval-only search request."""
    query_text: str
    scope: Optional[ScopeFilter] = None
    document_ids: Optional[List[UUID]] = None
    collection_id: Optional[UUID] = None
    top_k: Optional[int] = None
    filters: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    """Ranked retrieval results without LLM generation."""
    results: List[RetrievalResult] = Field(default_factory=list)
    total: int = 0
    latency_ms: int = 0
