"""
Workspace ORM model.
A workspace is a scoped sub-division within an organization.
Documents, collections, and API keys are all scoped to a workspace.
"""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Workspace(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A workspace within an organization."""

    __tablename__ = "workspaces"

    org_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="workspaces")
    api_keys = relationship("ApiKey", back_populates="workspace", cascade="all, delete-orphan")
