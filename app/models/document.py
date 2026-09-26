"""
Document, DocumentVersion, and DocumentMetadata ORM models.
Per docs/09_DATA_MODELS.md §1-3.
"""
from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Top-level document record, mirrors a subset of Express's document record."""

    __tablename__ = "documents"

    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    workspace_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    folder_id = Column(UUID(as_uuid=True), ForeignKey("collections.id"), nullable=True)
    filename = Column(String(512), nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    current_version_id = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    collection = relationship("Collection", back_populates="documents")
    versions = relationship(
        "DocumentVersion", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentVersion(Base, UUIDPrimaryKeyMixin):
    """Version of a document, each with its own processing pipeline run."""

    __tablename__ = "document_versions"

    document_id = Column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    version_number = Column(Integer, nullable=False, default=1)
    file_ref = Column(String(1024), nullable=False)  # object storage key
    declared_mime_type = Column(String(128), nullable=False)
    detected_type = Column(
        String(32), nullable=True
    )  # digital_pdf, scanned_pdf, docx, xlsx, csv, image
    page_count = Column(Integer, nullable=True)
    uploaded_by_user_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    # Relationships
    document = relationship("Document", back_populates="versions")
    pages = relationship(
        "Page", back_populates="document_version", cascade="all, delete-orphan"
    )
    sections = relationship(
        "Section", back_populates="document_version", cascade="all, delete-orphan"
    )
    tables = relationship(
        "Table", back_populates="document_version", cascade="all, delete-orphan"
    )
    metadata_record = relationship(
        "DocumentMetadata",
        back_populates="document_version",
        uselist=False,
        cascade="all, delete-orphan",
    )


class DocumentMetadata(Base, UUIDPrimaryKeyMixin):
    """Extracted document-level metadata."""

    __tablename__ = "document_metadata"

    document_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id"),
        nullable=False,
        unique=True,
    )
    title = Column(String(512), nullable=True)
    document_type = Column(String(128), nullable=True)
    detected_dates = Column(ARRAY(String), default=list)
    detected_subsidiary_names = Column(ARRAY(String), default=list)
    detected_mine_names = Column(ARRAY(String), default=list)
    language = Column(String(16), nullable=True)

    # Relationships
    document_version = relationship("DocumentVersion", back_populates="metadata_record")
