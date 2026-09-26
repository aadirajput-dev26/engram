"""
Unit tests for structure-aware chunking.
Per docs/04_DOCUMENT_PROCESSING_SPEC.md §7.
"""
from __future__ import annotations

import uuid

from app.core.chunking.structure_aware import chunk_document
from app.core.pageindex.mapper import MappedSection


def test_chunking_respects_section_boundaries():
    sec1 = MappedSection(
        id=uuid.uuid4(),
        parent_id=None,
        title="Geological Setting",
        page_start=1,
        page_end=1,
        section_path="1",
        level=1,
    )
    sec2 = MappedSection(
        id=uuid.uuid4(),
        parent_id=None,
        title="Mining Methodology",
        page_start=2,
        page_end=2,
        section_path="2",
        level=1,
    )

    pages_text = {
        1: "The Gondwana basin is composed of sandstone and coal seams.",
        2: "Continuous miners are deployed in underground panels.",
    }
    tables_text = {}

    chunks = chunk_document(
        pages_text=pages_text,
        sections=[sec1, sec2],
        tables_text=tables_text,
    )

    assert len(chunks) == 2
    # Check that chunks belong to their respective sections
    assert chunks[0].section_path == "1"
    assert "Gondwana" in chunks[0].text
    assert chunks[1].section_path == "2"
    assert "Continuous miners" in chunks[1].text


def test_table_chunks_isolated():
    pages_text = {1: "Some intro text."}
    tables_text = {1: ["| Col1 | Col2 |\n|---|---|\n| A | 10 |"]}

    chunks = chunk_document(
        pages_text=pages_text,
        sections=[],
        tables_text=tables_text,
    )

    table_chunks = [c for c in chunks if c.chunk_type == "table"]
    assert len(table_chunks) == 1
    assert "Col1" in table_chunks[0].text
