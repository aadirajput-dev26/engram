"""
Auth & tenant management endpoints.

Routes:
  POST  /auth/register              — create org + owner user, return JWT
  POST  /auth/login                 — email/password login, return JWT
  GET   /auth/me                    — current user info (JWT required)
  POST  /auth/workspaces            — create workspace (JWT required)
  GET   /auth/workspaces            — list workspaces in caller's org (JWT required)
  POST  /auth/api-keys              — issue sk-engram-* key (JWT required)
  GET   /auth/api-keys              — list active keys (JWT required)
  DELETE /auth/api-keys/{key_id}    — revoke a key (JWT required)
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security.auth import get_current_user_id
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ApiKeyCreatedResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
    CreateWorkspaceRequest,
    IssueApiKeyRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    WorkspaceListResponse,
    WorkspaceResponse,
)
from app.services.auth_service import (
    create_workspace,
    issue_api_key,
    list_api_keys,
    list_workspaces,
    login,
    register_org,
    revoke_api_key,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Registration & Login (public)
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new organization and owner account",
)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a new Organization + owner User in one atomic operation.
    Returns a JWT you can use immediately for subsequent requests.
    """
    try:
        result = await register_org(
            db=db,
            org_name=request.org_name,
            org_slug=request.org_slug,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
        )
        return RegisterResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "CONFLICT", "message": str(e), "details": {}}},
        )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login and receive a JWT",
)
async def login_endpoint(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Email + password login. Returns a signed JWT."""
    try:
        result = await login(db=db, email=request.email, password=request.password)
        return LoginResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": str(e), "details": {}}},
        )


# ---------------------------------------------------------------------------
# Current user info
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    summary="Get current user info",
)
async def me(
    token_payload: dict = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Returns the currently authenticated user's profile."""
    user_id = UUID(token_payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "USER_NOT_FOUND", "message": "User not found.", "details": {}}},
        )
    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "org_id": user.org_id,
    }


# ---------------------------------------------------------------------------
# Workspaces (JWT required)
# ---------------------------------------------------------------------------

@router.post(
    "/workspaces",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace in your organization",
)
async def create_workspace_endpoint(
    request: CreateWorkspaceRequest,
    token_payload: dict = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Creates a workspace scoped to the caller's organization."""
    org_id = UUID(token_payload["org"])
    try:
        workspace = await create_workspace(
            db=db,
            org_id=org_id,
            name=request.name,
            slug=request.slug,
            description=request.description,
        )
        return WorkspaceResponse(
            workspace_id=workspace.id,
            org_id=workspace.org_id,
            name=workspace.name,
            slug=workspace.slug,
            description=workspace.description,
            created_at=workspace.created_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "CONFLICT", "message": str(e), "details": {}}},
        )


@router.get(
    "/workspaces",
    response_model=WorkspaceListResponse,
    summary="List all workspaces in your organization",
)
async def list_workspaces_endpoint(
    token_payload: dict = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Returns all workspaces belonging to the caller's organization."""
    org_id = UUID(token_payload["org"])
    workspaces = await list_workspaces(db=db, org_id=org_id)
    items = [
        WorkspaceResponse(
            workspace_id=ws.id,
            org_id=ws.org_id,
            name=ws.name,
            slug=ws.slug,
            description=ws.description,
            created_at=ws.created_at,
        )
        for ws in workspaces
    ]
    return WorkspaceListResponse(workspaces=items, total=len(items))


# ---------------------------------------------------------------------------
# API Keys (JWT required)
# ---------------------------------------------------------------------------

@router.post(
    "/api-keys",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a new sk-engram-* API key",
)
async def issue_key_endpoint(
    request: IssueApiKeyRequest,
    token_payload: dict = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Generates a new `sk-engram-*` API key scoped to the specified workspace.

    ⚠️ The full key is returned **only once** — store it securely.
    Only the first 20 characters (prefix) are stored server-side for display.
    """
    org_id = UUID(token_payload["org"])
    user_id = UUID(token_payload["sub"])
    try:
        result = await issue_api_key(
            db=db,
            org_id=org_id,
            workspace_id=request.workspace_id,
            created_by=user_id,
            name=request.name,
        )
        return ApiKeyCreatedResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e), "details": {}}},
        )


@router.get(
    "/api-keys",
    response_model=ApiKeyListResponse,
    summary="List your active API keys",
)
async def list_keys_endpoint(
    workspace_id: UUID | None = None,
    token_payload: dict = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists all active API keys for your organization.
    Optionally filter by workspace_id query param.
    Full key values are never returned — only the prefix.
    """
    org_id = UUID(token_payload["org"])
    keys = await list_api_keys(db=db, org_id=org_id, workspace_id=workspace_id)
    items = [
        ApiKeyResponse(
            key_id=k.id,
            key_prefix=k.key_prefix,
            name=k.name,
            workspace_id=k.workspace_id,
            org_id=k.org_id,
            is_active=k.is_active,
            last_used_at=k.last_used_at,
            created_at=k.created_at,
        )
        for k in keys
    ]
    return ApiKeyListResponse(keys=items, total=len(items))


@router.delete(
    "/api-keys/{key_id}",
    status_code=status.HTTP_200_OK,
    summary="Revoke an API key",
)
async def revoke_key_endpoint(
    key_id: UUID,
    token_payload: dict = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Permanently deactivates an API key. Any requests using this key will
    immediately receive 401. This action cannot be undone.
    """
    org_id = UUID(token_payload["org"])
    revoked = await revoke_api_key(db=db, key_id=key_id, org_id=org_id)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "API key not found.", "details": {}}},
        )
    return {"message": "API key revoked successfully.", "key_id": key_id}
