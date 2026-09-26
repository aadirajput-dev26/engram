"""
Document ingestion service.
Orchestrates the full pipeline: Ingest -> Parse -> OCR -> PageIndex -> DB -> Chunk -> Embed -> Index.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chunking.structure_aware import ChunkRecord, chunk_document
from app.core.config import get_settings
from app.core.embeddings.embedding_service import embed_texts, get_embedding_dimension, get_model_name
from app.core.logging import get_logger
from app.core.ocr.ocr_service import is_ocr_available, ocr_page_image, ocr_pdf_page
from app.core.pageindex.adapter import PageIndexAdapter, get_pageindex_adapter
from app.core.pageindex.mapper import MappedSection, map_tree_to_sections
from app.core.parsing.parser_factory import parse_document
from app.core.parsing.pdf_parser import ParsedDocument
from app.core.storage.local_storage import get_storage
from app.core.vectorstore.qdrant_service import ensure_collection, upsert_chunks
from app.models.chunk import Chunk
from app.models.document import Document, DocumentMetadata, DocumentVersion
from app.models.job import ProcessingJob
from app.models.page import Page
from app.models.section import Section
from app.models.table import Table

logger = get_logger(__name__)


async def ingest_document(
    db: AsyncSession,
    file_data: bytes,
    filename: str,
    org_id: str,
    workspace_id: str,
    uploaded_by_user_id: str,
    document_id: Optional[str] = None,
    folder_id: Optional[str] = None,
    content_hash: Optional[str] = None,
    declared_mime_type: str = "application/pdf",
) -> Dict[str, Any]:
    """
    Ingest and process a document through the full pipeline.

    Returns:
        Dict with document_id, document_version_id, job_id, status.
    """
    storage = get_storage()
    settings = get_settings()

    # 1. Compute content hash and check for duplicates
    computed_hash = storage.compute_hash(file_data)
    if content_hash and content_hash != computed_hash:
        raise ValueError(
            f"Content hash mismatch: declared={content_hash}, computed={computed_hash}"
        )

    # 2. Create or get Document record
    doc_id = uuid.UUID(document_id) if document_id else uuid.uuid4()
    doc = Document(
        id=doc_id,
        org_id=uuid.UUID(org_id),
        workspace_id=uuid.UUID(workspace_id),
        folder_id=uuid.UUID(folder_id) if folder_id else None,
        filename=filename,
        content_hash=computed_hash,
    )
    db.add(doc)
    await db.flush()

    # 3. Create DocumentVersion
    version_id = uuid.uuid4()
    file_key = f"documents/{org_id}/{workspace_id}/{doc_id}/{version_id}/{filename}"
    storage.save_file(file_key, file_data)

    version = DocumentVersion(
        id=version_id,
        document_id=doc_id,
        version_number=1,
        file_ref=file_key,
        declared_mime_type=declared_mime_type,
        uploaded_by_user_id=uuid.UUID(uploaded_by_user_id),
    )
    db.add(version)
    await db.flush()

    doc.current_version_id = version_id

    # 4. Create ProcessingJob
    job_id = uuid.uuid4()
    job = ProcessingJob(
        id=job_id,
        document_id=doc_id,
        document_version_id=version_id,
        org_id=uuid.UUID(org_id),
        workspace_id=uuid.UUID(workspace_id),
        overall_status="PROCESSING",
        stages=[],
        created_by_user_id=uuid.UUID(uploaded_by_user_id),
    )
    db.add(job)
    await db.flush()

    try:
        # 5. Parse document (routes to PDF / DOCX / XLSX / CSV / image / HTML / text parser)
        logger.info("Stage: PARSING document %s (mime=%s)", filename, declared_mime_type)
        file_path = storage.get_file_path(file_key)
        parsed = parse_document(file_path, declared_mime_type, filename)
        version.page_count = parsed.page_count
        version.detected_type = parsed.detected_type

        # 6. Save Page records (with honest OCR)
        logger.info("Stage: OCR for %d pages", parsed.page_count)
        pages_text: Dict[int, str] = {}
        # Images and scanned pages both arrive as source_type="scanned".
        # Images use ocr_page_image (directly on the file); PDFs use ocr_pdf_page.
        _is_image_mime = declared_mime_type.startswith("image/")

        for parsed_page in parsed.pages:
            if parsed_page.source_type == "native":
                source_type = "native"
                ocr_confidence = None
                raw_text = parsed_page.raw_text
            elif parsed_page.source_type == "scanned":
                # Route OCR: images → ocr_page_image, PDFs → ocr_pdf_page
                if _is_image_mime:
                    ocr_result = ocr_page_image(file_path)
                else:
                    ocr_result = ocr_pdf_page(file_path, parsed_page.page_number)
                source_type = ocr_result.source_type
                ocr_confidence = ocr_result.ocr_confidence
                raw_text = ocr_result.raw_text or parsed_page.raw_text
            else:
                source_type = "native"
                ocr_confidence = None
                raw_text = parsed_page.raw_text

            page = Page(
                id=uuid.uuid4(),
                document_version_id=version_id,
                page_number=parsed_page.page_number,
                source_type=source_type,
                ocr_confidence=ocr_confidence,
                raw_text=raw_text,
            )
            db.add(page)
            pages_text[parsed_page.page_number] = raw_text

        # 7. PageIndex structure understanding
        logger.info("Stage: STRUCTURE_EXTRACTION via PageIndex")
        sections: List[MappedSection] = []
        try:
            adapter = get_pageindex_adapter()
            pi_result = adapter.process_document(file_path)
            if pi_result.success and pi_result.tree:
                sections = map_tree_to_sections(pi_result.tree, parsed.page_count)
                # Use PageIndex page texts if richer than PyMuPDF
                for page_idx, pi_text in pi_result.page_texts.items():
                    page_num = page_idx + 1
                    if pi_text and len(pi_text) > len(pages_text.get(page_num, "")):
                        pages_text[page_num] = pi_text
            else:
                logger.warning(
                    "PageIndex processing failed or returned empty tree: %s",
                    pi_result.error,
                )
        except Exception as e:
            logger.warning("PageIndex unavailable, using fallback structure: %s", e)

        # 8. Save Section records
        for ms in sections:
            section = Section(
                id=ms.id,
                document_version_id=version_id,
                parent_section_id=ms.parent_id,
                level=ms.level,
                title=ms.title,
                page_start=ms.page_start,
                page_end=ms.page_end,
                section_path=ms.section_path,
            )
            db.add(section)

        # 9. Save Table records
        tables_text: Dict[int, List[str]] = {}
        for dt in parsed.tables:
            table = Table(
                id=uuid.uuid4(),
                document_version_id=version_id,
                page_number=dt.page_number,
                row_count=dt.row_count,
                col_count=dt.col_count,
                header_row=dt.header_row,
                raw_cells=dt.raw_cells,
            )
            db.add(table)

            # Create text representation for table chunking
            table_text = _table_to_text(dt.header_row, dt.raw_cells)
            tables_text.setdefault(dt.page_number, []).append(table_text)

        # 10. Structure-aware chunking
        logger.info("Stage: CHUNKING")
        chunk_records = chunk_document(pages_text, sections, tables_text)

        # 11. Save Chunk records to PostgreSQL
        for cr in chunk_records:
            chunk = Chunk(
                id=cr.id,
                document_id=doc_id,
                document_version_id=version_id,
                org_id=uuid.UUID(org_id),
                workspace_id=uuid.UUID(workspace_id),
                page_start=cr.page_start,
                page_end=cr.page_end,
                section_id=cr.section_id,
                section_path=cr.section_path,
                chunk_type=cr.chunk_type,
                text=cr.text,
                content_hash=cr.content_hash,
                char_offset_start=cr.char_offset_start,
                char_offset_end=cr.char_offset_end,
                embedding_model=get_model_name(),
            )
            db.add(chunk)

        # 12. Generate embeddings
        logger.info("Stage: EMBEDDING %d chunks", len(chunk_records))
        texts = [cr.text for cr in chunk_records]
        vectors = embed_texts(texts)

        # 13. Ensure Qdrant collection and upsert
        logger.info("Stage: INDEXING in Qdrant")
        vector_dim = get_embedding_dimension()
        ensure_collection(vector_dim)

        chunk_ids = [str(cr.id) for cr in chunk_records]
        payloads = [
            {
                "chunk_id": str(cr.id),
                "document_id": str(doc_id),
                "document_name": filename,
                "org_id": org_id,
                "workspace_id": workspace_id,
                "page_start": cr.page_start,
                "page_end": cr.page_end,
                "section_path": cr.section_path or "",
                "chunk_type": cr.chunk_type,
                "text": cr.text[:500],  # Store truncated text in payload
            }
            for cr in chunk_records
        ]
        upsert_chunks(chunk_ids, vectors, payloads)

        # 14. Update job status
        job.overall_status = "READY"
        await db.flush()

        logger.info(
            "Document ingestion complete: %s (%d pages, %d sections, %d chunks)",
            filename, parsed.page_count, len(sections), len(chunk_records),
        )

        return {
            "document_id": str(doc_id),
            "document_version_id": str(version_id),
            "job_id": str(job_id),
            "status": "READY",
        }

    except Exception as e:
        logger.error("Document ingestion failed: %s", e)
        job.overall_status = "FAILED"
        job.stages = [{"stage": "PROCESSING", "error_message": str(e)}]
        await db.flush()
        raise


def _table_to_text(
    header_row: Optional[List[str]], raw_cells: List[List[str]]
) -> str:
    """Convert table data to a text representation for chunking."""
    lines = []
    if header_row:
        lines.append(" | ".join(header_row))
        lines.append("-" * 40)
    for row in raw_cells:
        if row != header_row:  # Skip header duplication
            lines.append(" | ".join(str(c) for c in row))
    return "\n".join(lines)


async def process_document_pipeline(
    session: AsyncSession,
    job_id: uuid.UUID,
    document_id: uuid.UUID,
    document_version_id: uuid.UUID,
    file_path: str,
) -> None:
    """Worker task wrapper for document processing pipeline."""
    if not os.path.exists(file_path):
        logger.error("File not found for async processing: %s", file_path)
        return

    with open(file_path, "rb") as f:
        file_data = f.read()

    # Query document version to get metadata
    res = await session.execute(select(DocumentVersion).where(DocumentVersion.id == document_version_id))
    version = res.scalar_one_or_none()
    if not version:
        logger.error("Document version %s not found", document_version_id)
        return

    doc_res = await session.execute(select(Document).where(Document.id == document_id))
    doc = doc_res.scalar_one_or_none()
    if not doc:
        logger.error("Document %s not found", document_id)
        return

    # Ingest document processing logic (multi-format via parser factory)
    declared_mime = version.declared_mime_type or "application/pdf"
    parsed = parse_document(file_path, declared_mime, doc.filename)
    version.page_count = parsed.page_count
    version.detected_type = parsed.detected_type

    pages_text: Dict[int, str] = {}
    _is_image_mime = declared_mime.startswith("image/")
    for parsed_page in parsed.pages:
        if parsed_page.source_type == "scanned":
            if _is_image_mime:
                ocr_result = ocr_page_image(file_path)
            else:
                ocr_result = ocr_pdf_page(file_path, parsed_page.page_number)
            source_type = ocr_result.source_type
            ocr_confidence = ocr_result.ocr_confidence
            raw_text = ocr_result.raw_text or parsed_page.raw_text
        else:
            source_type = "native"
            ocr_confidence = None
            raw_text = parsed_page.raw_text

        page = Page(
            id=uuid.uuid4(),
            document_version_id=document_version_id,
            page_number=parsed_page.page_number,
            source_type=source_type,
            ocr_confidence=ocr_confidence,
            raw_text=raw_text,
        )
        session.add(page)
        pages_text[parsed_page.page_number] = raw_text

    sections: List[MappedSection] = []
    try:
        adapter = get_pageindex_adapter()
        pi_result = adapter.process_document(file_path)
        if pi_result.success and pi_result.tree:
            sections = map_tree_to_sections(pi_result.tree, parsed.page_count)
            for page_idx, pi_text in pi_result.page_texts.items():
                page_num = page_idx + 1
                if pi_text and len(pi_text) > len(pages_text.get(page_num, "")):
                    pages_text[page_num] = pi_text
    except Exception as e:
        logger.warning("PageIndex error in async pipeline: %s", e)

    for ms in sections:
        sec = Section(
            id=ms.id,
            document_version_id=document_version_id,
            parent_section_id=ms.parent_id,
            level=ms.level,
            title=ms.title,
            page_start=ms.page_start,
            page_end=ms.page_end,
            section_path=ms.section_path,
        )
        session.add(sec)

    tables_text: Dict[int, List[str]] = {}
    for dt in parsed.tables:
        t = Table(
            id=uuid.uuid4(),
            document_version_id=document_version_id,
            page_number=dt.page_number,
            row_count=dt.row_count,
            col_count=dt.col_count,
            header_row=dt.header_row,
            raw_cells=dt.raw_cells,
        )
        session.add(t)
        tables_text.setdefault(dt.page_number, []).append(_table_to_text(dt.header_row, dt.raw_cells))

    chunk_records = chunk_document(pages_text, sections, tables_text)

    for cr in chunk_records:
        chunk = Chunk(
            id=cr.id,
            document_id=document_id,
            document_version_id=document_version_id,
            org_id=doc.org_id,
            workspace_id=doc.workspace_id,
            page_start=cr.page_start,
            page_end=cr.page_end,
            section_id=cr.section_id,
            section_path=cr.section_path,
            chunk_type=cr.chunk_type,
            text=cr.text,
            content_hash=cr.content_hash,
            char_offset_start=cr.char_offset_start,
            char_offset_end=cr.char_offset_end,
            embedding_model=get_model_name(),
        )
        session.add(chunk)

    texts = [cr.text for cr in chunk_records]
    vectors = embed_texts(texts)

    vector_dim = get_embedding_dimension()
    ensure_collection(vector_dim)

    chunk_ids = [str(cr.id) for cr in chunk_records]
    payloads = [
        {
            "chunk_id": str(cr.id),
            "document_id": str(document_id),
            "org_id": str(doc.org_id),
            "workspace_id": str(doc.workspace_id),
            "page_start": cr.page_start,
            "page_end": cr.page_end,
            "section_path": cr.section_path or "",
            "chunk_type": cr.chunk_type,
            "text": cr.text[:500],
        }
        for cr in chunk_records
    ]
    upsert_chunks(chunk_ids, vectors, payloads)

