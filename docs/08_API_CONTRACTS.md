# 08 — API Contracts (FastAPI AI / Document Intelligence Service)

## 0. Conventions

- All endpoints are prefixed `/api/v1` (versioned from day one).
- All endpoints require:
  - Header `X-Api-Key: <AI_SERVICE_API_KEY>` — proves the caller is the trusted Node.js Backend backend.
  - Requests missing or failing this check return `401 Unauthorized`.
- All request/response bodies are Pydantic models (see `09_DATA_MODELS.md`); FastAPI's automatic OpenAPI schema is the source of truth for exact field types, generated from these models — this document specifies intent, field presence, and semantics, not a hand-duplicated JSON schema.
- Errors follow a consistent envelope:
  ```json
  { "error": { "code": "STRING_ERROR_CODE", "message": "human readable", "details": {} } }
  ```
- Idempotency: endpoints that create a resource accept an optional `Idempotency-Key` header; replaying the same key returns the original result rather than creating a duplicate (important for document ingestion retries from Node.js Backend).

## 1. `POST /api/v1/documents/ingest`

**Purpose:** register a new document (or new version of an existing document) for processing.

**Request (`DocumentIngestRequest`):**
- `org_id`, `workspace_id`, `folder_id` (from scope/context)
- `document_id` (optional — if provided, this is a new version of an existing document)
- `file_ref`: object-storage reference (bucket/key) OR a direct multipart upload for small files
- `filename`, `declared_mime_type`
- `content_hash` (client-computed, verified server-side)
- `uploaded_by_user_id`

**Response (`DocumentIngestResponse`):**
- `document_id`, `document_version_id`, `job_id`, `status: "QUEUED"` (or `"ALREADY_PROCESSED"` if `content_hash` matches an existing ready version — idempotent short-circuit, see `04_DOCUMENT_PROCESSING_SPEC.md` §8)

**Errors:** `400` invalid file type/size, `409` content hash mismatch with declared version, `422` schema validation failure.

## 2. `GET /api/v1/documents/{document_id}/status`

**Purpose:** poll processing status.

**Response (`ProcessingStatusResponse`):**
- `document_id`, `document_version_id`, `job_id`
- `overall_status`: one of the lifecycle states in `14_ASYNC_PROCESSING.md` (`UPLOADED, QUEUED, PROCESSING, OCR, STRUCTURE_EXTRACTION, DATA_EXTRACTION, CHUNKING, EMBEDDING, INDEXING, READY, FAILED, PARTIAL`)
- `stage_details[]`: per-stage status, progress (e.g., pages completed/total), error message if failed
- `updated_at`

## 3. `POST /api/v1/documents/{document_id}/process`

**Purpose:** explicitly (re)trigger processing — e.g., retry a `FAILED`/`PARTIAL` job, or re-run a specific stage after a fix.

**Request (`ReprocessRequest`):**
- `stages`: optional list restricting reprocessing to specific stages (e.g., `["DATA_EXTRACTION"]`); omitted = resume from the first failed/incomplete stage.
- `document_version_id`: which version to reprocess (defaults to latest).

**Response:** same shape as ingest response (`job_id`, `status`).

**Authorization:** requires `documents.upload` or an equivalent reprocessing capability.

## 4. `POST /api/v1/query`

**Purpose:** the AI-based query/response system (structured / RAG / hybrid).

**Request (`QueryRequest`):**
- `query_text`
- `scope`: `{org_id, workspace_id, document_ids?: []}` (from the caller's granted scope — Node.js Backend fills this from the scope token; FastAPI re-validates it matches the token)
- `route_override`: optional (`structured|rag|hybrid`) for debugging/testing; default is auto-classification
- `top_k`: optional override for retrieval depth
- `conversation_id`: optional, for multi-turn context (see note below)

**Response (`QueryResponse`):**
- `answer`
- `route_used`: `structured|rag|hybrid`
- `no_evidence`: bool
- `citations[]`: `{citation_id, document_id, document_name, page_number, section_path, chunk_id?, fact_id?}`
- `structured_evidence[]`: raw fact rows used, if any
- `confidence`
- `latency_ms`

**Note on multi-turn:** conversational follow-up handling (resolving pronouns/context across turns) is **not specified in detail here** — the problem statement does not explicitly require multi-turn chat; the field exists for forward compatibility but v1 may treat each query independently. Marked as an open item in `18_IMPLEMENTATION_ROADMAP.md`.

**Authorization:** requires `ai.query` capability plus `documents.read` on the resolved scope.

## 5. `POST /api/v1/search`

**Purpose:** lower-level retrieval-only endpoint (no LLM answer generation) — useful for a "search results" UI distinct from the conversational assistant, and for debugging retrieval quality.

**Request (`SearchRequest`):** `query_text`, `scope`, `top_k`, `filters?` (metric/mine/period/date-range hints).

**Response (`SearchResponse`):** ranked list of `RetrievalResult` (chunk-level: `chunk_id`, `document_id`, `page_number`, `section_path`, `snippet`, `score`).

## 6. `POST /api/v1/extract`

**Purpose:** on-demand structured extraction for a specific document/page range (e.g., "re-extract facts from this table the user just flagged as incorrect"), distinct from the automatic pipeline extraction run during ingestion.

**Request (`ExtractRequest`):** `document_id`, `document_version_id`, `page_range?`, `table_id?`.

**Response (`ExtractResponse`):** list of `ExtractedFact` produced/updated.

## 7. `POST /api/v1/topics`

**Purpose:** trigger topic identification / word-cloud analysis over a document collection.

**Request (`TopicAnalysisRequest`):** `scope` (`org_id`, `workspace_id`, `document_ids[]` or "all in workspace"), `method_options?` (e.g., number of topics).

**Response (`TopicAnalysisResponse`):** `job_id`, `status` — this is an **asynchronous** endpoint for non-trivial collections (see `13_TOPIC_ANALYSIS.md`); result is retrieved via a corresponding status/result endpoint, e.g. `GET /api/v1/topics/{job_id}`.

## 8. `GET /api/v1/topics/{job_id}`

**Response (`TopicResult`):** `keywords[]` (term, score), `topics[]` (topic label/id, top terms, representative document/chunk references), `word_cloud_data[]` (term, frequency, normalized weight), `entities[]` (named entities with counts).

## 9. `POST /api/v1/reports/generate`

**Purpose:** AI-assisted report generation.

**Request (`ReportGenerateRequest`):** `scope`, `report_type` (extensible enum, e.g., `production_summary`, `parliamentary_response_draft`, `custom`), `parameters` (mines/subsidiaries/periods/question text depending on `report_type`), `output_format` (`docx|pdf`).

**Response:** `job_id`, `status` (asynchronous — report generation involves multiple retrieval/validation passes; see `12_REPORT_GENERATION.md`). Result retrieved via `GET /api/v1/reports/{job_id}` returning the generated file reference (object storage) plus the full evidence/citation trail used, which Node.js Backend persists as the report's metadata.

## 10. Common Error Codes

| Code | Meaning |
|---|---|
| `INVALID_SCOPE` | Scope token does not grant access to the requested resource |
| `UNSUPPORTED_FILE_TYPE` | File type not in the supported list |
| `DOCUMENT_NOT_READY` | Query/extract/report requested against a document still processing |
| `UNSUPPORTED_QUERY` | Structured query plan did not map to any known template |
| `NO_EVIDENCE_FOUND` | Not strictly an error — a valid, explicit response state (HTTP 200, `no_evidence: true`) |
| `PROCESSING_FAILED` | Terminal failure of a processing job/stage |
