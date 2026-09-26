"""
Async database session management.
Supports Supabase (PostgreSQL with SSL required) and local development.
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_engine = None
_async_session_factory = None


def get_engine():
    """Get or create the async SQLAlchemy engine.
    
    In production (Supabase), SSL is required and the free tier
    limits connections to ~15, so pool_size is kept small.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        is_production = settings.SERVICE_ENV == "production"

        # Supabase requires SSL in production.
        # asyncpg accepts ssl as a connect_arg.
        connect_args = {"ssl": "require"} if is_production else {}

        _engine = create_async_engine(
            settings.AI_DATABASE_URL,
            echo=settings.SERVICE_ENV == "local",
            # Supabase free tier allows ~15 connections total.
            # Keep pool small to avoid "too many connections" errors.
            pool_size=3 if is_production else 5,
            max_overflow=2 if is_production else 10,
            pool_pre_ping=True,
            pool_recycle=300,  # Recycle stale connections every 5 minutes
            connect_args=connect_args,
        )
    return _engine


def get_session_factory():
    """Get or create the async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


def async_session_factory():
    """Return a new AsyncSession instance."""
    return get_session_factory()()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async DB session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_db() -> None:
    """Close the database engine (for shutdown)."""
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
