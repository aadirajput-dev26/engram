"""
Page ORM model.
Per docs/09_DATA_MODELS.md §5.
"""
from __future__ import annotations

from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, UUIDPrimaryKeyMixin


class Page(Base, UUIDPrimaryKeyMixin):
    """Represents a single page of a document version."""

    __tablename__ = "pages"

    document_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id"),
        nullable=False,
        index=True,
    )
    page_number = Column(Integer, nullable=False)
    source_type = Column(
        String(20), nullable=False, default="native"
    )  # native | ocr | ocr_unavailable
    ocr_confidence = Column(Float, nullable=True)
    raw_text = Column(Text, nullable=False, default="")

    # Relationships
    document_version = relationship("DocumentVersion", back_populates="pages")
