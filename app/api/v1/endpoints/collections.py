"""
Collections (Folders) API endpoints.
"""
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security.auth import require_api_key
from app.db.session import get_db
from app.schemas.collection import CollectionCreate, CollectionResponse, CollectionUpdate
from app.services import collection_service

logger = get_logger("endpoint_collections")
router = APIRouter(prefix="/collections", tags=["collections"])


@router.post("", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    request: CollectionCreate,
    org_id: str,
    workspace_id: str,
    _key: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> CollectionResponse:
    """Create a new collection for a given organization and workspace."""
    collection = await collection_service.create_collection(
        db=db,
        org_id=org_id,
        workspace_id=workspace_id,
        data=request,
    )
    return collection


@router.get("", response_model=List[CollectionResponse])
async def list_collections(
    org_id: str,
    workspace_id: str,
    _key: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> List[CollectionResponse]:
    """List all collections for a given organization and workspace."""
    collections = await collection_service.list_collections(
        db=db, org_id=org_id, workspace_id=workspace_id
    )
    return collections


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: UUID,
    org_id: str,
    workspace_id: str,
    _key: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> CollectionResponse:
    """Get details of a specific collection."""
    collection = await collection_service.get_collection(
        db=db, collection_id=collection_id, org_id=org_id, workspace_id=workspace_id
    )
    return collection


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: UUID,
    request: CollectionUpdate,
    org_id: str,
    workspace_id: str,
    _key: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> CollectionResponse:
    """Update a specific collection."""
    collection = await collection_service.update_collection(
        db=db, collection_id=collection_id, org_id=org_id, workspace_id=workspace_id, data=request
    )
    return collection


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: UUID,
    org_id: str,
    workspace_id: str,
    _key: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Delete a specific collection."""
    await collection_service.delete_collection(
        db=db, collection_id=collection_id, org_id=org_id, workspace_id=workspace_id
    )
