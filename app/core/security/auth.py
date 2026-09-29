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
# API Key resolution & Zero-Trust Authentication
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)


# In-memory cache for resolved TenantContext:
# raw_key -> (TenantContext, expires_at_timestamp)
import time

_API_KEY_CACHE: dict[str, tuple[TenantContext, float]] = {}
_API_KEY_CACHE_TTL = 300.0  # 5 minutes cache for hot API keys


def invalidate_api_key_cache(raw_key: Optional[str] = None):
    """Clear cached key or entire cache when an API key is revoked."""
    global _API_KEY_CACHE
    if raw_key:
        _API_KEY_CACHE.pop(raw_key, None)
    else:
        _API_KEY_CACHE.clear()


async def require_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-Api-Key"),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """
    Authenticate request via API Key and resolve TenantContext (org_id, workspace_id, user_id, key_id).

    Accepts:
      - 'X-Api-Key: sk-engram-...' or 'X-Api-Key: <AI_SERVICE_API_KEY>'
      - 'Authorization: Bearer sk-engram-...'

    Returns:
        TenantContext with resolved org_id and workspace_id.
    """
    raw_key = None
    if x_api_key and x_api_key.strip():
        raw_key = x_api_key.strip()
    elif credentials and credentials.credentials and credentials.credentials.strip():
        raw_key = credentials.credentials.strip()

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "MISSING_API_KEY",
                    "message": "Missing API Key. Provide via 'X-Api-Key' header or 'Authorization: Bearer <key>'.",
                    "details": {},
                }
            },
        )

    # 0. Check in-memory TTL cache (0ms instant lookup)
    now = time.time()
    cached = _API_KEY_CACHE.get(raw_key)
    if cached is not None:
        tenant_context, expires_at = cached
        if now < expires_at:
            return tenant_context
        else:
            _API_KEY_CACHE.pop(raw_key, None)

    # 1. Programmatic API key path (sk-engram-*)
    if raw_key.startswith("sk-engram-"):
        from app.services.auth_service import resolve_key
        api_key = await resolve_key(db, raw_key)
        if not api_key or not api_key.is_active:
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
        tenant_context = TenantContext(
            org_id=api_key.org_id,
            workspace_id=api_key.workspace_id,
            user_id=api_key.created_by,
            key_id=api_key.id,
        )
        _API_KEY_CACHE[raw_key] = (tenant_context, now + _API_KEY_CACHE_TTL)
        return tenant_context

    # 2. Master service key path (settings.AI_SERVICE_API_KEY)
    if raw_key == settings.AI_SERVICE_API_KEY:
        from sqlalchemy import select
        from app.models.workspace import Workspace
        try:
            ws_res = await db.execute(select(Workspace).order_by(Workspace.created_at.asc()).limit(1))
            ws = ws_res.scalar_one_or_none()
            if ws:
                tenant_context = TenantContext(
                    org_id=ws.org_id,
                    workspace_id=ws.id,
                    user_id=UUID("00000000-0000-0000-0000-000000000001"),
                    key_id=UUID("00000000-0000-0000-0000-000000000001"),
                )
                _API_KEY_CACHE[raw_key] = (tenant_context, now + _API_KEY_CACHE_TTL)
                return tenant_context
        except Exception:
            pass
        tenant_context = TenantContext(
            org_id=UUID("00000000-0000-0000-0000-000000000001"),
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            key_id=UUID("00000000-0000-0000-0000-000000000001"),
        )
        _API_KEY_CACHE[raw_key] = (tenant_context, now + _API_KEY_CACHE_TTL)
        return tenant_context

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


async def verify_api_key(
    tenant: TenantContext = Depends(require_api_key),
) -> TenantContext:
    """Compatibility wrapper returning TenantContext."""
    return tenant


resolve_tenant_from_key = require_api_key


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


async def require_auth(tenant: TenantContext = Depends(require_api_key)) -> ScopeContext:
    """Compat alias — returns ScopeContext populated from TenantContext."""
    return ScopeContext(
        user_id=str(tenant.user_id),
        org_id=str(tenant.org_id),
        workspace_id=str(tenant.workspace_id),
    )


require_scope = require_auth


def require_permission(_permission: str):
    """
    Compat alias — enforces API key and returns ScopeContext.
    """
    async def _check(tenant: TenantContext = Depends(require_api_key)) -> ScopeContext:
        return ScopeContext(
            user_id=str(tenant.user_id),
            org_id=str(tenant.org_id),
            workspace_id=str(tenant.workspace_id),
        )

    return _check
