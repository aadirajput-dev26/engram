"""
Section ORM model (hierarchical document structure).
Per docs/09_DATA_MODELS.md §6.
"""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, UUIDPrimaryKeyMixin


class Section(Base, UUIDPrimaryKeyMixin):
    """Hierarchical section of a document, built from PageIndex structure tree."""

    __tablename__ = "sections"

    document_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id"),
        nullable=False,
        index=True,
    )
    parent_section_id = Column(
        UUID(as_uuid=True), ForeignKey("sections.id"), nullable=True
    )
    level = Column(Integer, nullable=False, default=0)
    title = Column(String(512), nullable=True)
    page_start = Column(Integer, nullable=False)
    page_end = Column(Integer, nullable=False)
    section_path = Column(String(256), nullable=True)  # e.g. "3 > 3.2"

    # Self-referential relationship for tree hierarchy
    parent = relationship("Section", remote_side="Section.id", backref="children")
    document_version = relationship("DocumentVersion", back_populates="sections")
