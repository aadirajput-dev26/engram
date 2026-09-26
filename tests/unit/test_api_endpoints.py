"""
Integration/unit tests for FastAPI API endpoints.
"""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt
import pytest
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.core.security.auth import ScopeContext
from app.db.session import get_db
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    settings = get_settings()
    user_id = str(uuid4())
    org_id = str(uuid4())
    ws_id = str(uuid4())

    return {
        "X-Api-Key": settings.AI_SERVICE_API_KEY,
    }


def test_health_endpoints():
    with TestClient(app) as test_client:
        # Live check
        resp = test_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "alive"

        # Ready check
        ready_resp = test_client.get("/health/ready")
        assert ready_resp.status_code == 200
        ready_data = ready_resp.json()
        assert ready_data["status"] == "ready"
    ready_data = ready_resp.json()
    assert ready_data["status"] == "ready"


def test_auth_rejection_missing_headers(client: TestClient):
    # Missing headers should fail with 422 or 401
    resp = client.post(
        "/api/v1/query",
        json={"query_text": "What was production?"},
    )
    assert resp.status_code in (401, 422)


@patch("app.api.v1.endpoints.query.process_query", new_callable=AsyncMock)
def test_query_endpoint(mock_query, client: TestClient, auth_headers: dict):
    mock_query.return_value = {
        "answer": "Production was 131.5 MT in FY24 [F1].",
        "route_used": "structured",
        "no_evidence": False,
        "citations": [],
        "structured_evidence": [],
        "confidence": 0.95,
        "latency_ms": 120,
    }

    # Mock DB dependency
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        resp = client.post(
            "/api/v1/query",
            json={
                "query_text": "What was production in 2023?",
                "scope": {"org_id": str(uuid4()), "workspace_id": str(uuid4())},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["route_used"] == "structured"
        assert "131.5 MT" in data["answer"]
    finally:
        app.dependency_overrides.pop(get_db, None)


@patch("app.api.v1.endpoints.search.rerank")
@patch("app.api.v1.endpoints.search.semantic_search")
@patch("app.api.v1.endpoints.search.keyword_search", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.search.reciprocal_rank_fusion")
def test_search_endpoint(mock_rrf, mock_kw, mock_sem, mock_rerank, client: TestClient, auth_headers: dict):
    mock_sem.return_value = []
    mock_kw.return_value = []
    mock_rrf.return_value = [
        {
            "chunk_id": str(uuid4()),
            "document_id": str(uuid4()),
            "document_name": "Report.pdf",
            "page_start": 1,
            "page_end": 1,
            "section_path": "1",
            "text": "Overview text",
            "rrf_score": 0.032,
        }
    ]
    mock_rerank.return_value = mock_rrf.return_value

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        resp = client.post(
            "/api/v1/search",
            json={
                "query_text": "mining methods",
                "scope": {"org_id": str(uuid4()), "workspace_id": str(uuid4())},
                "top_k": 5,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["results"][0]["snippet"] == "Overview text"
    finally:
        app.dependency_overrides.pop(get_db, None)
