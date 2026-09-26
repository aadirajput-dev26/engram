"""
Chunk ORM model — metadata in PostgreSQL, vector in Qdrant.
Per docs/09_DATA_MODELS.md §8.
"""
from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, text as sa_text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Chunk(Base, UUIDPrimaryKeyMixin):
    """
    Text chunk of a document for retrieval.
    Metadata stored here; embedding vector stored in Qdrant keyed by the same id.
    The tsv column provides PostgreSQL full-text search via a GIN index.
    """

    __tablename__ = "chunks"

    document_id = Column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    document_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id"),
        nullable=False,
        index=True,
    )
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    workspace_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    page_start = Column(Integer, nullable=False)
    page_end = Column(Integer, nullable=False)
    section_id = Column(UUID(as_uuid=True), ForeignKey("sections.id"), nullable=True)
    section_path = Column(String(256), nullable=True)
    chunk_type = Column(
        String(32), nullable=False, default="paragraph"
    )  # paragraph | table | heading_context
    text = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    char_offset_start = Column(Integer, nullable=False, default=0)
    char_offset_end = Column(Integer, nullable=False, default=0)
    embedding_model = Column(String(128), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=sa_text("now()"),
        nullable=False,
    )

    # Note: The TSVECTOR column and GIN index are created via raw SQL in the
    # Alembic migration since SQLAlchemy doesn't natively support generated
    # tsvector columns. The column name is 'tsv'.
    # See alembic/versions/ for the migration.

    # Relationships
    document = relationship("Document")
    document_version = relationship("DocumentVersion")
    section = relationship("Section")
