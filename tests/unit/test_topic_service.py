"""
Unit tests for topic identification and keyword extraction.
Per docs/13_TOPIC_ANALYSIS.md.
"""
from __future__ import annotations

import uuid

from app.domain.topics.topic_service import (
    compute_tfidf_keywords,
    extract_domain_entities,
    extract_topic_clusters,
)


def test_tfidf_keywords_extraction():
    corpus = [
        "Northern Coalfields Limited achieved record coal production of 130 MT.",
        "Production at Nigahi mine increased due to deployment of new electric shovels.",
        "Overburden removal target was exceeded in Jayant opencast project.",
    ]
    keywords = compute_tfidf_keywords(corpus, top_k=5)
    assert len(keywords) > 0
    terms = [k.term for k in keywords]
    assert any(t in terms for t in ["production", "coal", "nigahi", "jayant", "overburden"])


def test_domain_entity_extraction():
    corpus = [
        "NCL and BCCL are major coal producing subsidiaries of Coal India.",
        "Operations in Singrauli coalfield region continued at full capacity.",
    ]
    entities = extract_domain_entities(corpus)
    texts = [e["text"] for e in entities]
    assert "Northern Coalfields Limited" in texts
    assert "Bharat Coking Coal Limited" in texts
    assert "Singrauli" in texts


def test_topic_clustering():
    doc1_id = uuid.uuid4()
    doc2_id = uuid.uuid4()
    corpus = [
        {"text": "Coal production, annual target and overburden removal.", "document_id": doc1_id},
        {"text": "Mine safety audit, zero accident protocol and environmental compliance.", "document_id": doc2_id},
    ]
    topics = extract_topic_clusters(corpus, num_topics=3)
    labels = [t.label for t in topics]
    assert any("Production" in l for l in labels)
    assert any("Safety" in l for l in labels)
