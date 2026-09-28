# 19 — Environment Variables & Configuration

This document specifies the environment variables utilized by the RAG Pipeline microservice. All configuration is centralized through Pydantic Settings (`app/core/config.py`).

> **Security Note:** Never commit actual secrets or production keys to version control. Use `.env` for local testing and secure environment vaults in production.

---

## 1. Service Identity & Networking

| Variable | Default Value | Description |
|---|---|---|
| `SERVICE_ENV` | `local` | Execution environment (`local`, `staging`, `production`). |
| `AI_SERVICE_API_KEY` | *(Required)* | Master service API key used for internal/admin verification or fallback access. |
| `JWT_SECRET_KEY` | *(Required in prod)* | Secret key for signing and verifying JSON Web Tokens (dashboard and session authentication). |
| `JWT_ALGORITHM` | `HS256` | JWT signature algorithm. |
| `JWT_EXPIRE_MINUTES` | `10080` (7 days) | JWT expiration lifetime in minutes. |

---

## 2. Relational Database (PostgreSQL)

| Variable | Default Value | Description |
|---|---|---|
| `AI_DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/rag_ai` | Asynchronous PostgreSQL connection string using `asyncpg`. Automatically converts standard `postgresql://` URIs if provided. |

---

## 3. Object & Document Storage

| Variable | Default Value | Description |
|---|---|---|
| `STORAGE_BACKEND` | `local` | Target storage provider: `local` (filesystem) or `s3` (S3-compatible object store). |
| `STORAGE_LOCAL_DIR` | `./storage` | Filesystem path for uploaded artifacts when `STORAGE_BACKEND=local`. |
| `OBJECT_STORAGE_ENDPOINT` | `None` | S3-compatible API endpoint URL (e.g., AWS S3, Cloudflare R2, MinIO). |
| `OBJECT_STORAGE_BUCKET` | `None` | Bucket identifier for raw documents and processing artifacts. |
| `OBJECT_STORAGE_ACCESS_KEY` | `None` | Access key credential for object storage. |
| `OBJECT_STORAGE_SECRET_KEY` | `None` | Secret key credential for object storage. |
| `OBJECT_STORAGE_REGION` | `us-east-1` | Cloud region for object storage bucket. |

---

## 4. Vector Database (Qdrant)

| Variable | Default Value | Description |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | Endpoint URL for the Qdrant vector database. |
| `QDRANT_API_KEY` | `None` | API key for managed Qdrant Cloud or secured clusters. |
| `QDRANT_COLLECTION_NAME` | `rag_chunks` | Primary collection name housing document chunk embeddings. |

---

## 5. Large Language Model (OpenAI-Compatible Spec)

| Variable | Default Value | Description |
|---|---|---|
| `LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible endpoint URL (OpenAI, Azure, vLLM, Ollama). |
| `LLM_API_KEY` | `None` | Authentication key for the target LLM provider. |
| `LLM_MODEL_NAME` | `gpt-4o-mini` | Model identifier string dispatched in inference requests. |
| `LLM_MAX_TOKENS` | `1024` | Default token ceiling reserved for generated answers. |
| `LLM_TEMPERATURE` | `0.1` | Sampling temperature (recommend low values for grounded synthesis). |
| `LLM_REQUEST_TIMEOUT_SECONDS` | `45` | Maximum timeout in seconds for LLM generation calls. |

---

## 6. Embedding & Cross-Encoder Models

| Variable | Default Value | Description |
|---|---|---|
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-base-en-v1.5` | Sentence-Transformers model used for dense vector embeddings. |
| `EMBEDDING_BATCH_SIZE` | `32` | Batch size for vector embedding computation. |
| `RERANKER_MODEL_NAME` | `BAAI/bge-reranker-base` | Cross-encoder model used for deep query-passage reranking. |

---

## 7. OCR & Ingestion Pipeline Settings

| Variable | Default Value | Description |
|---|---|---|
| `OCR_ENGINE` | `paddleocr` | OCR engine implementation (`paddleocr` or `tesseract`). |
| `OCR_RENDER_DPI` | `200` | Resolution for page rasterization prior to OCR. |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum direct multipart file upload ceiling in megabytes. |
| `PAGE_BATCH_SIZE` | `10` | Number of document pages processed per worker checkpoint batch. |
| `MAX_STAGE_RETRY_COUNT` | `3` | Maximum retry attempts for a failed page-batch task before poison-pill isolation. |

---

## 8. Hybrid Retrieval & Rank Fusion Tuning

| Variable | Default Value | Description |
|---|---|---|
| `RETRIEVAL_TOP_N_SEMANTIC` | `30` | Top candidates retrieved from dense vector search in Qdrant. |
| `RETRIEVAL_TOP_N_KEYWORD` | `30` | Top candidates retrieved from PostgreSQL lexical Full-Text Search. |
| `RETRIEVAL_TOP_M_FUSED` | `40` | Total candidates retained following Reciprocal Rank Fusion (RRF). |
| `RETRIEVAL_TOP_K_FINAL` | `8` | Final reranked context chunks injected into the synthesis prompt. |
| `RRF_K_CONSTANT` | `60` | Rank dampening constant $k$ applied during Reciprocal Rank Fusion. |

---

## 9. Background Worker Queue

| Variable | Default Value | Description |
|---|---|---|
| `WORKER_POLL_INTERVAL_SECONDS` | `2.0` | Polling frequency for the PostgreSQL-backed task queue. |
| `WORKER_CONCURRENCY` | `2` | Number of concurrent processing tasks per worker instance. |
