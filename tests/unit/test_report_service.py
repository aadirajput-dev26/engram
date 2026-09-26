"""
Unit tests for Report Generation Service.
Per docs/12_REPORT_GENERATION.md.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.domain.reports.report_service import (
    SECTION_TEMPLATES,
    _render_docx,
    generate_report_draft,
)
from app.schemas.report import ReportSection


def test_render_docx_creates_file(tmp_path: Path):
    output_path = tmp_path / "test_report.docx"
    sections = [
        ReportSection(
            heading="1. Production Overview",
            content="Total coal production reached 131.5 MT in FY2023-24.",
            citations=[],
        )
    ]
    rendered = _render_docx(
        title="Test Production Report",
        sections=sections,
        output_path=output_path,
    )
    assert os.path.exists(rendered)
    assert os.path.getsize(rendered) > 0


@pytest.mark.asyncio
@patch("app.domain.reports.report_service.process_query", new_callable=AsyncMock)
async def test_generate_report_draft(mock_process_query):
    mock_process_query.return_value = {
        "answer": "Raw coal production reached 131.5 MT against target of 130 MT [F1].",
        "route_used": "hybrid",
        "no_evidence": False,
        "citations": [
            {
                "citation_id": "F1",
                "source_type": "fact",
                "document_id": str(uuid4()),
                "document_name": "Report_FY24.pdf",
                "page_number": 5,
                "section_path": "1 > 1.2",
            }
        ],
    }

    mock_db = AsyncMock()
    job_id = uuid4()
    org_id = uuid4()
    ws_id = uuid4()

    draft = await generate_report_draft(
        db=mock_db,
        job_id=job_id,
        org_id=org_id,
        workspace_id=ws_id,
        report_type="production_summary",
        parameters={"subsidiary_name": "NCL", "fiscal_year": "FY2023-24"},
    )

    assert draft.job_id == job_id
    assert draft.status in ("READY", "PARTIAL")
    assert len(draft.sections) == len(SECTION_TEMPLATES["production_summary"])
    assert "131.5 MT" in draft.sections[0].content
