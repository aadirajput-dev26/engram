# app/models/__init__.py
"""SQLAlchemy ORM models for the AI Document Intelligence service."""

from app.models.collection import Collection
from app.models.document import Document, DocumentMetadata, DocumentVersion
from app.models.page import Page
from app.models.section import Section
from app.models.table import Table
from app.models.chunk import Chunk
from app.models.job import JobTask, ProcessingJob

# Auth / tenant models — imported last so FKs resolve correctly
from app.models.organization import Organization
from app.models.workspace import Workspace
from app.models.user import User
from app.models.api_key import ApiKey

__all__ = [
    "Collection",
    "Document",
    "DocumentVersion",
    "DocumentMetadata",
    "Page",
    "Section",
    "Table",
    "Chunk",
    "ProcessingJob",
    "JobTask",
    # Auth
    "Organization",
    "Workspace",
    "User",
    "ApiKey",
]
