"""
FastAPI application entrypoint.

Provides:
  - /health and /health/ready endpoints
  - Consistent error envelope handler
  - /api/v1 router mount
  - Lifespan handler for startup/shutdown
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)

# Track service readiness
_ready = False


def _error_envelope(code: str, message: str, details: Any = None) -> dict:
    """Build a consistent error response envelope per docs/08_API_CONTRACTS.md."""
    return {"error": {"code": code, "message": message, "details": details or {}}}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown hooks."""
    global _ready
    settings = get_settings()
    setup_logging("DEBUG" if settings.SERVICE_ENV == "local" else "INFO")
    logger.info(
        "Starting AI Document Intelligence Service (env=%s)", settings.SERVICE_ENV
    )

    # Startup: initialize resources
    # DB pool, embedding model, etc. will be initialized here in later slices
    _ready = True
    logger.info("Service is ready")

    yield

    # Shutdown: clean up resources
    _ready = False
    logger.info("Service shutting down")


app = FastAPI(
    title="AI Document Intelligence / RAG Microservice",
    description="FastAPI service for document processing, RAG-based retrieval, and AI-powered query answering.",
    version="0.1.0",
    lifespan=lifespan,
)


# --- Error handlers ---


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return validation errors in the standard error envelope."""
    return JSONResponse(
        status_code=422,
        content=_error_envelope(
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            details={"errors": exc.errors()},
        ),
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all handler returning the standard error envelope."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=_error_envelope(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
        ),
    )


# --- Middleware ---


@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    """Add X-Process-Time header to all responses."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    response.headers["X-Process-Time-Ms"] = str(elapsed_ms)
    return response


# --- Health endpoints ---


@app.get("/health", tags=["health"])
async def health():
    """Basic liveness check."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
async def health_ready():
    """Readiness check — returns 503 if the service is not ready."""
    if not _ready:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready"},
        )
    return {"status": "ready"}


# --- Mount API router ---

app.include_router(api_v1_router)
