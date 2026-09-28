"""
Query endpoint.
Per docs/08_API_CONTRACTS.md §4.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security.auth import require_api_key
from app.db.session import get_db
from app.schemas.auth import TenantContext
from app.schemas.query import QueryRequest, QueryResponse
from app.services.query_service import process_query

logger = get_logger(__name__)

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    tenant: TenantContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """AI-powered query with full RAG pipeline. Tenant scope is resolved from the API key."""
    doc_ids_list = request.document_ids or (request.scope.document_ids if request.scope and request.scope.document_ids else None)
    document_ids = [str(d) for d in doc_ids_list] if doc_ids_list else None

    col_id = request.collection_id or (request.scope.collection_id if request.scope and request.scope.collection_id else None)
    collection_id = str(col_id) if col_id else None

    result = await process_query(
        db=db,
        query_text=request.query_text,
        org_id=str(tenant.org_id),
        workspace_id=str(tenant.workspace_id),
        document_ids=document_ids,
        collection_id=collection_id,
        top_k=request.top_k,
        route_override=request.route_override,
    )

    return QueryResponse(**result)
