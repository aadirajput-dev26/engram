"""
API v1 router — aggregates all endpoint routers under /api/v1.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import documents, query, search

router = APIRouter(prefix="/api/v1")

router.include_router(documents.router)
router.include_router(query.router)
router.include_router(search.router)
