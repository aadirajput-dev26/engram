"""
Unit tests for Table Parser.
Per docs/06_STRUCTURED_DATA_EXTRACTION.md §3.1.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from app.domain.extraction.table_parser import (
    TableParser,
    normalize_unit,
    parse_numeric_value,
    parse_period,
)


def test_parse_period():
    assert parse_period("2023") == ("year", "2023")
    assert parse_period("FY2023-24") == ("fiscal_year", "FY2023-24")
    assert parse_period("2022-23") == ("fiscal_year", "FY2022-23")
    assert parse_period("Q1 2024") == ("quarter", "Q1 2024")


def test_parse_numeric_value():
    assert parse_numeric_value("1,234.56") == Decimal("1234.56")
    assert parse_numeric_value("(50.2)") == Decimal("-50.2")
    assert parse_numeric_value("85.5%") == Decimal("85.5")
    assert parse_numeric_value("-") is None
    assert parse_numeric_value("N/A") is None


def test_normalize_unit():
    assert normalize_unit("MT") == ("MT", "MT")
    assert normalize_unit("Million Tonnes") == ("Million Tonnes", "MT")
    assert normalize_unit("tonnes") == ("tonnes", "tonnes")


def test_table_parsing_pipeline():
    parser = TableParser()
    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()

    table_data = [
        ["Subsidiary", "Target (MT)", "Production (MT)", "Achievement (%)"],
        ["NCL", "130.00", "131.50", "101.15%"],
        ["ECL", "45.00", "42.30", "94.00%"],
    ]

    facts = parser.parse_table(
        table_data=table_data,
        document_id=doc_id,
        document_version_id=ver_id,
        page_number=4,
        section_path="2 > 2.1",
        ocr_confidence=1.0,
    )

    assert len(facts) >= 4
    # Check NCL production fact
    ncl_prod = next(
        f for f in facts
        if f["subsidiary_name"] == "Northern Coalfields Limited" and f["metric"] == "production"
    )
    assert ncl_prod["value"] == Decimal("131.50")
    assert ncl_prod["unit_normalized"] == "MT"
    assert ncl_prod["extraction_method"] == "table_parser"
