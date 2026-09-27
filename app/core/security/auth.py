"""
Security / authentication layer.

Two auth paths co-exist:

1. sk-engram-* API keys (new — for end-users of the RAG platform)
   Header: Authorization: Bearer sk-engram-...
   → resolve_tenant_from_key()  returns TenantContext
   → RAG endpoints auto-inject org_id / workspace_id from context

2. Shared X-Api-Key (legacy — for the trusted Express backend)
   Header: X-Api-Key: <AI_SERVICE_API_KEY from .env>
   → require_api_key() / verify_api_key()  (unchanged behaviour)

See docs/02_SYSTEM_ARCHITECTURE.md §4.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.auth import TenantContext

# ---------------------------------------------------------------------------
# Legacy path — shared X-Api-Key (Express → FastAPI internal)
# ---------------------------------------------------------------------------

async def verify_api_key(
    x_api_key: str = Header(..., alias="X-Api-Key"),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Validate the X-Api-Key header against AI_SERVICE_API_KEY.
    Returns the key on success, raises 401 on failure.
    """
    if not x_api_key or x_api_key != settings.AI_SERVICE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_API_KEY",
                    "message": "Invalid or missing X-Api-Key header.",
                    "details": {},
                }
            },
        )
    return x_api_key


async def require_api_key(
    _key: str = Depends(verify_api_key),
) -> None:
    """
    FastAPI dependency: enforce API key authentication on any endpoint.
    Use as:  Depends(require_api_key)
    """
    return None


# ---------------------------------------------------------------------------
# New path — sk-engram-* bearer keys (end-user RAG clients)
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)


async def resolve_tenant_from_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """
    FastAPI dependency: resolve TenantContext from a Bearer sk-engram-* token.

    Usage on an endpoint::

        @router.post("/ingest")
        async def ingest(tenant: TenantContext = Depends(resolve_tenant_from_key)):
            ...

    Raises 401 if the token is missing, malformed, or not found in the DB.
    """
    from app.services.auth_service import resolve_key

    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "MISSING_AUTH",
                    "message": "Authorization header with Bearer sk-engram-* key is required.",
                    "details": {},
                }
            },
        )

    raw_key = credentials.credentials

    if not raw_key.startswith("sk-engram-"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_KEY_FORMAT",
                    "message": "API key must start with 'sk-engram-'.",
                    "details": {},
                }
            },
        )

    api_key = await resolve_key(db, raw_key)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_API_KEY",
                    "message": "API key is invalid, expired, or has been revoked.",
                    "details": {},
                }
            },
        )

    return TenantContext(
        org_id=api_key.org_id,
        workspace_id=api_key.workspace_id,
        user_id=api_key.created_by,
        key_id=api_key.id,
    )


# ---------------------------------------------------------------------------
# JWT dependency — for dashboard endpoints (auth router)
# ---------------------------------------------------------------------------

async def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Validate a dashboard JWT and return the decoded payload.
    Raises 401 on any failure.

    Returns dict with keys: sub (user_id str), org (org_id str).
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "MISSING_TOKEN",
                    "message": "Authorization header with Bearer JWT is required.",
                    "details": {},
                }
            },
        )

    token = credentials.credentials

    # sk-engram-* keys are API keys, not JWTs — reject them here
    if token.startswith("sk-engram-"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "USE_API_KEY_ENDPOINT",
                    "message": "sk-engram-* keys are not valid JWT tokens.",
                    "details": {},
                }
            },
        )

    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "TOKEN_EXPIRED", "message": "JWT has expired.", "details": {}}},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "JWT is invalid.", "details": {}}},
        )

    return payload  # {"sub": user_id_str, "org": org_id_str}


# ---------------------------------------------------------------------------
# Backwards-compatibility shims (kept for existing endpoints)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScopeContext:
    """
    Thin compatibility shim.  Endpoints that previously extracted tenant IDs
    from the JWT scope token now receive them directly from request body fields
    (org_id, workspace_id).  This dataclass is kept so endpoints that still
    reference scope.org_uuid / scope.workspace_uuid do not break immediately.

    In new endpoints, prefer reading org_id / workspace_id directly from the
    Pydantic request model instead.
    """
    user_id: str = ""
    org_id: str = ""
    workspace_id: str = ""
    allowed_document_ids: Optional[List[str]] = None
    workspace_scope: bool = False
    permissions: List[str] = field(default_factory=list)

    @property
    def org_uuid(self) -> UUID:
        return UUID(str(self.org_id))

    @property
    def workspace_uuid(self) -> UUID:
        return UUID(str(self.workspace_id))


async def require_auth(_key: str = Depends(verify_api_key)) -> ScopeContext:
    """Compat alias — returns an empty ScopeContext after API key check."""
    return ScopeContext()


require_scope = require_auth


def require_permission(_permission: str):
    """
    Compat alias — permission checks are now handled by Express (RBAC layer).
    Still enforces the API key; ignores the permission string.
    """
    async def _check(_key: str = Depends(verify_api_key)) -> ScopeContext:
        return ScopeContext()

    return _check
