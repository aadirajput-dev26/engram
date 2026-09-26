"""
Pydantic schemas for Collection (Folder) operations.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CollectionBase(BaseModel):
    name: str = Field(..., max_length=255, description="Name of the collection")
    description: Optional[str] = Field(None, description="Optional description of the collection")


class CollectionCreate(CollectionBase):
    pass


class CollectionUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None


class CollectionResponse(CollectionBase):
    id: UUID
    org_id: UUID
    workspace_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
