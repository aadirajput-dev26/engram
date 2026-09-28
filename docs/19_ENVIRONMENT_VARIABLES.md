# 19 — Environment Variables

All values below are variable **names and semantics**. No real secret values are ever placed in this file, in `.env.example`, or in source control.

## 1. Service Identity / Networking

| Variable | Used by | Description |
|---|---|---|
| `SERVICE_ENV` | Both | `local \| staging \| production` |
| `AI_SERVICE_BASE_URL` | Node.js Backend | Base URL Node.js Backend uses to reach the FastAPI service |
| `AI_SERVICE_API_KEY` | Both | Shared API key sent by Node.js Backend as X-Api-Key header (see `16_SECURITY.md` §3) |

## 2. Database

| Variable | Used by | Description |
|---|---|---|
| `EXPRESS_DATABASE_URL` | Node.js Backend | Node.js Backend-owned PostgreSQL schema connection string — **VERIFY AGAINST EXISTING REPOSITORY** for current variable name |
| `AI_DATABASE_URL` | FastAPI | AI-owned PostgreSQL schema connection string (may point at the same physical instance, different schema — see `02_SYSTEM_ARCHITECTURE.md` §1) |

## 3. Object Storage

| Variable | Used by | Description |
|---|---|---|
| `OBJECT_STORAGE_ENDPOINT` | FastAPI (+ Node.js Backend if it generates pre-signed upload URLs) | S3-compatible endpoint URL |
| `OBJECT_STORAGE_BUCKET` | Both | Bucket name for raw documents and processing intermediates |
| `OBJECT_STORAGE_ACCESS_KEY` | Both | Access key |
| `OBJECT_STORAGE_SECRET_KEY` | Both | Secret key |
| `OBJECT_STORAGE_REGION` | Both | Region, if applicable to the provider |

## 4. Vector Database

| Variable | Used by | Description |
|---|---|---|
| `QDRANT_URL` | FastAPI | Qdrant endpoint (cloud or self-hosted) |
| `QDRANT_API_KEY` | FastAPI | Qdrant API key |
| `QDRANT_COLLECTION_NAME` | FastAPI | Single shared collection name (see `05_RETRIEVAL_AND_RERANKING.md` §3 decision) |

## 5. LLM Provider (configurable, OpenAI-compatible)

| Variable | Used by | Description |
|---|---|---|
| `LLM_BASE_URL` | FastAPI | OpenAI-compatible base URL (e.g., GTWY endpoint, OpenAI, or local Ollama for dev) |
| `LLM_API_KEY` | FastAPI | API key for the configured provider |
| `LLM_MODEL_NAME` | FastAPI | Model identifier (e.g., the GPT-5 nano model string as exposed by the provider) |
| `LLM_MAX_TOKENS` | FastAPI | Default max output tokens per generation call |
| `LLM_TEMPERATURE` | FastAPI | Default temperature (recommend low, e.g., 0–0.2, for factual generation tasks) |
| `LLM_REQUEST_TIMEOUT_SECONDS` | FastAPI | Timeout for LLM API calls |

> The LLM provider must never be hard-coded in application code; every LLM client call goes through a single configurable client built from these variables (`02_SYSTEM_ARCHITECTURE.md` §... / `09_DATA_MODELS.md` generation module).

## 6. Embeddings & Reranking (self-hosted, in-process)

| Variable | Used by | Description |
|---|---|---|
| `EMBEDDING_MODEL_NAME` | FastAPI | sentence-transformers model identifier (default suggested: `BAAI/bge-base-en-v1.5`) |
| `EMBEDDING_BATCH_SIZE` | FastAPI | Batch size for embedding computation |
| `RERANKER_MODEL_NAME` | FastAPI | Cross-encoder reranker model identifier (default suggested: `BAAI/bge-reranker-base`) |

## 7. OCR / Document Processing

| Variable | Used by | Description |
|---|---|---|
| `OCR_ENGINE` | FastAPI | `paddleocr` (default) — configurable in case of future engine swap |
| `OCR_RENDER_DPI` | FastAPI | Page render DPI for OCR (default suggested 200–300) |
| `MAX_UPLOAD_SIZE_MB` | Both | Max direct-upload file size before requiring pre-signed/object-storage-first upload |
| `PAGE_BATCH_SIZE` | FastAPI | Number of pages processed per batch/task (`04_DOCUMENT_PROCESSING_SPEC.md` §10) |
| `MAX_STAGE_RETRY_COUNT` | FastAPI | Max retries per failed stage-batch before marking permanently `FAILED` |

## 8. Retrieval Tuning

| Variable | Used by | Description |
|---|---|---|
| `RETRIEVAL_TOP_N_SEMANTIC` | FastAPI | Semantic candidates before fusion (default suggested 30) |
| `RETRIEVAL_TOP_N_KEYWORD` | FastAPI | Keyword candidates before fusion (default suggested 30) |
| `RETRIEVAL_TOP_M_FUSED` | FastAPI | Fused candidates before reranking (default suggested 40) |
| `RETRIEVAL_TOP_K_FINAL` | FastAPI | Final chunks passed to context selection (default suggested 8–12) |
| `RRF_K_CONSTANT` | FastAPI | RRF fusion constant (default suggested 60) |

## 9. Topic Analysis

| Variable | Used by | Description |
|---|---|---|
| `TOPIC_MODEL_BACKEND` | FastAPI | `lda` (default) or `bertopic` (see `13_TOPIC_ANALYSIS.md` §3) |
| `TOPIC_ASYNC_THRESHOLD_DOCS` | FastAPI | Document count above which topic analysis always runs async (default suggested 20) |

## 10. Job Queue / Workers

| Variable | Used by | Description |
|---|---|---|
| `WORKER_POLL_INTERVAL_SECONDS` | FastAPI worker | Polling interval for the Postgres-backed job queue |
| `WORKER_CONCURRENCY` | FastAPI worker | Number of concurrent tasks a single worker process handles |

## 11. Local Development Only

| Variable | Used by | Description |
|---|---|---|
| `USE_LOCAL_OLLAMA` | FastAPI (local dev) | If true, `LLM_BASE_URL` points at a local Ollama instance — never set in staging/production configuration |

## 12. Guidance for Coding Agents

- Every new external dependency (provider, model, threshold) introduced during implementation must be exposed as an environment variable here, with a corresponding entry added to this document and to `.env.example` — never hard-coded as a literal in application code.
- Secrets (`*_API_KEY`, `*_SECRET_KEY`, `*_SECRET`) must never have real values committed anywhere in the repository.
