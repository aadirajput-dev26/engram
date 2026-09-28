"""
Tests for Collections API.
"""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.schemas.collection import CollectionResponse
from datetime import datetime

client = TestClient(app)

@pytest.fixture
def auth_headers():
    import os
    return {"X-Api-Key": os.getenv("AI_SERVICE_API_KEY", "test-service-key")}


@patch("app.api.v1.endpoints.collections.collection_service.create_collection", new_callable=AsyncMock)
def test_create_collection(mock_create, auth_headers):
    org_id = str(uuid4())
    workspace_id = str(uuid4())
    col_id = uuid4()
    
    mock_create.return_value = CollectionResponse(
        id=col_id,
        org_id=uuid4(),
        workspace_id=uuid4(),
        name="Test Collection",
        description="A test collection",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    response = client.post(
        f"/api/v1/collections?org_id={org_id}&workspace_id={workspace_id}",
        headers=auth_headers,
        json={"name": "Test Collection", "description": "A test collection"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Collection"
    assert "id" in data


@patch("app.api.v1.endpoints.collections.collection_service.list_collections", new_callable=AsyncMock)
def test_list_collections(mock_list, auth_headers):
    org_id = str(uuid4())
    workspace_id = str(uuid4())
    
    mock_list.return_value = [
        CollectionResponse(
            id=uuid4(),
            org_id=uuid4(),
            workspace_id=uuid4(),
            name="Test Collection",
            description="A test collection",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    ]
    
    response = client.get(
        f"/api/v1/collections?org_id={org_id}&workspace_id={workspace_id}",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Collection"


@patch("app.api.v1.endpoints.collections.collection_service.get_collection", new_callable=AsyncMock)
def test_get_collection(mock_get, auth_headers):
    org_id = str(uuid4())
    workspace_id = str(uuid4())
    col_id = str(uuid4())
    
    mock_get.return_value = CollectionResponse(
        id=col_id,
        org_id=uuid4(),
        workspace_id=uuid4(),
        name="Test Collection",
        description="A test collection",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    response = client.get(
        f"/api/v1/collections/{col_id}?org_id={org_id}&workspace_id={workspace_id}",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Collection"


@patch("app.api.v1.endpoints.collections.collection_service.update_collection", new_callable=AsyncMock)
def test_update_collection(mock_update, auth_headers):
    org_id = str(uuid4())
    workspace_id = str(uuid4())
    col_id = str(uuid4())
    
    mock_update.return_value = CollectionResponse(
        id=col_id,
        org_id=uuid4(),
        workspace_id=uuid4(),
        name="Updated Collection Name",
        description="A test collection",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    response = client.put(
        f"/api/v1/collections/{col_id}?org_id={org_id}&workspace_id={workspace_id}",
        headers=auth_headers,
        json={"name": "Updated Collection Name"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Collection Name"


@patch("app.api.v1.endpoints.collections.collection_service.delete_collection", new_callable=AsyncMock)
def test_delete_collection(mock_delete, auth_headers):
    org_id = str(uuid4())
    workspace_id = str(uuid4())
    col_id = str(uuid4())
    
    mock_delete.return_value = None
    
    response = client.delete(
        f"/api/v1/collections/{col_id}?org_id={org_id}&workspace_id={workspace_id}",
        headers=auth_headers,
    )
    
    assert response.status_code == 204
