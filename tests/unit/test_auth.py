"""
Unit tests for authentication and authorization.
"""
from __future__ import annotations

import pytest
from app.services.auth_service import hash_password, verify_password, _generate_raw_key, _hash_key

def test_password_hashing():
    raw = "SuperSecret123!"
    hashed = hash_password(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

def test_api_key_generation():
    raw_key = _generate_raw_key()
    key_hash = _hash_key(raw_key)
    assert raw_key.startswith("sk-engram-")
    assert len(key_hash) == 64
