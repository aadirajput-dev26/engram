# 08 — API Contracts (RAG Pipeline Microservice)

## 0. Conventions & Standards

- **Base URL Prefix:** All endpoints are versioned under `/api/v1`.
- **Authentication & Tenant Scoping:**
  - Header: `X-Api-Key: sk-engram-...`
  - The API key cryptographically resolves to the caller's authenticated tenant context (`org_id`, `workspace_id`).
  - **No Redundant Form Parameters:** Callers do not need to redundantly pass `org_id` or `workspace_id` in request payloads; the microservice automatically extracts and enforces tenant boundaries directly from the API key.
  - Requests missing or carrying invalid API keys return `401 Unauthorized`.
- **Response Format:** All JSON responses conform to standard Pydantic schemas.
- **Consistent Error Structure:**
  ```json
  {
    "error": {
      "code": "STRING_ERROR_CODE",
      "message": "Human-readable description of error",
      "details": {}
    }
  }
  ```
- **Idempotency:** Endpoints that create or trigger jobs accept an optional `Idempotency-Key` header to safely allow retries without duplicate processing.

---

## 1. Document Ingestion API

### `POST /api/v1/documents/ingest`
**Purpose:** Unified ingestion endpoint for all supported document media types and external sources.

**Authentication:** `X-Api-Key` required (resolves `org_id` and `workspace_id`).

**Request Format:** Multipart Form (`multipart/form-data`) or JSON (for URL links).

**Parameters:**
- `file`: (Binary, optional if submitting URL) The document file bytes.
- `url`: (String, optional if submitting file) URL to fetch and ingest document content.
- `document_type`: (Enum, optional) Declared document category: `pdf`, `docx`, `xlsx`, `csv`, `image`, `url`. If omitted, automatically inferred via MIME sniffing.
- `filename`: (String, optional) Target filename display override.
- `document_id`: (UUID, optional) If specified, registers this upload as a new version (`v2`, `v3`) of an existing document.
- `folder_id`: (UUID, optional) Logical folder placement within workspace.
- `content_hash`: (String, optional) Client-computed SHA-256 hash for immediate deduplication check.

**Response (`202 Accepted` or `200 OK`):**
```json
{
  "document_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "document_version_id": "a1b2c3d4-0000-1111-2222-333344445555",
  "job_id": "e4d3c2b1-9999-8888-7777-666655554444",
  "status": "QUEUED",
  "message": "Document accepted for asynchronous processing."
}
```
*Note: If the `content_hash` matches an existing, fully-processed document in the same workspace, the endpoint responds idempotently with `status: "ALREADY_PROCESSED"`.*

---

## 2. Document Status & Lifecycle APIs

### `GET /api/v1/documents/{document_id}/status`
**Purpose:** Poll processing progress and stage-level execution metrics for an ingested document.

**Response (`200 OK`):**
```json
{
  "document_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "document_version_id": "a1b2c3d4-0000-1111-2222-333344445555",
  "job_id": "e4d3c2b1-9999-8888-7777-666655554444",
  "overall_status": "READY",
  "progress_percentage": 100.0,
  "stage_details": [
    { "stage": "VALIDATION", "status": "COMPLETED", "details": "MIME type verified" },
    { "stage": "LAYOUT_EXTRACTION", "status": "COMPLETED", "details": "42 pages parsed" },
    { "stage": "STRUCTURED_FACTS", "status": "COMPLETED", "details": "128 facts stored" },
    { "stage": "CHUNKING_EMBEDDING", "status": "COMPLETED", "details": "164 chunks indexed in Qdrant" }
  ],
  "updated_at": "2026-09-29T01:00:00Z"
}
```

### `GET /api/v1/documents/{document_id}/chunks`
**Purpose:** Retrieve paginated, structure-aware chunks and layout metadata for a processed document.

**Query Parameters:**
- `page`: Page index (default: `1`).
- `limit`: Chunk page size (default: `50`, max: `100`).

**Response (`200 OK`):**
```json
{
  "document_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "total_chunks": 164,
  "page": 1,
  "limit": 50,
  "chunks": [
    {
      "chunk_id": "f8a1... ",
      "chunk_index": 0,
      "page_numbers": [1, 2],
      "section_path": "Executive Summary > Overview",
      "chunk_type": "paragraph",
      "text": "The organization achieved positive operating margin...",
      "char_count": 482
    }
  ]
}
```

### `POST /api/v1/documents/{document_id}/process`
**Purpose:** Re-trigger or resume processing for a document version that encountered a partial error or needs re-indexing.

**Request Body (`ReprocessRequest`):**
```json
{
  "stages": ["CHUNKING_EMBEDDING"],
  "document_version_id": "a1b2c3d4-0000-1111-2222-333344445555"
}
```

---

## 3. Query & Inference APIs

### `POST /api/v1/query`
**Purpose:** Execute an intelligent, grounded query across the workspace or selected documents. Automatically coordinates structured SQL, hybrid RAG, or dual-path synthesis.

**Request Body (`QueryRequest`):**
```json
{
  "query_text": "What was the operating revenue for Division Alpha in 2024 and why did it fluctuate?",
  "document_ids": ["7c9e6679-7425-40de-944b-e07fc1f90ae7"],
  "route_override": null,
  "top_k": 8
}
```
*(Note: `org_id` and `workspace_id` are automatically bound from the caller's API key).*

**Response (`200 OK`):**
```json
{
  "answer": "In FY2024, Division Alpha generated $142.5M in operating revenue [F1]. The fluctuation observed in Q3 was primarily attributed to temporary supply chain delays and logistical re-routing [C1].",
  "route_used": "HYBRID",
  "no_evidence": false,
  "confidence": 0.96,
  "citations": [
    {
      "citation_id": "F1",
      "type": "STRUCTURED_FACT",
      "document_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "document_title": "FY2024 Annual Financial Report",
      "page_number": 14,
      "fact_details": { "metric": "operating_revenue", "value": 142.5, "unit": "USD_MILLIONS", "period": "2024" }
    },
    {
      "citation_id": "C1",
      "type": "NARRATIVE_CHUNK",
      "document_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "document_title": "FY2024 Annual Financial Report",
      "page_number": 19,
      "section_path": "Operational Review > Supply Chain",
      "excerpt": "Operating margins in Q3 were impacted by external transit bottlenecks..."
    }
  ],
  "latency_ms": 780
}
```

---

## 4. Semantic Search API

### `POST /api/v1/search`
**Purpose:** Perform pure hybrid retrieval (dense vector + lexical FTS + cross-encoder reranking) without LLM answer generation. Used for search UIs and evidence discovery.

**Request Body (`SearchRequest`):**
```json
{
  "query_text": "supply chain risk factors",
  "document_ids": [],
  "top_k": 10,
  "min_score": 0.50
}
```

**Response (`200 OK`):**
```json
{
  "total_results": 10,
  "results": [
    {
      "chunk_id": "c1d2e3f4...",
      "document_id": "7c9e6679...",
      "page_numbers": [19],
      "section_path": "Risk Factors > Logistics",
      "snippet": "Supply chain operations experienced localized disruptions...",
      "score": 0.924,
      "retrieval_source": "HYBRID_FUSION"
    }
  ]
}
```

---

## 5. Collections & Groupings API

### `POST /api/v1/collections`
**Purpose:** Group documents into logical collections within a workspace for focused querying and analytics.

---

## 6. Planned Roadmap Endpoints

The following endpoints represent planned extensions specified in the roadmap:

### `POST /api/v1/topics` *(Roadmap)*
Initiates corpus-wide topic modeling and keyword distribution analysis (runs asynchronously). Status and results queried via `GET /api/v1/topics/{job_id}`.

### `POST /api/v1/reports/generate` *(Roadmap)*
Triggers automated multi-section report drafting based on evidence templates. Output retrieved via `GET /api/v1/reports/{job_id}`.

---

## 7. Standard HTTP Error Codes

| Status Code | Error Code | Description |
|---|---|---|
| `400` | `BAD_REQUEST` | Malformed parameters, unsupported file MIME type, or file size exceeds limits. |
| `401` | `UNAUTHORIZED` | Missing or invalid `X-Api-Key` header. |
| `403` | `FORBIDDEN` | Caller does not possess permissions for the requested workspace or document scope. |
| `404` | `NOT_FOUND` | Specified document or job identifier does not exist. |
| `409` | `CONFLICT` | Resource version mismatch or concurrent mutation conflict. |
| `422` | `UNPROCESSABLE_ENTITY` | Pydantic schema validation failure on request payload. |
| `500` | `INTERNAL_SERVER_ERROR` | Unhandled processing error during pipeline execution. |
