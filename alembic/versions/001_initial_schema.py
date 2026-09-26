"""Initial schema for AI document intelligence microservice

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-20 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("folder_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filename", sa.String(256), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False, index=True),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 2. Document Versions
    op.create_table(
        "document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("file_ref", sa.String(512), nullable=False),
        sa.Column("declared_mime_type", sa.String(128), nullable=False),
        sa.Column("detected_type", sa.String(64), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 3. Document Metadata
    op.create_table(
        "document_metadata",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("document_type", sa.String(128), nullable=True),
        sa.Column("detected_dates", postgresql.JSONB(), nullable=False, default=list),
        sa.Column("detected_subsidiary_names", postgresql.JSONB(), nullable=False, default=list),
        sa.Column("detected_mine_names", postgresql.JSONB(), nullable=False, default=list),
        sa.Column("language", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 4. Pages
    op.create_table(
        "pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False, default="native"),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 5. Sections
    op.create_table(
        "sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("parent_section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sections.id"), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False, default=1),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("section_path", sa.String(256), nullable=False, index=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 6. Tables
    op.create_table(
        "tables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sections.id"), nullable=True),
        sa.Column("section_path", sa.String(256), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False, default=0),
        sa.Column("col_count", sa.Integer(), nullable=False, default=0),
        sa.Column("header_row", postgresql.JSONB(), nullable=True),
        sa.Column("raw_cells", postgresql.JSONB(), nullable=False, default=list),
        sa.Column("structure", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 7. Chunks
    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sections.id"), nullable=True),
        sa.Column("section_path", sa.String(256), nullable=True),
        sa.Column("chunk_type", sa.String(32), nullable=False, default="paragraph"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False, index=True),
        sa.Column("char_offset_start", sa.Integer(), nullable=False, default=0),
        sa.Column("char_offset_end", sa.Integer(), nullable=False, default=0),
        sa.Column("embedding_model", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Add TSVECTOR generated column and GIN index for PostgreSQL FTS
    op.execute(
        """
        ALTER TABLE chunks
        ADD COLUMN tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('english', text)) STORED;
        """
    )
    op.execute("CREATE INDEX ix_chunks_tsv ON chunks USING gin(tsv);")

    # 8. Extracted Facts
    op.create_table(
        "extracted_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("section_path", sa.String(256), nullable=True),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tables.id"), nullable=True),
        sa.Column("metric", sa.String(256), nullable=False, index=True),
        sa.Column("metric_raw_label", sa.String(512), nullable=True),
        sa.Column("value", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("unit", sa.String(64), nullable=False),
        sa.Column("unit_normalized", sa.String(64), nullable=True),
        sa.Column("mine_name", sa.String(256), nullable=True, index=True),
        sa.Column("subsidiary_name", sa.String(256), nullable=True, index=True),
        sa.Column("coal_grade", sa.String(64), nullable=True),
        sa.Column("period_type", sa.String(32), nullable=False),
        sa.Column("period_value", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, default=1.0),
        sa.Column("extraction_method", sa.String(32), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("validation_flag", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 9. Processing Jobs
    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("overall_status", sa.String(32), nullable=False, default="QUEUED"),
        sa.Column("stages", postgresql.JSONB(), nullable=False, default=list),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 10. Job Tasks
    op.create_table(
        "job_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("processing_jobs.id"), nullable=True, index=True),
        sa.Column("task_type", sa.String(64), nullable=False, index=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, default=dict),
        sa.Column("status", sa.String(32), nullable=False, default="PENDING", index=True),
        sa.Column("priority", sa.Integer(), nullable=False, default=0, index=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, default=0),
        sa.Column("max_retries", sa.Integer(), nullable=False, default=3),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("claimed_by", sa.String(128), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 11. Topic Results
    op.create_table(
        "topic_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True, index=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("status", sa.String(32), nullable=False, default="PROCESSING"),
        sa.Column("keywords", postgresql.JSONB(), nullable=False, default=list),
        sa.Column("topics", postgresql.JSONB(), nullable=False, default=list),
        sa.Column("word_cloud_data", postgresql.JSONB(), nullable=False, default=list),
        sa.Column("entities", postgresql.JSONB(), nullable=False, default=list),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 12. Report Drafts
    op.create_table(
        "report_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True, index=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("report_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("sections", postgresql.JSONB(), nullable=False, default=list),
        sa.Column("file_ref", sa.String(512), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, default="DRAFTING"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("report_drafts")
    op.drop_table("topic_results")
    op.drop_table("job_tasks")
    op.drop_table("processing_jobs")
    op.drop_table("extracted_facts")
    op.drop_table("chunks")
    op.drop_table("tables")
    op.drop_table("sections")
    op.drop_table("pages")
    op.drop_table("document_metadata")
    op.drop_table("document_versions")
    op.drop_table("documents")
