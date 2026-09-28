# 14 — Asynchronous Task Processing Architecture

## 1. Architectural Imperative: Non-Blocking Execution

Document processing (multi-page OCR, layout tree construction, dense embedding generation, and vector indexing) along with multi-pass operations (iterative report compilation, topic clustering across collections) can take from seconds to several minutes depending on document length and visual complexity.

Synchronous HTTP request handling for these workloads is fragile, leads to gateway timeouts, and risks resource starvation. Consequently, all computationally heavy workloads are executed asynchronously as **durable, resumable background jobs**.

---

## 2. Durable Job Queue Architecture

The microservice employs a **PostgreSQL-native queue mechanism** (`SELECT ... FOR UPDATE SKIP LOCKED`):

```
API Request (Ingest / Reprocess / Report / Topic)
  │
  ▼
[FastAPI Route Handler]
  ├── Inserts record into `processing_jobs` table (status: `QUEUED`)
  ├── Writes stage tracking records (`VALIDATION`, `LAYOUT_EXTRACTION`, etc.)
  └── Returns HTTP 202 Accepted with `job_id`
  │
  ▼
[PostgreSQL Database: `processing_jobs`]
  │
  ├── Worker Process 1 (polls: SELECT ... FOR UPDATE SKIP LOCKED)
  ├── Worker Process 2 (concurrent worker scaling)
  └── Worker Process N
```

### Architectural Rationale
- **Zero Additional Infrastructure Overhead:** Eliminates the operational complexity of managing external brokers (such as Celery, RabbitMQ, or Redis) while providing immediate ACID transaction guarantees.
- **Concurrency & Contention-Free Polling:** `FOR UPDATE SKIP LOCKED` ensures multiple distributed worker instances can poll the job queue concurrently without race conditions or lock contention.
- **Durability & Resumability:** Job states, progress percentages, and stage checkpoints are transactional and survive worker restarts or service redeployments.

---

## 3. Worker Process Architecture

- **Independent Worker Lifecycles:** Workers run as dedicated worker processes, decoupled from the user-facing FastAPI HTTP request loop.
- **Horizontal Worker Scaling:** In production, worker instances can be scaled horizontally to match document ingestion volume independently from API gateway instances.
- **Decomposed Stage Tasks:** Large documents are partitioned into granular, page-batched tasks rather than monolithic document jobs:
  - Progress is transparently observable (`progress_current` vs. `progress_total`).
  - Unexpected worker crashes resume precisely from the last completed page batch rather than re-executing the entire document from page one.

---

## 4. End-to-End Document Processing Lifecycle

```
[UPLOADED]
   │
   ▼
[QUEUED]
   │
   ▼
[PROCESSING]
   │
   ├── 1. VALIDATION                (MIME sniffing & SHA-256 content hashing)
   ├── 2. LAYOUT_EXTRACTION         (PDF text parsing / OCR raster fallback)
   ├── 3. STRUCTURE_UNDERSTANDING   (PageIndex tree & table detection)
   ├── 4. STRUCTURED_FACTS          (Table parsing & fact extraction to Postgres)
   ├── 5. CHUNKING                  (Structure-aware semantic windowing)
   ├── 6. EMBEDDING                 (Dense vector generation)
   └── 7. INDEXING                  (Qdrant vector upsert & Postgres FTS indexing)
   │
   ▼
[READY] (or [FAILED] / [PARTIAL] upon unrecoverable error)
```

### Lifecycle State Definitions
- `QUEUED`: Job created and awaiting an available worker thread.
- `PROCESSING`: Job actively being handled by a worker across the defined sub-stages.
- `READY`: All pages and stages successfully parsed, stored, and indexed. Ready for querying.
- `PARTIAL`: Completed with non-fatal page-level exceptions (e.g., individual corrupted scanned pages skipped, with remaining content fully queryable).
- `FAILED`: Terminal processing failure (e.g., completely corrupt binary or unsupported encoding).

---

## 5. Resilient Retry Semantics & Poison-Pill Isolation

- **Selective Reprocessing (`POST /api/v1/documents/{document_id}/process`):** When retrying a failed or partially processed job, the system queries the stage audit logs and re-queues **only the incomplete or failed stages**, preserving already completed embeddings and parsed facts.
- **Poison-Pill Protection:** If a specific page repeatedly triggers exceptions during OCR or layout parsing, that single page is marked `FAILED` after reaching maximum retry attempts (configurable, default: 3). The worker records an error annotation for that page and proceeds with the rest of the document, preventing an isolated defective page from halting entire enterprise archives.

---

## 6. Unified Asynchronous Lifecycle Across Features

The PostgreSQL-backed job queue powers all long-running asynchronous workflows in the microservice:
1. **Document Ingestion & Version Processing**
2. **On-Demand Document Re-Extraction**
3. **Corpus Analytics & Topic Modeling Jobs**
4. **Multi-Section Grounded Report Drafting**

Each feature surfaces identical lifecycle contracts (`job_id`, `status`, `stage_details`, `progress_percentage`), providing a unified interface for consuming client applications.
