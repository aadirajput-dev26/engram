"""
Local filesystem object storage abstraction.
Preserves S3-style key semantics for easy migration to cloud storage later.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LocalStorage:
    """Object storage backed by the local filesystem."""

    def __init__(self, base_dir: Optional[str] = None):
        settings = get_settings()
        self._base_dir = Path(base_dir or settings.STORAGE_LOCAL_DIR).resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)
        logger.info("LocalStorage initialized at %s", self._base_dir)

    def _key_to_path(self, key: str) -> Path:
        """Convert an S3-style key to a local filesystem path."""
        # Sanitize key to prevent path traversal
        safe_key = key.lstrip("/").replace("..", "")
        path = (self._base_dir / safe_key).resolve()
        if os.name == "nt":
            path_str = str(path)
            if not path_str.startswith("\\\\?\\"):
                path_str = "\\\\?\\" + path_str
            return Path(path_str)
        return path

    def save_file(self, key: str, data: bytes) -> str:
        """Save data to storage. Returns the key."""
        path = self._key_to_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        logger.debug("Saved %d bytes to %s", len(data), key)
        return key

    def save_file_from_path(self, key: str, source_path: str) -> str:
        """Copy a file from source_path into storage under key."""
        dest = self._key_to_path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest)
        logger.debug("Copied %s to %s", source_path, key)
        return key

    def get_file(self, key: str) -> bytes:
        """Read data from storage."""
        path = self._key_to_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {key}")
        return path.read_bytes()

    def get_file_path(self, key: str) -> str:
        """Get the absolute filesystem path for a key (for libraries that need a path)."""
        path = self._key_to_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {key}")
        return str(path)

    def delete_file(self, key: str) -> None:
        """Delete an object from storage."""
        path = self._key_to_path(key)
        if path.exists():
            path.unlink()
            logger.debug("Deleted %s", key)

    def exists(self, key: str) -> bool:
        """Check if an object exists."""
        return self._key_to_path(key).exists()

    @staticmethod
    def compute_hash(data: bytes) -> str:
        """Compute SHA-256 hash of data."""
        return hashlib.sha256(data).hexdigest()


# Module-level singleton
_storage: Optional[LocalStorage] = None


def get_storage() -> LocalStorage:
    """Get or create the storage singleton."""
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage
