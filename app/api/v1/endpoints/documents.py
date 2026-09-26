"""
Document API endpoints.
Per docs/08_API_CONTRACTS.md §1-3.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import AnyHttpUrl, BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security.auth import require_api_key
from app.db.session import get_db
from app.models.chunk import Chunk
from app.models.job import ProcessingJob
from app.schemas.document import (
    DocumentChunkItem,
    DocumentChunksResponse,
    DocumentIngestResponse,
    ProcessingStatusResponse,
    ProcessingStageDetail,
    ReprocessRequest,
)
from app.services.document_service import ingest_document

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


class URLIngestRequest(BaseModel):
    """Request body for URL-based document ingestion."""
    url: AnyHttpUrl
    org_id: str
    workspace_id: str
    uploaded_by_user_id: str
    document_id: str | None = None
    folder_id: str | None = None


@router.post("/ingest", response_model=DocumentIngestResponse)
async def ingest(
    file: UploadFile = File(...),
    org_id: str = Form(...),
    workspace_id: str = Form(...),
    filename: str = Form(None),
    declared_mime_type: str = Form("application/pdf"),
    content_hash: str = Form(""),
    uploaded_by_user_id: str = Form(...),
    document_id: str = Form(None),
    folder_id: str = Form(None),
    _key: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest a new document for processing.
    Accepts multipart file upload.
    """
    settings = get_settings()

    # Validate file size
    file_data = await file.read()
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

    # org_id comes from the form field — Express is trusted to supply correct tenant values

    try:
        result = await ingest_document(
            db=db,
            file_data=file_data,
            filename=filename or file.filename or "document.pdf",
            org_id=org_id,
            workspace_id=workspace_id,
            uploaded_by_user_id=uploaded_by_user_id,
            document_id=document_id,
            folder_id=folder_id,
            content_hash=content_hash or None,
            declared_mime_type=declared_mime_type,
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


@router.post("/ingest-url", response_model=DocumentIngestResponse)
async def ingest_url(
    request: URLIngestRequest,
    _key: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest a document from a remote URL.

    Supports:
      - Static HTML web pages (e.g. https://gtwy.ai)
      - Remotely hosted PDFs (e.g. https://example.com/report.pdf)
      - Remote images (PNG, JPG, etc.)
      - Any URL returning a supported MIME type

    Note: JavaScript-rendered SPAs will return minimal text without
    a headless browser. Plain static HTML is fully supported.
    """
    from app.core.parsing.parser_factory import parse_from_url
    from app.core.storage.local_storage import get_storage
    import hashlib

    url_str = str(request.url)
    logger.info("URL ingest request: %s", url_str)

    try:
        # Fetch + parse the URL
        parsed_doc, mime_type, filename = parse_from_url(url_str)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "URL_FETCH_FAILED", "message": str(e), "details": {}}},
        )

    # Encode the parsed text as bytes for storage (we store the extracted text,
    # not the raw binary, since we already did the heavy parsing above).
    # This is intentional: for HTML pages there is no canonical binary to store.
    all_text = "\n\n".join(p.raw_text for p in parsed_doc.pages if p.raw_text)
    file_data = all_text.encode("utf-8")
    content_hash = hashlib.sha256(file_data).hexdigest()

    settings = get_settings()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "CONTENT_TOO_LARGE",
                    "message": f"Fetched content exceeds {settings.MAX_UPLOAD_SIZE_MB}MB.",
                    "details": {},
                }
            },
        )

    try:
        result = await ingest_document(
            db=db,
            file_data=file_data,
            filename=filename,
            org_id=request.org_id,
            workspace_id=request.workspace_id,
            uploaded_by_user_id=request.uploaded_by_user_id,
            document_id=request.document_id,
            folder_id=request.folder_id,
            content_hash=content_hash,
            declared_mime_type=mime_type,
        )
        from uuid import UUID
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
        logger.exception("URL ingestion failed for %s", url_str)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "PROCESSING_FAILED", "message": str(e), "details": {}}},
        )


@router.get("/{document_id}/status", response_model=ProcessingStatusResponse)
async def get_status(
    document_id: UUID,
    _key: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Poll processing status for a document."""
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
    _key: None = Depends(require_api_key),
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
    _key: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all indexed chunks for a specific document with pagination."""
    count_stmt = select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id)
    count_res = await db.execute(count_stmt)
    total = count_res.scalar_one() or 0

    stmt = (
        select(Chunk)
        .where(Chunk.document_id == document_id)
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
