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
from app.schemas.query import QueryRequest, QueryResponse
from app.services.query_service import process_query

logger = get_logger(__name__)

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    _key: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """AI-powered query with full RAG pipeline."""
    # org_id / workspace_id / document_ids come from request.scope — Express supplies correct tenant values
    document_ids = [str(d) for d in request.scope.document_ids] if request.scope.document_ids else None

    result = await process_query(
        db=db,
        query_text=request.query_text,
        org_id=str(request.scope.org_id),
        workspace_id=str(request.scope.workspace_id),
        document_ids=document_ids,
        top_k=request.top_k,
        route_override=request.route_override,
    )

    return QueryResponse(**result)
