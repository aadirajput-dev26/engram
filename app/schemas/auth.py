"""
Pydantic schemas for auth and tenant management endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Registration & Login
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    """Create a new organization + owner user in one shot."""
    org_name: str = Field(..., min_length=2, max_length=255)
    org_slug: str = Field(
        ...,
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="URL-safe lowercase slug, e.g. 'acme-corp'",
    )
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = Field(None, max_length=255)

    @field_validator("org_slug")
    @classmethod
    def slug_lower(cls, v: str) -> str:
        return v.lower()


class RegisterResponse(BaseModel):
    org_id: UUID
    org_name: str
    org_slug: str
    user_id: UUID
    email: str
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    org_id: UUID
    email: str
    full_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------

class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(
        ...,
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    description: Optional[str] = None

    @field_validator("slug")
    @classmethod
    def slug_lower(cls, v: str) -> str:
        return v.lower()


class WorkspaceResponse(BaseModel):
    workspace_id: UUID
    org_id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceListResponse(BaseModel):
    workspaces: List[WorkspaceResponse]
    total: int


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

class IssueApiKeyRequest(BaseModel):
    workspace_id: UUID
    name: str = Field(..., min_length=1, max_length=255, description="Human-readable label for this key")


class ApiKeyCreatedResponse(BaseModel):
    """Returned ONCE at creation time. The full key is never retrievable again."""
    key_id: UUID
    key: str = Field(..., description="Full sk-engram-* key — store this securely, shown only once")
    key_prefix: str = Field(..., description="Short prefix shown in UI for identification")
    name: str
    workspace_id: UUID
    org_id: UUID
    created_at: datetime


class ApiKeyResponse(BaseModel):
    """Safe representation — key hash is never exposed."""
    key_id: UUID
    key_prefix: str
    name: str
    workspace_id: UUID
    org_id: UUID
    is_active: bool
    last_used_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyListResponse(BaseModel):
    keys: List[ApiKeyResponse]
    total: int


# ---------------------------------------------------------------------------
# Tenant context (injected by resolve_api_key dependency)
# ---------------------------------------------------------------------------

class TenantContext(BaseModel):
    """Resolved from a valid sk-engram-* key. Injected into every RAG endpoint."""
    org_id: UUID
    workspace_id: UUID
    user_id: UUID
    key_id: UUID
