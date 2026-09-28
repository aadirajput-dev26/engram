"""
Complete test suite for all 13 API endpoints in the AI Document Intelligence Service.
"""
from __future__ import annotations

import datetime
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.models.document import Document, DocumentVersion
from app.models.job import ProcessingJob
from app.models.table import Table


@pytest.fixture
def test_env():
    settings = get_settings()
    org_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()

    headers = {
        "X-Api-Key": settings.AI_SERVICE_API_KEY,
    }

    return {
        "org_id": org_id,
        "workspace_id": workspace_id,
        "user_id": user_id,
        "headers": headers,
    }


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


# 1. GET /health
def test_1_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}


# 2. GET /health/ready
def test_2_health_ready(client: TestClient):
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


# 3. POST /api/v1/documents/ingest
@patch("app.api.v1.endpoints.documents.ingest_document", new_callable=AsyncMock)
def test_3_document_ingest(mock_ingest, client: TestClient, test_env: dict):
    doc_id = uuid4()
    ver_id = uuid4()
    job_id = uuid4()

    mock_ingest.return_value = {
        "document_id": str(doc_id),
        "document_version_id": str(ver_id),
        "job_id": str(job_id),
        "status": "QUEUED",
    }

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        files = {"file": ("test.pdf", b"%PDF-1.4 mock content", "application/pdf")}
        data = {
            "org_id": str(test_env["org_id"]),
            "workspace_id": str(test_env["workspace_id"]),
            "uploaded_by_user_id": str(test_env["user_id"]),
            "filename": "test.pdf",
            "declared_mime_type": "application/pdf",
        }
        resp = client.post(
            "/api/v1/documents/ingest",
            data=data,
            files=files,
            headers=test_env["headers"],
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["document_id"] == str(doc_id)
        assert body["document_version_id"] == str(ver_id)
        assert body["job_id"] == str(job_id)
        assert body["status"] == "QUEUED"
    finally:
        app.dependency_overrides.pop(get_db, None)


# 4. GET /api/v1/documents/{document_id}/status
def test_4_document_status(client: TestClient, test_env: dict):
    doc_id = uuid4()
    ver_id = uuid4()
    job_id = uuid4()

    mock_job = ProcessingJob(
        id=job_id,
        document_id=doc_id,
        document_version_id=ver_id,
        org_id=test_env["org_id"],
        workspace_id=test_env["workspace_id"],
        overall_status="COMPLETED",
        stages=[
            {"stage": "PAGE_INDEX", "progress_current": 10, "progress_total": 10},
            {"stage": "EMBEDDING", "progress_current": 100, "progress_total": 100},
        ],
        created_by_user_id=test_env["user_id"],
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_job

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_res
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        resp = client.get(
            f"/api/v1/documents/{doc_id}/status",
            headers=test_env["headers"],
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["document_id"] == str(doc_id)
        assert body["overall_status"] == "COMPLETED"
        assert len(body["stage_details"]) == 2
    finally:
        app.dependency_overrides.pop(get_db, None)


# 5. POST /api/v1/documents/{document_id}/process
def test_5_document_reprocess(client: TestClient, test_env: dict):
    doc_id = uuid4()
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        resp = client.post(
            f"/api/v1/documents/{doc_id}/process",
            json={"priority": 1, "force_ocr": False},
            headers=test_env["headers"],
        )
        assert resp.status_code == 501, resp.text
        body = resp.json()
        error_code = body.get("error", {}).get("code") or body.get("detail", {}).get("error", {}).get("code")
        assert error_code == "NOT_IMPLEMENTED"
    finally:
        app.dependency_overrides.pop(get_db, None)


# 6. POST /api/v1/query
@patch("app.api.v1.endpoints.query.process_query", new_callable=AsyncMock)
def test_6_query(mock_query, client: TestClient, test_env: dict):
    doc_id = uuid4()
    mock_query.return_value = {
        "answer": "Coal production reached 131.5 MT in FY24 [F1].",
        "route_used": "structured",
        "no_evidence": False,
        "citations": [
            {
                "citation_id": "F1",
                "source_type": "fact",
                "document_id": str(doc_id),
                "document_name": "Annual_Report_2024.pdf",
                "page_number": 12,
            }
        ],
        "structured_evidence": [
            {
                "fact_id": str(uuid4()),
                "metric": "raw_coal_production",
                "value": 131.5,
                "unit": "MT",
                "mine_name": "Gevra",
                "period_value": "FY24",
                "page_number": 12,
            }
        ],
        "confidence": 0.98,
        "latency_ms": 95,
    }

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        resp = client.post(
            "/api/v1/query",
            json={
                "query_text": "What was raw coal production in FY24?",
                "scope": {
                    "org_id": str(test_env["org_id"]),
                    "workspace_id": str(test_env["workspace_id"]),
                    "document_ids": [str(doc_id)],
                },
                "route_override": "structured",
            },
            headers=test_env["headers"],
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "131.5 MT" in body["answer"]
        assert body["route_used"] == "structured"
        assert body["citations"][0]["citation_id"] == "F1"
    finally:
        app.dependency_overrides.pop(get_db, None)


# 7. POST /api/v1/search
@patch("app.api.v1.endpoints.search.rerank")
@patch("app.api.v1.endpoints.search.semantic_search")
@patch("app.api.v1.endpoints.search.keyword_search", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.search.reciprocal_rank_fusion")
def test_7_search(mock_rrf, mock_kw, mock_sem, mock_rerank, client: TestClient, test_env: dict):
    chunk_id = uuid4()
    doc_id = uuid4()

    mock_sem.return_value = []
    mock_kw.return_value = []
    candidates = [
        {
            "chunk_id": str(chunk_id),
            "document_id": str(doc_id),
            "document_name": "Annual_Report.pdf",
            "page_start": 5,
            "page_end": 6,
            "section_path": "Operational Performance",
            "text": "Total coal dispatches were 125 MT.",
            "semantic_score": 0.89,
            "keyword_score": 0.75,
            "rrf_score": 0.032,
            "rerank_score": 0.94,
        }
    ]
    mock_rrf.return_value = candidates
    mock_rerank.return_value = candidates

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        resp = client.post(
            "/api/v1/search",
            json={
                "query_text": "coal dispatch metrics",
                "scope": {
                    "org_id": str(test_env["org_id"]),
                    "workspace_id": str(test_env["workspace_id"]),
                },
                "top_k": 5,
            },
            headers=test_env["headers"],
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 1
        assert body["results"][0]["chunk_id"] == str(chunk_id)
        assert body["results"][0]["rerank_score"] == 0.94
    finally:
        app.dependency_overrides.pop(get_db, None)


