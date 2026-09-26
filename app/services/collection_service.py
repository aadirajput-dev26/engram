"""
Service layer for managing Collections (Folders).
"""
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collection import Collection
from app.schemas.collection import CollectionCreate, CollectionUpdate


async def create_collection(
    db: AsyncSession,
    org_id: str,
    workspace_id: str,
    data: CollectionCreate,
) -> Collection:
    """Create a new collection."""
    db_collection = Collection(
        org_id=UUID(org_id),
        workspace_id=UUID(workspace_id),
        name=data.name,
        description=data.description,
    )
    db.add(db_collection)
    await db.commit()
    await db.refresh(db_collection)
    return db_collection


async def get_collection(
    db: AsyncSession,
    collection_id: UUID,
    org_id: str,
    workspace_id: str,
) -> Collection:
    """Retrieve a single collection by ID."""
    stmt = select(Collection).where(
        Collection.id == collection_id,
        Collection.org_id == UUID(org_id),
        Collection.workspace_id == UUID(workspace_id),
    )
    res = await db.execute(stmt)
    collection = res.scalar_one_or_none()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )
    return collection


async def list_collections(
    db: AsyncSession,
    org_id: str,
    workspace_id: str,
) -> List[Collection]:
    """List all collections for a workspace."""
    stmt = select(Collection).where(
        Collection.org_id == UUID(org_id),
        Collection.workspace_id == UUID(workspace_id),
    ).order_by(Collection.created_at.desc())
    
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def update_collection(
    db: AsyncSession,
    collection_id: UUID,
    org_id: str,
    workspace_id: str,
    data: CollectionUpdate,
) -> Collection:
    """Update a collection."""
    collection = await get_collection(db, collection_id, org_id, workspace_id)
    
    if data.name is not None:
        collection.name = data.name
    if data.description is not None:
        collection.description = data.description
        
    await db.commit()
    await db.refresh(collection)
    return collection


async def delete_collection(
    db: AsyncSession,
    collection_id: UUID,
    org_id: str,
    workspace_id: str,
) -> None:
    """Delete a collection."""
    collection = await get_collection(db, collection_id, org_id, workspace_id)
    await db.delete(collection)
    await db.commit()
