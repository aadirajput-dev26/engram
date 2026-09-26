"""
Unit tests for regex narrative statement extractor.
Per docs/06_STRUCTURED_DATA_EXTRACTION.md §3.2.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from app.domain.extraction.regex_extractor import RegexExtractor


def test_regex_extract_narrative_statement():
    extractor = RegexExtractor()
    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()

    text = (
        "Northern Coalfields Limited produced 131.50 MT of raw coal during FY2023-24. "
        "The subsidiary maintained consistent dispatch throughout the year."
    )

    facts = extractor.extract_from_text(
        text=text,
        document_id=doc_id,
        document_version_id=ver_id,
        page_number=2,
    )

    assert len(facts) >= 1
    fact = facts[0]
    assert fact["subsidiary_name"] == "Northern Coalfields Limited"
    assert fact["value"] == Decimal("131.50")
    assert fact["period_value"] == "FY2023-24"
    assert fact["metric"] == "production"
    assert fact["extraction_method"] == "regex"
