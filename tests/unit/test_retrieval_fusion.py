"""
Unit tests for Reciprocal Rank Fusion (RRF).
"""
from __future__ import annotations

from app.core.retrieval.fusion import reciprocal_rank_fusion


def test_rrf_scoring_and_deduplication():
    # Chunk A is rank 1 in semantic and rank 2 in keyword
    # Chunk B is rank 2 in semantic only
    # Chunk C is rank 1 in keyword only
    semantic_results = [
        {"chunk_id": "chunk-A", "document_id": "doc-1", "text": "Text A", "semantic_rank": 1, "semantic_score": 0.95},
        {"chunk_id": "chunk-B", "document_id": "doc-1", "text": "Text B", "semantic_rank": 2, "semantic_score": 0.85},
    ]

    keyword_results = [
        {"chunk_id": "chunk-C", "document_id": "doc-2", "text": "Text C", "keyword_rank": 1, "keyword_score": 0.90},
        {"chunk_id": "chunk-A", "document_id": "doc-1", "text": "Text A", "keyword_rank": 2, "keyword_score": 0.80},
    ]

    k = 60
    fused = reciprocal_rank_fusion(
        semantic_results=semantic_results,
        keyword_results=keyword_results,
        k=k,
        top_m=10,
    )

    assert len(fused) == 3
    # Chunk A should have the highest score because it appears in both rank lists:
    # 1/(60+1) + 1/(60+2) = 1/61 + 1/62
    expected_score_a = (1.0 / 61) + (1.0 / 62)
    assert fused[0]["chunk_id"] == "chunk-A"
    assert abs(fused[0]["rrf_score"] - expected_score_a) < 1e-6


def test_rrf_top_m_truncation():
    semantic_results = [
        {"chunk_id": f"chunk-{i}", "semantic_rank": i + 1, "text": f"Text {i}"}
        for i in range(20)
    ]
    keyword_results = []

    fused = reciprocal_rank_fusion(
        semantic_results=semantic_results,
        keyword_results=keyword_results,
        k=60,
        top_m=5,
    )
    assert len(fused) == 5
    assert fused[0]["chunk_id"] == "chunk-0"
