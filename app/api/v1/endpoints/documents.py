"""
Document API endpoints.
Per docs/08_API_CONTRACTS.md §1-3.
"""
from __future__ import annotations

import hashlib
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security.auth import require_api_key
from app.db.session import async_session_factory, get_db
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.job import ProcessingJob
from app.schemas.auth import TenantContext
from app.schemas.document import (
    DocumentChunkItem,
    DocumentChunksResponse,
    DocumentIngestResponse,
    DocumentListItem,
    DocumentListResponse,
    ProcessingStageDetail,
    ProcessingStatusResponse,
    ReprocessRequest,
)
from app.services.document_service import ingest_document, queue_document_ingest, process_document_pipeline

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

async def _bg_run_document_pipeline(job_id: UUID, document_id: UUID, version_id: UUID, file_path: str):
    try:
        async with async_session_factory() as session:
            await process_document_pipeline(
                session=session,
                job_id=job_id,
                document_id=document_id,
                document_version_id=version_id,
                file_path=file_path,
            )
    except Exception as e:
        logger.exception("Background pipeline execution failed for doc %s: %s", document_id, e)


@router.post("/ingest", response_model=DocumentIngestResponse)
async def ingest(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    filename: Optional[str] = Form(None),
    declared_mime_type: Optional[str] = Form(None),
    content_hash: Optional[str] = Form(None),
    document_id: Optional[str] = Form(None),
    folder_id: Optional[str] = Form(None),
    tenant: TenantContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Unified ingestion endpoint accepting either a file upload or a URL.
    Tenant context (org_id, workspace_id, user_id) is automatically resolved from the API key.
    """
    settings = get_settings()

    if not file and not url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "MISSING_INPUT",
                    "message": "Either 'file' or 'url' must be provided for ingestion.",
                    "details": {},
                }
            },
        )

    # 1. Handle URL Ingestion
    if url and url.strip():
        from app.core.parsing.parser_factory import parse_from_url

        url_str = url.strip()
        logger.info("URL ingest request: %s (workspace=%s)", url_str, tenant.workspace_id)

        try:
            parsed_doc, detected_mime, default_filename = parse_from_url(url_str)
        except RuntimeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "URL_FETCH_FAILED", "message": str(e), "details": {}}},
            )
        except Exception as e:
            logger.exception("URL ingestion failed for %s", url_str)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": {"code": "PROCESSING_FAILED", "message": str(e), "details": {}}},
            )

        all_text = "\n\n".join(p.raw_text for p in parsed_doc.pages if p.raw_text)
        file_data = all_text.encode("utf-8")
        computed_hash = hashlib.sha256(file_data).hexdigest()
        effective_filename = filename or default_filename
        effective_mime = declared_mime_type or detected_mime
        effective_hash = content_hash or computed_hash

    # 2. Handle File Ingestion
    else:
        file_data = await file.read()
        effective_filename = filename or file.filename or "document.pdf"
        effective_mime = declared_mime_type or file.content_type or "application/pdf"
        effective_hash = content_hash or None

    # Validate file size
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB.",
                    "details": {"max_mb": settings.MAX_UPLOAD_SIZE_MB},
                }
            },
        )

    try:
        result = await queue_document_ingest(
            db=db,
            file_data=file_data,
            filename=effective_filename,
            org_id=str(tenant.org_id),
            workspace_id=str(tenant.workspace_id),
            uploaded_by_user_id=str(tenant.user_id),
            document_id=document_id,
            folder_id=folder_id,
            content_hash=effective_hash,
            declared_mime_type=effective_mime,
        )

        # Dispatch background pipeline execution (Non-blocking response returns <50ms)
        background_tasks.add_task(
            _bg_run_document_pipeline,
            UUID(result["job_id"]),
            UUID(result["document_id"]),
            UUID(result["document_version_id"]),
            result["file_path"],
        )

        return DocumentIngestResponse(
            document_id=UUID(result["document_id"]),
            document_version_id=UUID(result["document_version_id"]),
            job_id=UUID(result["job_id"]),
            status="QUEUED",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "details": {}}},
        )
    except Exception as e:
        logger.exception("Ingestion failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "PROCESSING_FAILED", "message": str(e), "details": {}}},
        )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Max documents to return"),
    folder_id: Optional[UUID] = Query(None, description="Optional folder/collection filter"),
    tenant: TenantContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    List all documents in the caller's workspace with pagination and status.
    Workspace scope is derived automatically from the API key.
    """
    # 1. Fetch documents page
    stmt = select(Document).where(
        Document.workspace_id == tenant.workspace_id,
        Document.org_id == tenant.org_id,
    )
    if folder_id:
        stmt = stmt.where(Document.folder_id == folder_id)

    stmt = stmt.order_by(Document.created_at.desc()).offset(skip).limit(limit)
    res = await db.execute(stmt)
    docs = res.scalars().all()

    # 2. Count total documents (skip redundant DB round-trip if on page 1 and fewer than limit)
    if skip == 0 and len(docs) < limit:
        total = len(docs)
    else:
        count_query = select(func.count(Document.id)).where(
            Document.workspace_id == tenant.workspace_id,
            Document.org_id == tenant.org_id,
        )
        if folder_id:
            count_query = count_query.where(Document.folder_id == folder_id)
        total_res = await db.execute(count_query)
        total = total_res.scalar_one() or 0

    # Query latest job status for these documents
    doc_ids = [d.id for d in docs]
    status_map = {}
    if doc_ids:
        jobs_stmt = (
            select(ProcessingJob.document_id, ProcessingJob.overall_status)
            .where(ProcessingJob.document_id.in_(doc_ids))
            .order_by(ProcessingJob.created_at.desc())
        )
        jobs_res = await db.execute(jobs_stmt)
        for d_id, status_val in jobs_res.all():
            if d_id not in status_map:
                status_map[d_id] = status_val

    items = [
        DocumentListItem(
            id=d.id,
            filename=d.filename,
            content_hash=d.content_hash,
            folder_id=d.folder_id,
            current_version_id=d.current_version_id,
            status=status_map.get(d.id, "READY"),
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in docs
    ]

    return DocumentListResponse(
        documents=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{document_id}/status", response_model=ProcessingStatusResponse)
async def get_status(
    document_id: UUID,
    tenant: TenantContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Poll processing status for a document."""
    # Ensure document belongs to tenant's workspace
    doc_res = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id == tenant.workspace_id,
        )
    )
    doc = doc_res.scalar_one_or_none()
    if not doc:
        # Check if job exists for this workspace
        job_check = await db.execute(
            select(ProcessingJob).where(
                ProcessingJob.document_id == document_id,
                ProcessingJob.workspace_id == tenant.workspace_id,
            )
        )
        if not job_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Document or processing job not found in this workspace.", "details": {}}},
            )

    result = await db.execute(
        select(ProcessingJob)
        .where(ProcessingJob.document_id == document_id)
        .order_by(ProcessingJob.created_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "No processing job found.", "details": {}}},
        )

    stages = []
    for stage_data in (job.stages or []):
        stages.append(ProcessingStageDetail(**stage_data) if isinstance(stage_data, dict) else stage_data)

    return ProcessingStatusResponse(
        document_id=job.document_id,
        document_version_id=job.document_version_id,
        job_id=job.id,
        overall_status=job.overall_status,
        stage_details=stages,
        updated_at=job.updated_at,
    )


@router.post("/{document_id}/process", response_model=DocumentIngestResponse)
async def reprocess(
    document_id: UUID,
    request: ReprocessRequest,
    tenant: TenantContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Re-trigger processing for a document."""
    # Placeholder — full reprocessing logic will be implemented in Slice 8
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"error": {"code": "NOT_IMPLEMENTED", "message": "Reprocessing not yet implemented.", "details": {}}},
    )


@router.get("/{document_id}/chunks", response_model=DocumentChunksResponse)
async def get_document_chunks(
    document_id: UUID,
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=200, description="Max chunks to return"),
    tenant: TenantContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all indexed chunks for a specific document with pagination."""
    # Ensure document belongs to tenant's workspace
    doc_res = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id == tenant.workspace_id,
        )
    )
    doc = doc_res.scalar_one_or_none()
    if not doc:
        # Check if chunks exist for this workspace
        chunk_check = await db.execute(
            select(Chunk.id).where(
                Chunk.document_id == document_id,
                Chunk.workspace_id == tenant.workspace_id,
            ).limit(1)
        )
        if not chunk_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Document not found in this workspace.", "details": {}}},
            )

    count_stmt = select(func.count()).select_from(Chunk).where(
        Chunk.document_id == document_id,
        Chunk.workspace_id == tenant.workspace_id,
    )
    count_res = await db.execute(count_stmt)
    total = count_res.scalar_one() or 0

    stmt = (
        select(Chunk)
        .where(
            Chunk.document_id == document_id,
            Chunk.workspace_id == tenant.workspace_id,
        )
        .order_by(Chunk.page_start.asc(), Chunk.char_offset_start.asc())
        .offset(skip)
        .limit(limit)
    )
    res = await db.execute(stmt)
    chunks_db = res.scalars().all()

    items = [
        DocumentChunkItem(
            chunk_id=c.id,
            document_id=c.document_id,
            document_version_id=c.document_version_id,
            page_start=c.page_start,
            page_end=c.page_end,
            section_path=c.section_path,
            chunk_type=c.chunk_type,
            text=c.text,
            char_offset_start=c.char_offset_start,
            char_offset_end=c.char_offset_end,
            embedding_model=c.embedding_model,
            created_at=c.created_at,
        )
        for c in chunks_db
    ]

    return DocumentChunksResponse(
        document_id=document_id,
        chunks=items,
        total=total,
        skip=skip,
        limit=limit,
    )
