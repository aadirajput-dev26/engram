"""
Tests for the Zero-Trust Auth Refactor, Unified Ingestion, and GET /documents endpoint.
"""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.models.document import Document
from app.models.job import ProcessingJob
from app.schemas.auth import TenantContext


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_tenant():
    return TenantContext(
        org_id=uuid4(),
        workspace_id=uuid4(),
        user_id=uuid4(),
        key_id=uuid4(),
    )


@patch("app.api.v1.endpoints.documents.ingest_document", new_callable=AsyncMock)
def test_unified_ingest_file_no_tenant_params(mock_ingest, client: TestClient, mock_tenant: TenantContext):
    """Verify that file ingestion works without passing org_id or workspace_id in form."""
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

    from app.core.security.auth import require_api_key
    app.dependency_overrides[require_api_key] = lambda: mock_tenant

    try:
        files = {"file": ("sample.pdf", b"%PDF-1.4 test binary", "application/pdf")}
        data = {"filename": "sample.pdf"}

        resp = client.post(
            "/api/v1/documents/ingest",
            data=data,
            files=files,
            headers={"X-Api-Key": "test-key"},
        )
        assert resp.status_code == 200, resp.text
        res_data = resp.json()
        assert res_data["document_id"] == str(doc_id)
        assert res_data["status"] == "QUEUED"

        # Assert ingest_document was called with tenant's workspace and org
        mock_ingest.assert_called_once()
        _, kwargs = mock_ingest.call_args
        assert kwargs["org_id"] == str(mock_tenant.org_id)
        assert kwargs["workspace_id"] == str(mock_tenant.workspace_id)
        assert kwargs["uploaded_by_user_id"] == str(mock_tenant.user_id)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_api_key, None)


@patch("app.core.parsing.parser_factory.parse_from_url")
@patch("app.api.v1.endpoints.documents.ingest_document", new_callable=AsyncMock)
def test_unified_ingest_url(mock_ingest, mock_parse_url, client: TestClient, mock_tenant: TenantContext):
    """Verify that URL ingestion works via POST /api/v1/documents/ingest."""
    doc_id = uuid4()
    ver_id = uuid4()
    job_id = uuid4()

    mock_page = MagicMock()
    mock_page.raw_text = "Parsed content from website."
    mock_doc = MagicMock()
    mock_doc.pages = [mock_page]

    mock_parse_url.return_value = (mock_doc, "text/html", "website.html")

    mock_ingest.return_value = {
        "document_id": str(doc_id),
        "document_version_id": str(ver_id),
        "job_id": str(job_id),
        "status": "QUEUED",
    }

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    from app.core.security.auth import require_api_key
    app.dependency_overrides[require_api_key] = lambda: mock_tenant

    try:
        data = {"url": "https://example.com/article"}
        resp = client.post(
            "/api/v1/documents/ingest",
            data=data,
            headers={"X-Api-Key": "test-key"},
        )
        assert resp.status_code == 200, resp.text
        res_data = resp.json()
        assert res_data["document_id"] == str(doc_id)
        assert res_data["status"] == "QUEUED"

        mock_parse_url.assert_called_once_with("https://example.com/article")
        mock_ingest.assert_called_once()
        _, kwargs = mock_ingest.call_args
        assert kwargs["org_id"] == str(mock_tenant.org_id)
        assert kwargs["workspace_id"] == str(mock_tenant.workspace_id)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_api_key, None)


def test_unified_ingest_missing_both_file_and_url(client: TestClient, mock_tenant: TenantContext):
    """Verify that ingestion fails with 400 when neither file nor url is given."""
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    from app.core.security.auth import require_api_key
    app.dependency_overrides[require_api_key] = lambda: mock_tenant

    try:
        resp = client.post(
            "/api/v1/documents/ingest",
            data={},
            headers={"X-Api-Key": "test-key"},
        )
        assert resp.status_code == 400
        data = resp.json()
        error_obj = data.get("detail", {}).get("error") or data.get("error", {})
        assert error_obj["code"] == "MISSING_INPUT"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_api_key, None)


def test_get_documents_list(client: TestClient, mock_tenant: TenantContext):
    """Verify GET /api/v1/documents lists workspace documents."""
    doc1 = Document(
        id=uuid4(),
        org_id=mock_tenant.org_id,
        workspace_id=mock_tenant.workspace_id,
        filename="first.pdf",
        content_hash="hash1",
        current_version_id=uuid4(),
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )
    doc2 = Document(
        id=uuid4(),
        org_id=mock_tenant.org_id,
        workspace_id=mock_tenant.workspace_id,
        filename="second.pdf",
        content_hash="hash2",
        current_version_id=uuid4(),
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )

    mock_count_res = MagicMock()
    mock_count_res.scalar_one.return_value = 2

    mock_docs_res = MagicMock()
    mock_docs_res.scalars.return_value.all.return_value = [doc1, doc2]

    mock_jobs_res = MagicMock()
    mock_jobs_res.all.return_value = [
        (doc1.id, "READY"),
        (doc2.id, "PROCESSING"),
    ]

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [mock_count_res, mock_docs_res, mock_jobs_res]
    app.dependency_overrides[get_db] = lambda: mock_db

    from app.core.security.auth import require_api_key
    app.dependency_overrides[require_api_key] = lambda: mock_tenant

    try:
        resp = client.get(
            "/api/v1/documents",
            headers={"X-Api-Key": "test-key"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 2
        assert len(data["documents"]) == 2
        assert data["documents"][0]["filename"] == "first.pdf"
        assert data["documents"][0]["status"] == "READY"
        assert data["documents"][1]["filename"] == "second.pdf"
        assert data["documents"][1]["status"] == "PROCESSING"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_api_key, None)
