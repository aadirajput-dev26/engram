"""
Unit tests for Query Router and Classifier.
Per docs/07_AI_QUERY_ENGINE.md §3 golden test cases.
"""
from __future__ import annotations

from app.core.query_router.classifier import (
    classify_query,
    extract_query_parameters,
    get_query_classification,
)


def test_golden_case_structured():
    """Golden case 1: 'What was coal production in 2023?' -> STRUCTURED"""
    query = "What was coal production in 2023?"
    route = classify_query(query)
    assert route == "structured"

    classification = get_query_classification(query)
    assert classification.route == "structured"
    assert "production" in classification.metrics
    assert "2023" in classification.periods


def test_golden_case_rag():
    """Golden case 2: 'Why did production decline in 2023?' -> RAG"""
    query = "Why did production decline in 2023?"
    route = classify_query(query)
    assert route == "rag"

    classification = get_query_classification(query)
    assert classification.route == "rag"


def test_golden_case_hybrid():
    """Golden case 3: 'Compare production decline with the operational reasons mentioned in reports.' -> HYBRID"""
    query = "Compare production decline with the operational reasons mentioned in reports."
    route = classify_query(query)
    assert route == "hybrid"

    classification = get_query_classification(query)
    assert classification.route == "hybrid"
    assert classification.comparison is True


def test_subsidiary_extraction():
    query = "What was the dispatch from NCL and BCCL in FY2023-24?"
    params = extract_query_parameters(query)
    assert "Northern Coalfields Limited" in params["subsidiaries"]
    assert "Bharat Coking Coal Limited" in params["subsidiaries"]
    assert "dispatch" in params["metrics"]
    assert "FY2023-24" in params["periods"]
