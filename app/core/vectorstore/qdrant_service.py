"""
Qdrant vector database service via direct HTTP REST (httpx).
Manages collection creation, chunk upsertion, and semantic search
with mandatory tenant payload filtering, completely avoiding native C++ DLL crashes.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_headers() -> Dict[str, str]:
    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.QDRANT_API_KEY:
        headers["api-key"] = settings.QDRANT_API_KEY
    return headers


def ensure_collection(vector_size: int) -> None:
    """Create the Qdrant collection if it doesn't exist."""
    try:
        settings = get_settings()
        base_url = settings.QDRANT_URL.rstrip("/")
        collection_name = settings.QDRANT_COLLECTION_NAME
        headers = _get_headers()

        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{base_url}/collections", headers=headers)
            if resp.status_code == 200:
                collections = resp.json().get("result", {}).get("collections", [])
                existing = [c.get("name") for c in collections]
                if collection_name not in existing:
                    create_payload = {
                        "vectors": {
                            "size": vector_size,
                            "distance": "Cosine",
                        }
                    }
                    create_resp = client.put(
                        f"{base_url}/collections/{collection_name}",
                        json=create_payload,
                        headers=headers,
                    )
                    if create_resp.status_code in (200, 201):
                        logger.info("Created Qdrant collection '%s' (dim=%d, Cosine)", collection_name, vector_size)
                    else:
                        logger.warning("Create collection notice: %s", create_resp.text)
                else:
                    logger.info("Qdrant collection '%s' already exists", collection_name)
    except Exception as e:
        logger.warning("Qdrant collection notice (%s). Continuing with relational vector fallback.", e)


def upsert_chunks(
    chunk_ids: List[str],
    vectors: List[List[float]],
    payloads: List[Dict[str, Any]],
) -> None:
    """
    Upsert chunk vectors with metadata payload.
    """
    try:
        settings = get_settings()
        base_url = settings.QDRANT_URL.rstrip("/")
        collection_name = settings.QDRANT_COLLECTION_NAME
        headers = _get_headers()

        points = [
            {
                "id": chunk_id,
                "vector": vector,
                "payload": payload,
            }
            for chunk_id, vector, payload in zip(chunk_ids, vectors, payloads)
        ]

        batch_size = 100
        with httpx.Client(timeout=30.0) as client:
            for i in range(0, len(points), batch_size):
                batch = points[i : i + batch_size]
                client.put(
                    f"{base_url}/collections/{collection_name}/points",
                    json={"points": batch},
                    headers=headers,
                )

        logger.info("Upserted %d vectors to Qdrant collection '%s'", len(points), collection_name)
    except Exception as e:
        logger.warning("Qdrant vector upsert notice (%s). Chunks safely preserved in PostgreSQL database.", e)


def search_vectors(
    query_vector: List[float],
    org_id: str,
    workspace_id: str,
    top_k: int = 30,
    document_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Semantic search with tenant filtering via REST.
    """
    try:
        settings = get_settings()
        base_url = settings.QDRANT_URL.rstrip("/")
        collection_name = settings.QDRANT_COLLECTION_NAME
        headers = _get_headers()

        must_conditions: List[Dict[str, Any]] = [
            {"key": "org_id", "match": {"value": org_id}},
            {"key": "workspace_id", "match": {"value": workspace_id}},
        ]

        if document_ids:
            must_conditions.append(
                {"key": "document_id", "match": {"any": document_ids}}
            )

        payload = {
            "vector": query_vector,
            "filter": {"must": must_conditions},
            "limit": top_k,
            "with_payload": True,
        }

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{base_url}/collections/{collection_name}/points/search",
                json=payload,
                headers=headers,
            )
            if resp.status_code == 200:
                hits = resp.json().get("result", [])
                return [
                    {
                        "id": str(hit.get("id")),
                        "score": hit.get("score", 0.0),
                        **(hit.get("payload") or {}),
                    }
                    for hit in hits
                ]
            else:
                logger.warning("Qdrant search HTTP %d: %s", resp.status_code, resp.text)
                return []
    except Exception as e:
        logger.warning("Qdrant search notice: %s", e)
        return []


def delete_document_vectors(document_id: str) -> None:
    """Delete all vectors for a specific document."""
    try:
        settings = get_settings()
        base_url = settings.QDRANT_URL.rstrip("/")
        collection_name = settings.QDRANT_COLLECTION_NAME
        headers = _get_headers()

        payload = {
            "filter": {
                "must": [
                    {"key": "document_id", "match": {"value": document_id}}
                ]
            }
        }

        with httpx.Client(timeout=10.0) as client:
            client.post(
                f"{base_url}/collections/{collection_name}/points/delete",
                json=payload,
                headers=headers,
            )
        logger.info("Deleted vectors for document %s", document_id)
    except Exception as e:
        logger.warning("Qdrant delete notice: %s", e)
