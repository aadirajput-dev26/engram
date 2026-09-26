"""
ProcessingJob and JobTask ORM models.
Per docs/09_DATA_MODELS.md §4 and docs/14_ASYNC_PROCESSING.md.
"""
from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, text as sa_text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProcessingJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Tracks the processing lifecycle of a document version.
    stages is a JSON array of ProcessingStageStatus objects.
    """

    __tablename__ = "processing_jobs"

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
    overall_status = Column(String(32), nullable=False, default="QUEUED")
    stages = Column(JSONB, nullable=False, default=list)
    created_by_user_id = Column(UUID(as_uuid=True), nullable=False)


class JobTask(Base, UUIDPrimaryKeyMixin):
    """
    Queue item for asynchronous workers using PostgreSQL SELECT ... FOR UPDATE SKIP LOCKED.
    Per docs/14_ASYNC_PROCESSING.md §2-3.
    """

    __tablename__ = "job_tasks"

    job_id = Column(UUID(as_uuid=True), ForeignKey("processing_jobs.id"), nullable=True, index=True)
    task_type = Column(String(64), nullable=False, index=True)
    payload = Column(JSONB, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="PENDING", index=True)  # PENDING | CLAIMED | COMPLETED | FAILED
    priority = Column(Integer, nullable=False, default=0, index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    error_message = Column(Text, nullable=True)
    claimed_by = Column(String(128), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=sa_text("now()"),
        nullable=False,
    )
