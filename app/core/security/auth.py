"""
Simplified single-layer API key authentication for the FastAPI microservice.

All calls must come from the trusted Express backend, proven by the
X-Api-Key header matching AI_SERVICE_API_KEY in the environment.

Tenant context (org_id, workspace_id, user_id, etc.) is passed directly
in each request body by Express, which handles RBAC at its own layer.

See docs/02_SYSTEM_ARCHITECTURE.md §4 for the updated security model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings


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
# Backwards-compatibility shims so that existing endpoint code that
# imports ScopeContext, require_auth, require_scope, require_permission
# continues to work without changes during the transition.
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
