# 15 — Deployment Architecture

## 1. Explicit Separation: Prototype vs. Production

This separation is treated as a first-class design concern, not an afterthought — the project brief explicitly warns against claiming a free/small web service can production-process arbitrary 267 MB scanned documents. This document keeps the two stories distinct and never conflates them.

## 2. Prototype (SIH Demo) Deployment

| Component | Suggested Platform |
|---|---|
| Frontend | Vercel |
| Node.js Core API (`BACKEND`) | Render (or equivalent small web service) |
| FastAPI AI Service | Render (or equivalent small web service) |
| Job workers | Same Render service as FastAPI (a background worker process/dyno) or a second small Render service, depending on available plan tiers |
| PostgreSQL | A managed PostgreSQL provider (e.g., Render Postgres, Supabase, Neon — implementation choice, not mandated) |
| Vector DB | Qdrant Cloud (free/small tier) |
| Object storage | Any S3-compatible provider with a free/low tier (implementation choice) |
| LLM | External API via a configurable OpenAI-compatible endpoint — GTWY serving GPT-5 nano, per the team's current access |

**Constraints acknowledged for the prototype:**
- Limited compute/memory per service instance (e.g., ~512 MB–1 GB class web services).
- The SIH demo uses a **representative 8–10 MB data-heavy report**, not the 267 MB reference document, specifically because free/small-tier compute cannot be assumed to process the largest documents within a live-demo time budget. This is a demo-logistics decision, not an architectural limitation (see §4).
- A single worker process is sufficient for demo purposes; horizontal worker scaling is a production concern (§3).

## 3. Production Deployment (target, not required for the SIH demo)

| Component | Production Approach |
|---|---|
| Frontend | CDN-hosted static/SSR frontend (Vercel or equivalent scales natively) |
| Node.js Core API (`BACKEND`) | Horizontally scaled container/service behind a load balancer |
| FastAPI AI Service (API layer) | Horizontally scaled container/service, stateless (all state in Postgres/Qdrant/object storage) |
| Job workers | Independently scaled worker pool (separate deployment/replica count from the API layer), sized based on processing throughput needs; can scale up during bulk archival-digitization phases and down otherwise |
| PostgreSQL | Managed, production-tier PostgreSQL with backups, read replicas if needed |
| Vector DB | Qdrant Cloud production tier (or self-hosted Qdrant cluster) |
| Object storage | Production-grade object storage (S3 or equivalent) with lifecycle policies for intermediate-artifact cleanup |
| OCR/processing compute | Dedicated compute (potentially GPU-backed if OCR/embedding throughput demands it) separate from the API tier |
| LLM | Same configurable OpenAI-compatible interface; provider/model may be upgraded from GPT-5 nano as needs grow, via configuration only |
| Monitoring | Structured logs + metrics/alerting (implementation choice: e.g., hosted logging/APM provider) |
| Backups | Automated PostgreSQL backups; object storage versioning/retention policy |

## 4. Why 267 MB Is Not Architecturally Different From 8–10 MB

Because processing is **page-batched and asynchronous** (`04_DOCUMENT_PROCESSING_SPEC.md` §10, `14_ASYNC_PROCESSING.md`), peak memory per processing step is bounded by batch size, not total document size. A 267 MB document simply produces more page-batches and job-tasks, and takes proportionally longer wall-clock time (especially for OCR, which is the dominant cost for scanned content) — it does not require redesigning the pipeline. What *does* change between the two is:
- **Time budget:** a 267 MB scanned document may take substantially longer to fully process — unsuitable for a live, time-boxed demo, but entirely acceptable for an asynchronous production batch/ingestion pipeline.
- **Worker capacity needed to keep total pipeline throughput acceptable across many such documents** — a production concern addressed by scaling the worker pool independently (§3), not by changing the algorithm.
- **Storage/object-storage costs**, which scale roughly linearly and are a capacity-planning concern, not an architecture concern.

The documentation does not claim any specific throughput number (e.g., pages/minute) without empirical measurement — see `17_TESTING_STRATEGY.md` for how such numbers should eventually be produced.

## 5. Configuration-Driven Provider Choices

To keep prototype and production interchangeable without code changes, all external-service endpoints are environment-variable-driven (see `19_ENVIRONMENT_VARIABLES.md`): LLM base URL/API key/model name, Qdrant URL/API key, object storage endpoint/credentials/bucket, PostgreSQL connection strings (separate for Node.js Backend and AI schemas per `02_SYSTEM_ARCHITECTURE.md` §1's decision).

## 6. Local Development

- Docker Compose is used for local development: FastAPI service, worker process, local PostgreSQL, local Qdrant (Qdrant provides an official Docker image), and a local object-storage emulator (e.g., MinIO) — all swappable for their managed-cloud equivalents via env vars only.
- **Ollama** may optionally be run locally as an OpenAI-compatible LLM endpoint for offline development, satisfying the "configurable OpenAI-compatible LLM endpoint" requirement without requiring internet access or API cost during early development — this is explicitly a local-dev convenience, never assumed in production configuration or documentation elsewhere in this pack.
