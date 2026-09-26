"""
Pytest configuration and shared fixtures.
"""
import os

# Set test environment variables before any app imports
os.environ.setdefault("AI_SERVICE_API_KEY", "test-service-key")
os.environ.setdefault("AI_SCOPE_TOKEN_SECRET", "test-scope-secret")
os.environ.setdefault("AI_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/rag_ai_test")
os.environ.setdefault("SERVICE_ENV", "local")
os.environ.setdefault("LLM_API_KEY", "test-llm-key")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
