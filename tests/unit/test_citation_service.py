"""
Unit tests for citation formatting service.
Per docs/09_DATA_MODELS.md §11.
"""
from __future__ import annotations

import uuid

from app.core.validation.citation_service import build_citations


def test_build_citations_from_chunks_and_facts():
    doc_id = str(uuid.uuid4())
    chunk_id = str(uuid.uuid4())
    fact_id = str(uuid.uuid4())

    evidence_chunks = [
        {
            "chunk_id": chunk_id,
            "document_id": doc_id,
            "document_name": "Annual_Report_2023.pdf",
            "page_start": 15,
            "section_path": "3 > 3.1",
            "text": "Production details...",
        }
    ]

    evidence_facts = [
        {
            "id": fact_id,
            "document_id": doc_id,
            "document_name": "Annual_Report_2023.pdf",
            "page_number": 12,
            "section_path": "2 > 2.4",
            "metric": "production",
            "value": 131.5,
        }
    ]

    answer = "The subsidiary achieved 131.5 MT [F1] despite flooding in monsoon [C1]."

    citations = build_citations(
        answer=answer,
        evidence_chunks=evidence_chunks,
        evidence_facts=evidence_facts,
    )

    assert len(citations) == 2
    cit_map = {c["citation_id"]: c for c in citations}

    assert cit_map["C1"]["source_type"] == "chunk"
    assert cit_map["C1"]["page_number"] == 15
    assert cit_map["C1"]["document_name"] == "Annual_Report_2023.pdf"

    assert cit_map["F1"]["source_type"] == "fact"
    assert cit_map["F1"]["page_number"] == 12
    assert cit_map["F1"]["fact_id"] == fact_id
