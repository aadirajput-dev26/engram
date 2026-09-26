"""
Qdrant vector database service.
Manages collection creation, chunk upsertion, and semantic search
with mandatory tenant payload filtering.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client = None


def _get_client():
    """Get or create the Qdrant client."""
    global _client
    if _client is None:
        settings = get_settings()
        from qdrant_client import QdrantClient

        if settings.QDRANT_API_KEY:
            _client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
                check_compatibility=False,
            )
        else:
            _client = QdrantClient(url=settings.QDRANT_URL, check_compatibility=False)
        logger.info("Qdrant client initialized: %s", settings.QDRANT_URL)
    return _client


def ensure_collection(vector_size: int) -> None:
    """Create the Qdrant collection if it doesn't exist."""
    settings = get_settings()
    client = _get_client()
    collection_name = settings.QDRANT_COLLECTION_NAME

    from qdrant_client.models import Distance, VectorParams

    collections = client.get_collections().collections
    existing = [c.name for c in collections]

    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )
        logger.info(
            "Created Qdrant collection '%s' (dim=%d, cosine)",
            collection_name, vector_size,
        )
    else:
        logger.info("Qdrant collection '%s' already exists", collection_name)


def upsert_chunks(
    chunk_ids: List[str],
    vectors: List[List[float]],
    payloads: List[Dict[str, Any]],
) -> None:
    """
    Upsert chunk vectors with metadata payload.

    Each payload must include: chunk_id, document_id, org_id, workspace_id,
    page_start, page_end, section_path.
    """
    settings = get_settings()
    client = _get_client()
    collection_name = settings.QDRANT_COLLECTION_NAME

    from qdrant_client.models import PointStruct

    points = [
        PointStruct(
            id=chunk_id,
            vector=vector,
            payload=payload,
        )
        for chunk_id, vector, payload in zip(chunk_ids, vectors, payloads)
    ]

    # Upsert in batches of 100
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        client.upsert(collection_name=collection_name, points=batch)

    logger.info("Upserted %d vectors to Qdrant collection '%s'", len(points), collection_name)


def search_vectors(
    query_vector: List[float],
    org_id: str,
    workspace_id: str,
    top_k: int = 30,
    document_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Semantic search with mandatory tenant filtering.

    Args:
        query_vector: The query embedding vector.
        org_id: Organization ID (mandatory filter).
        workspace_id: Workspace ID (mandatory filter).
        top_k: Number of results to return.
        document_ids: Optional list of document IDs to filter by.

    Returns:
        List of dicts with 'id', 'score', and payload fields.
    """
    settings = get_settings()
    client = _get_client()
    collection_name = settings.QDRANT_COLLECTION_NAME

    from qdrant_client.models import FieldCondition, Filter, MatchValue

    # Mandatory tenant filter
    must_conditions = [
        FieldCondition(key="org_id", match=MatchValue(value=org_id)),
        FieldCondition(key="workspace_id", match=MatchValue(value=workspace_id)),
    ]

    # Optional document filter
    if document_ids:
        from qdrant_client.models import MatchAny
        must_conditions.append(
            FieldCondition(key="document_id", match=MatchAny(any=document_ids))
        )

    results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=Filter(must=must_conditions),
        limit=top_k,
    )

    return [
        {
            "id": str(hit.id),
            "score": hit.score,
            **hit.payload,
        }
        for hit in results
    ]


def delete_document_vectors(document_id: str) -> None:
    """Delete all vectors for a specific document."""
    settings = get_settings()
    client = _get_client()
    collection_name = settings.QDRANT_COLLECTION_NAME

    from qdrant_client.models import FieldCondition, Filter, MatchValue

    client.delete(
        collection_name=collection_name,
        points_selector=Filter(
            must=[
                FieldCondition(key="document_id", match=MatchValue(value=document_id)),
            ]
        ),
    )
    logger.info("Deleted vectors for document %s", document_id)
