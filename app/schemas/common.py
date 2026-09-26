"""
Common schemas used across multiple endpoints.
Per docs/08_API_CONTRACTS.md and docs/09_DATA_MODELS.md.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# --- Error Envelope ---


class ErrorDetail(BaseModel):
    """Standard error detail object."""
    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    """Standard error response envelope per docs/08_API_CONTRACTS.md §0."""
    error: ErrorDetail


# --- Scope ---


class ScopeFilter(BaseModel):
    """Scope filter for queries and searches."""
    org_id: UUID
    workspace_id: UUID
    document_ids: Optional[List[UUID]] = None


# --- Citation ---


class Citation(BaseModel):
    """Citation linking a claim to source evidence."""
    citation_id: str  # e.g. "C1" or "F1"
    source_type: Literal["chunk", "fact"]
    document_id: UUID
    document_name: str
    page_number: Optional[int] = None
    section_path: Optional[str] = None
    chunk_id: Optional[UUID] = None
    fact_id: Optional[UUID] = None


# --- Retrieval Result ---


class RetrievalResult(BaseModel):
    """A single retrieval candidate with scores from all stages."""
    chunk_id: UUID
    document_id: UUID
    document_name: str
    page_start: int
    page_end: int
    section_path: Optional[str] = None
    snippet: str
    semantic_score: Optional[float] = None
    keyword_score: Optional[float] = None
    fused_score: Optional[float] = None
    rerank_score: Optional[float] = None
