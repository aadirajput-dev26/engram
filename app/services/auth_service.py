"""
Auth service — business logic for registration, login, workspaces, and API keys.

Security design:
  - Passwords: bcrypt via passlib
  - JWT: HS256 signed with JWT_SECRET_KEY, expiry configurable
  - API keys: sk-engram-<32 random base62 chars>
              stored as SHA-256(key) in api_keys.key_hash
              plaintext is returned ONCE and never stored
"""
from __future__ import annotations

import hashlib
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.api_key import ApiKey
from app.models.organization import Organization
from app.models.user import User
from app.models.workspace import Workspace

import bcrypt

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

BASE62 = string.ascii_letters + string.digits  # 62 chars


def hash_password(plain: str) -> str:
    # bcrypt limits passwords to 72 bytes.
    # We encode to bytes, then hash, then decode back to string for the DB.
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(plain[:72].encode('utf-8'), salt)
    return hashed_bytes.decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain[:72].encode('utf-8'), hashed.encode('utf-8'))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _create_access_token(user_id: UUID, org_id: UUID) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "org": str(org_id),
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.PyJWTError on failure."""
    settings = get_settings()
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# API key helpers
# ---------------------------------------------------------------------------

def _generate_raw_key() -> str:
    """Generate a cryptographically random sk-engram-* key (32 base62 chars)."""
    suffix = "".join(secrets.choice(BASE62) for _ in range(32))
    return f"sk-engram-{suffix}"


def _hash_key(raw_key: str) -> str:
    """SHA-256 hex digest of the raw key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _key_prefix(raw_key: str) -> str:
    """First 20 characters — safe to display in UI."""
    return raw_key[:20] + "..."


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

async def register_org(
    db: AsyncSession,
    org_name: str,
    org_slug: str,
    email: str,
    password: str,
    full_name: Optional[str] = None,
) -> dict:
    """
    Create a new Organization + owner User atomically.
    Returns dict with org, user, and a fresh JWT.
    """
    # Check slug uniqueness
    existing_org = await db.execute(
        select(Organization).where(Organization.slug == org_slug)
    )
    if existing_org.scalar_one_or_none():
        raise ValueError(f"Organization slug '{org_slug}' is already taken.")

    # Check email uniqueness
    existing_user = await db.execute(
        select(User).where(User.email == email)
    )
    if existing_user.scalar_one_or_none():
        raise ValueError(f"Email '{email}' is already registered.")

    org = Organization(name=org_name, slug=org_slug)
    db.add(org)
    await db.flush()  # get org.id

    user = User(
        org_id=org.id,
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role="owner",
    )
    db.add(user)
    await db.flush()

    token = _create_access_token(user_id=user.id, org_id=org.id)

    logger.info("Registered org=%s user=%s", org.id, user.id)
    return {
        "org_id": org.id,
        "org_name": org.name,
        "org_slug": org.slug,
        "user_id": user.id,
        "email": user.email,
        "access_token": token,
    }


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

async def login(db: AsyncSession, email: str, password: str) -> dict:
    """Validate credentials and return a JWT."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        raise ValueError("Invalid email or password.")

    if not user.is_active:
        raise ValueError("Account is disabled.")

    token = _create_access_token(user_id=user.id, org_id=user.org_id)

    return {
        "access_token": token,
        "user_id": user.id,
        "org_id": user.org_id,
        "email": user.email,
        "full_name": user.full_name,
    }


# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------

async def create_workspace(
    db: AsyncSession,
    org_id: UUID,
    name: str,
    slug: str,
    description: Optional[str] = None,
) -> Workspace:
    """Create a new workspace under the given org."""
    # Slug must be unique within org
    existing = await db.execute(
        select(Workspace).where(
            Workspace.org_id == org_id, Workspace.slug == slug
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError(f"Workspace slug '{slug}' already exists in this organization.")

    workspace = Workspace(org_id=org_id, name=name, slug=slug, description=description)
    db.add(workspace)
    await db.flush()
    logger.info("Created workspace=%s org=%s", workspace.id, org_id)
    return workspace


async def list_workspaces(db: AsyncSession, org_id: UUID) -> List[Workspace]:
    """List all workspaces belonging to an org."""
    result = await db.execute(
        select(Workspace).where(Workspace.org_id == org_id).order_by(Workspace.created_at)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

async def issue_api_key(
    db: AsyncSession,
    org_id: UUID,
    workspace_id: UUID,
    created_by: UUID,
    name: str,
) -> dict:
    """
    Generate and store a new sk-engram-* API key.
    Returns the raw key (shown only once) plus metadata.
    """
    # Verify workspace belongs to this org
    ws_result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id, Workspace.org_id == org_id
        )
    )
    workspace = ws_result.scalar_one_or_none()
    if not workspace:
        raise ValueError("Workspace not found or does not belong to your organization.")

    raw_key = _generate_raw_key()
    key_hash = _hash_key(raw_key)
    prefix = _key_prefix(raw_key)

    api_key = ApiKey(
        org_id=org_id,
        workspace_id=workspace_id,
        created_by=created_by,
        name=name,
        key_hash=key_hash,
        key_prefix=prefix,
    )
    db.add(api_key)
    await db.flush()

    logger.info("Issued API key id=%s org=%s workspace=%s", api_key.id, org_id, workspace_id)
    return {
        "key_id": api_key.id,
        "key": raw_key,          # Only time plaintext is returned
        "key_prefix": prefix,
        "name": api_key.name,
        "workspace_id": workspace_id,
        "org_id": org_id,
        "created_at": api_key.created_at,
    }


async def list_api_keys(
    db: AsyncSession, org_id: UUID, workspace_id: Optional[UUID] = None
) -> List[ApiKey]:
    """List API keys for an org, optionally filtered by workspace."""
    stmt = select(ApiKey).where(ApiKey.org_id == org_id, ApiKey.is_active == True)
    if workspace_id:
        stmt = stmt.where(ApiKey.workspace_id == workspace_id)
    result = await db.execute(stmt.order_by(ApiKey.created_at.desc()))
    return list(result.scalars().all())


async def revoke_api_key(
    db: AsyncSession, key_id: UUID, org_id: UUID
) -> bool:
    """Soft-delete (deactivate) an API key. Returns True if found and revoked."""
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.org_id == org_id)
    )
    key = result.scalar_one_or_none()
    if not key:
        return False
    key.is_active = False

    # Evict from in-memory cache
    try:
        from app.core.security.auth import invalidate_api_key_cache
        invalidate_api_key_cache()
    except Exception:
        pass

    logger.info("Revoked API key id=%s org=%s", key_id, org_id)
    return True


# ---------------------------------------------------------------------------
# API Key resolution (used by RAG endpoint middleware)
# ---------------------------------------------------------------------------

async def resolve_key(db: AsyncSession, raw_key: str) -> Optional[ApiKey]:
    """
    Look up an API key by its SHA-256 hash.
    Throttles last_used_at to at most once every 5 minutes to avoid burning DB write locks on every request.
    Returns None if not found or inactive.
    """
    key_hash = _hash_key(raw_key)
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash, ApiKey.is_active == True
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key:
        now_utc = datetime.now(timezone.utc)
        # Only write to DB if last_used_at is None or older than 5 minutes
        if api_key.last_used_at is None or (now_utc - api_key.last_used_at).total_seconds() > 300:
            await db.execute(
                update(ApiKey)
                .where(ApiKey.id == api_key.id)
                .values(last_used_at=now_utc)
            )
    return api_key
