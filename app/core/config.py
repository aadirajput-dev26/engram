"\"\"
Application settings loaded from environment variables and .env file.
All external configuration is centralized here per docs/19_ENVIRONMENT_VARIABLES.md.
\"\"\"
from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    "\"\"Central configuration for the AI Document Intelligence service.\"\"\"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- 1. Service Identity ---
    SERVICE_ENV: Literal["local", "staging", "production"] = "local"
    AI_SERVICE_API_KEY: str = Field(
        ...,
        description=(
            "Shared API key sent by Express as X-Api-Key header on every request. "
            "Set this in .env and match it in your Express FASTAPI_API_KEY env var."
        ),
    )

    # --- 2. Database ---
    AI_DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/rag_ai",
        description="AI-owned PostgreSQL schema connection string",
    )

    @field_validator("AI_DATABASE_URL")
    @classmethod
    def force_asyncpg(cls, v: str) -> str:
        "\"\"Ensure the URL uses the asyncpg driver, converting Supabase default URLs.\"\"\"
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://") and "asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        if "prepared_statement_cache_size" not in v:
            sep = "&" if "?" in v else "?"
            v += f"{sep}prepared_statement_cache_size=0"
            
        return v

    # --- 3. Object Storage ---
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    STORAGE_LOCAL_DIR: str = "./storage"
    OBJECT_STORAGE_ENDPOINT: Optional[str] = None
    OBJECT_STORAGE_BUCKET: Optional[str] = None
    OBJECT_STORAGE_ACCESS_KEY: Optional[str] = None
    OBJECT_STORAGE_SECRET_KEY: Optional[str] = None
    OBJECT_STORAGE_REGION: Optional[str] = None

    # --- 4. Vector Database ---
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION_NAME: str = "document_chunks"

    # --- 5. LLM Provider ---
    LLM_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    LLM_API_KEY: str = Field(default="", description="API key for LLM provider")
    LLM_MODEL_NAME: str = "gemini-flash-lite-latest"
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.1
    LLM_REQUEST_TIMEOUT_SECONDS: int = 60

    # --- 6. Embeddings & Reranking ---
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-base-en-v1.5"
    EMBEDDING_BATCH_SIZE: int = 32
    RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-base"

    # --- 7. OCR / Document Processing ---
    OCR_ENGINE: str = "rapidocr"
    OCR_RENDER_DPI: int = 200
    MAX_UPLOAD_SIZE_MB: int = 50
    PAGE_BATCH_SIZE: int = 10
    MAX_STAGE_RETRY_COUNT: int = 3

    # --- 8. Retrieval Tuning ---
    RETRIEVAL_TOP_N_SEMANTIC: int = 30
    RETRIEVAL_TOP_N_KEYWORD: int = 30
    RETRIEVAL_TOP_M_FUSED: int = 40
    RETRIEVAL_TOP_K_FINAL: int = 10
    RRF_K_CONSTANT: int = 60

    # --- 9. Topic Analysis ---
    TOPIC_MODEL_BACKEND: str = "lda"
    TOPIC_ASYNC_THRESHOLD_DOCS: int = 20

    # --- 10. Job Queue / Workers ---
    WORKER_POLL_INTERVAL_SECONDS: int = 5
    WORKER_CONCURRENCY: int = 2

    @property
    def database_url_sync(self) -> str:
        "\"\"Return a synchronous database URL (for Alembic).\"\"\"
        return self.AI_DATABASE_URL.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )


def get_settings() -> Settings:
    "\"\"Factory for Settings, enabling test-time overrides.\"\"\"
    return Settings()
