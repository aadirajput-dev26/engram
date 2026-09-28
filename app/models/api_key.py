"""
ApiKey ORM model.
Stores hashed sk-engram-* keys scoped to an org + workspace.
Plaintext key is NEVER stored — only SHA-256 hash and a short prefix for UI display.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ApiKey(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A scoped API key for programmatic access to the RAG service."""

    __tablename__ = "api_keys"

    # The organization this key grants access to
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    # The specific workspace this key is scoped to
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    # Who created this key
    created_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    name = Column(String(255), nullable=False)  # Human-readable label e.g. "Production Key"

    # SHA-256 hex digest of the full key — used for constant-time lookup
    key_hash = Column(String(64), nullable=False, unique=True, index=True)

    # First 20 chars of the key shown in UI so user can identify it (e.g. "sk-engram-xK9p...")
    key_prefix = Column(String(32), nullable=False)

    is_active = Column(Boolean, nullable=False, default=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="api_keys")
    workspace = relationship("Workspace", back_populates="api_keys")
    created_by_user = relationship("User", back_populates="api_keys")
