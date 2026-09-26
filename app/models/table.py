"""
Table ORM model.
Per docs/09_DATA_MODELS.md §7.
"""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID, VARCHAR
from sqlalchemy.orm import relationship

from app.db.base import Base, UUIDPrimaryKeyMixin


class Table(Base, UUIDPrimaryKeyMixin):
    """Detected table within a document page."""

    __tablename__ = "tables"

    document_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id"),
        nullable=False,
        index=True,
    )
    page_number = Column(Integer, nullable=False)
    section_id = Column(UUID(as_uuid=True), ForeignKey("sections.id"), nullable=True)
    row_count = Column(Integer, nullable=False, default=0)
    col_count = Column(Integer, nullable=False, default=0)
    header_row = Column(JSON, nullable=True)
    raw_cells = Column(JSON, nullable=True)  # list[list[str]]

    # Relationships
    document_version = relationship("DocumentVersion", back_populates="tables")
    section = relationship("Section")
