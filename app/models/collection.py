"""
Collection (Folder) ORM model.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Collection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A logical grouping of documents (folder/collection)."""

    __tablename__ = "collections"

    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    workspace_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Relationships
    documents = relationship("Document", back_populates="collection")
