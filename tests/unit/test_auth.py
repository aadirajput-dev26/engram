"""
Unit tests for authentication and authorization.
"""
from __future__ import annotations

import datetime
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.core.security.auth import (
    ScopeContext,
    require_permission,
    verify_scope_token,
    verify_service_key,
)


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        AI_SERVICE_API_KEY="test-service-key",
        AI_SCOPE_TOKEN_SECRET="test-secret-key-1234567890",
    )


@pytest.mark.asyncio
async def test_verify_service_key_success(test_settings: Settings):
    key = await verify_service_key(
        x_service_key="test-service-key",
        settings=test_settings,
    )
    assert key == "test-service-key"


@pytest.mark.asyncio
async def test_verify_service_key_invalid(test_settings: Settings):
    with pytest.raises(HTTPException) as exc_info:
        await verify_service_key(
            x_service_key="wrong-key",
            settings=test_settings,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_scope_token_success(test_settings: Settings):
    user_id = str(uuid4())
    org_id = str(uuid4())
    ws_id = str(uuid4())

    token = jwt.encode(
        {
            "user_id": user_id,
            "org_id": org_id,
            "workspace_id": ws_id,
            "permissions": ["ai.query", "documents.read"],
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        },
        test_settings.AI_SCOPE_TOKEN_SECRET,
        algorithm="HS256",
    )

    ctx = await verify_scope_token(
        authorization=f"Bearer {token}",
        settings=test_settings,
    )
    assert ctx.user_id == user_id
    assert ctx.org_id == org_id
    assert ctx.workspace_id == ws_id
    assert str(ctx.org_uuid) == org_id
    assert str(ctx.workspace_uuid) == ws_id
    assert "ai.query" in ctx.permissions


@pytest.mark.asyncio
async def test_verify_scope_token_expired(test_settings: Settings):
    token = jwt.encode(
        {
            "user_id": str(uuid4()),
            "org_id": str(uuid4()),
            "workspace_id": str(uuid4()),
            "exp": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
        },
        test_settings.AI_SCOPE_TOKEN_SECRET,
        algorithm="HS256",
    )

    with pytest.raises(HTTPException) as exc_info:
        await verify_scope_token(
            authorization=f"Bearer {token}",
            settings=test_settings,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_scope_token_invalid_signature(test_settings: Settings):
    token = jwt.encode(
        {
            "user_id": str(uuid4()),
            "org_id": str(uuid4()),
            "workspace_id": str(uuid4()),
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        },
        "wrong-secret",
        algorithm="HS256",
    )

    with pytest.raises(HTTPException) as exc_info:
        await verify_scope_token(
            authorization=f"Bearer {token}",
            settings=test_settings,
        )
    assert exc_info.value.status_code == 401
