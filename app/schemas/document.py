"""
Document-related request/response schemas.
Per docs/08_API_CONTRACTS.md §1-3 and docs/09_DATA_MODELS.md.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# --- Ingest ---


class DocumentIngestRequest(BaseModel):
    """Request to ingest a new document or new version."""
    org_id: UUID
    workspace_id: UUID
    folder_id: Optional[UUID] = None
    document_id: Optional[UUID] = None  # if provided, this is a new version
    filename: str
    declared_mime_type: str = "application/pdf"
    content_hash: str
    uploaded_by_user_id: UUID
    file_ref: Optional[str] = None  # object storage key (for large files)


class DocumentIngestResponse(BaseModel):
    """Response after document ingestion."""
    document_id: UUID
    document_version_id: UUID
    job_id: UUID
    status: Literal["QUEUED", "ALREADY_PROCESSED"]


# --- Status ---


class ProcessingStageDetail(BaseModel):
    """Status of a single processing stage."""
    stage: str
    progress_current: Optional[int] = None
    progress_total: Optional[int] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ProcessingStatusResponse(BaseModel):
    """Response for processing status polling."""
    document_id: UUID
    document_version_id: UUID
    job_id: UUID
    overall_status: str
    stage_details: List[ProcessingStageDetail] = Field(default_factory=list)
    updated_at: datetime


# --- Reprocess ---


class ReprocessRequest(BaseModel):
    """Request to re-trigger processing."""
    stages: Optional[List[str]] = None
    document_version_id: Optional[UUID] = None


# --- Document Chunks ---


class DocumentChunkItem(BaseModel):
    """Schema for a single chunk of a document."""
    chunk_id: UUID
    document_id: UUID
    document_version_id: UUID
    page_start: int
    page_end: int
    section_path: Optional[str] = None
    chunk_type: str
    text: str
    char_offset_start: int = 0
    char_offset_end: int = 0
    embedding_model: Optional[str] = None
    created_at: Optional[datetime] = None


class DocumentChunksResponse(BaseModel):
    """Response containing chunk list for a document."""
    document_id: UUID
    chunks: List[DocumentChunkItem]
    total: int
    skip: int
    limit: int
