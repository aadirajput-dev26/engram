# 14 — Async Processing Architecture

## 1. Why Async Is Mandatory

Document processing (OCR, structure extraction, embedding) and multi-pass operations (report generation, topic analysis over large collections) can take from seconds to many minutes, especially for large scanned documents. Synchronous request/response is inappropriate — everything long-running is a **job** with persisted, resumable state.

## 2. Job Queue Design

> **Decision:** implement a PostgreSQL-backed job queue (a `processing_jobs`/`job_tasks` table with `SELECT ... FOR UPDATE SKIP LOCKED` polling by worker processes) rather than introducing Celery + Redis or another message broker.
>
> **Alternatives considered:**
> 1. Celery + Redis — rejected per the explicit project constraint to avoid unjustified extra infrastructure; also adds an operational dependency (Redis) with no capability this domain's job volume/throughput actually requires.
> 2. A managed cloud queue (e.g., SQS) — viable for production but introduces cloud-provider coupling not needed for the prototype and not clearly justified yet.
> 3. In-process background tasks only (e.g., FastAPI `BackgroundTasks`) — rejected as the sole mechanism because it does not survive process restarts and does not support horizontal worker scaling, both of which are required (large-document resumability, independent worker scaling per `02_SYSTEM_ARCHITECTURE.md`).
>
> **Reason for the chosen approach:** PostgreSQL is already a required dependency; a `SKIP LOCKED`-based queue is a well-understood, battle-tested pattern that supports multiple concurrent workers, durable retry state, and priority/ordering — sufficient for this domain's job volume (document counts in the hundreds/thousands, not millions of jobs/second). This keeps operational surface area minimal, in line with the project's explicit anti-over-engineering guidance. If job volume/throughput ever demands a dedicated broker, this is the documented upgrade path (see `15_DEPLOYMENT_ARCHITECTURE.md` production section).

## 3. Worker Architecture

- Workers are separate Python processes (can be the same codebase as the FastAPI app, run via a different entrypoint/command) that poll the job queue, claim a task, execute it, persist results, and mark it complete/failed.
- Workers scale independently from the FastAPI API process — in the prototype this may mean a single worker process; in production, multiple worker replicas (see `15_DEPLOYMENT_ARCHITECTURE.md`).
- Long-running document processing is decomposed into **per-stage, per-batch tasks** (not one monolithic task per document) so that:
  - Progress is observable at fine granularity (`ProcessingStageStatus.progress_current/total`, `09_DATA_MODELS.md`).
  - A crash/restart resumes from the last completed batch, not from scratch.
  - Multiple workers can, if useful, process different page-batches of the same large document in parallel (implementation detail, not required for v1, but the task decomposition supports it).

## 4. Document Processing Lifecycle

```
UPLOADED → QUEUED → PROCESSING
   → OCR (per page-batch; skipped/short-circuited per-page if native text is used)
   → STRUCTURE_EXTRACTION
   → DATA_EXTRACTION        (structured facts)
   → CHUNKING
   → EMBEDDING
   → INDEXING
→ READY

Failure states (can occur from any active stage): FAILED, PARTIAL
```

- `overall_status` is derived from the set of `stage` statuses: `READY` only when every required stage completed successfully for every page/batch; `PARTIAL` when some batches/stages succeeded and others failed (document is usable, but incompletely indexed — surfaced to the user); `FAILED` when a stage failed comprehensively (e.g., file unreadable at all).
- Each stage transition is persisted (`started_at`/`completed_at`) — this is the audit trail for both debugging and for the "resumable processing" requirement.

## 5. Retry Semantics

- Retrying a `FAILED`/`PARTIAL` job (`POST /api/v1/documents/{id}/process`) re-queues only the failed/incomplete stage-batches, identified from persisted per-batch stage status — never the whole pipeline, unless the caller explicitly requests `stages: ["ALL"]`.
- Each stage-batch task has a max retry count (configurable, e.g., 3) before being marked permanently `FAILED` for that batch, so a single corrupt page does not retry indefinitely and does not block the rest of a large document from completing (see `04_DOCUMENT_PROCESSING_SPEC.md` §11).

## 6. Other Async Job Types

The same job-queue mechanism (not a separate system) is reused for:
- Topic analysis jobs (`13_TOPIC_ANALYSIS.md`).
- Report generation jobs (`12_REPORT_GENERATION.md`).
- On-demand re-extraction jobs (`08_API_CONTRACTS.md` §6, when the extraction scope is large enough to warrant async handling).

This reuse (one job-queue implementation, multiple task types) is an explicit simplicity choice, avoiding duplicated async-orchestration code across features.

## 7. Status Visibility

All async operations expose a consistent status-polling shape (`job_id`, `overall_status`/`status`, stage/progress detail where applicable) so Node.js Backend (and ultimately the frontend) can implement a single generic "job status" UI pattern rather than bespoke polling per feature.
