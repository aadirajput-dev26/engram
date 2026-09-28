# 15 — Deployment Architecture

## 1. Deployment Topology

The RAG Pipeline microservice is architected as a modular, containerized system where stateless API endpoints, asynchronous processing workers, and stateful datastores scale independently.

```
                           ┌───────────────────────────┐
                           │    Client Application     │
                           └─────────────┬─────────────┘
                                         │ HTTPS (X-Api-Key)
                                         ▼
                           ┌───────────────────────────┐
                           │    Ingress Load Balancer  │
                           └─────────────┬─────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
     ┌───────────────────────┐                       ┌───────────────────────┐
     │ FastAPI Microservice  │                       │ FastAPI Microservice  │
     │     (API Node 1)      │                       │     (API Node 2)      │
     └───────────┬───────────┘                       └───────────┬───────────┘
                 │                                               │
                 ├───────────────────────┬───────────────────────┤
                 ▼                       ▼                       ▼
     ┌───────────────────────┐ ┌───────────────────┐ ┌───────────────────────┐
     │ PostgreSQL 16+        │ │ Qdrant Vector DB  │ │ S3-Compatible Storage │
     │ - Processing Jobs     │ │ - HNSW Collection │ │ - Raw Files           │
     │ - Relational Metadata │ │ - Filter Payload  │ │ - Page Images         │
     │ - FTS GIN Index       │ │   (org/workspace) │ │ - Rendered Artifacts  │
     │ - Extracted Facts     │ └─────────▲─────────┘ └───────────▲───────────┘
     └───────────▲───────────┘           │                       │
                 │                       │                       │
                 ├───────────────────────┴───────────────────────┤
                 │                                               │
     ┌───────────┴───────────┐                       ┌───────────┴───────────┐
     │  Background Worker 1  │                       │  Background Worker N  │
     │  (OCR, Chunking,      │                       │  (Horizontally        │
     │   Embeddings, Report) │                       │   Scalable Workers)   │
     └───────────┬───────────┘                       └───────────┬───────────┘
                 │                                               │
                 └───────────────────────┬───────────────────────┘
                                         │ HTTPS
                                         ▼
                           ┌───────────────────────────┐
                           │  Configurable LLM API     │
                           │  (OpenAI-Compatible Spec) │
                           └───────────────────────────┘
```

---

## 2. Infrastructure Tiers

### 2.1 API Tier (FastAPI)
- **Role:** Handles incoming HTTP traffic, authenticates requests via `X-Api-Key`, translates query plans, triggers async jobs, and serves real-time query/search requests.
- **Scaling:** Stateless; horizontally scalable behind standard layer-7 load balancers (AWS ALB, NGINX, Cloudflare).

### 2.2 Worker Tier (Async Runners)
- **Role:** Dequeues tasks from PostgreSQL using `SELECT ... FOR UPDATE SKIP LOCKED`. Executes CPU- and memory-intensive OCR, layout parsing, chunking, dense embeddings, and multi-pass report drafting.
- **Scaling:** Scales horizontally based on queue depth. Workers can be deployed on CPU-optimized or GPU-accelerated instances (to accelerate local OCR and embedding pipelines).

### 2.3 Datastores
- **Relational (PostgreSQL):** Stores multi-tenant schemas (`organizations`, `workspaces`, `api_keys`), document catalogs, chunk text with full-text search GIN indices, and extracted facts.
- **Vector DB (Qdrant):** Stores high-dimensional dense embeddings with indexed payloads (`org_id`, `workspace_id`, `document_id`) for sub-50ms approximate nearest neighbor (ANN) retrieval.
- **Object Storage (S3 / R2 / MinIO):** Stores raw binaries, rendered page rasters, and generated DOCX/PDF export files.

---

## 3. Deployment Environments

| Component | Development / Evaluation | Enterprise Production |
|---|---|---|
| **API Nodes** | 1 Container (Docker / Local) | Multi-replica containerized deployment (Kubernetes / ECS) |
| **Worker Nodes** | 1 Worker process | Auto-scaling worker cluster based on processing backlog |
| **Relational DB** | Local PostgreSQL 16 Container | Managed High-Availability PostgreSQL (RDS / Cloud SQL) |
| **Vector Engine** | Local Qdrant Container | Managed Qdrant Cloud or multi-node Qdrant cluster |
| **Object Store** | Local MinIO Container | AWS S3, Cloudflare R2, or Google Cloud Storage |
| **LLM Provider** | OpenAI / Ollama / Local Proxy | Enterprise OpenAI endpoint, Azure OpenAI, or self-hosted vLLM |

---

## 4. Scalability Principles for Heavy Document Archives

- **Bounded Memory via Streaming:** Because processing is page-batched, peak memory is strictly bounded by the page batch size (typically 10–20 pages), not total document size. A 500-page archive consumes the same peak memory footprint as a 10-page document.
- **Stateless Restarts:** Every completed page batch commits its text and vector representations to storage immediately. If a worker instance is preempted or terminated by an auto-scaler, processing resumes at the batch checkpoint upon restart.
- **Decoupled LLM Latency:** Embedding generation runs in-process or via high-throughput endpoints; query synthesis employs streaming tokens to minimize time-to-first-token (TTFT) for consuming client applications.

---

## 5. Local Development Environment

Developers can launch the complete microservice infrastructure locally using Docker Compose:

```yaml
version: '3.8'
services:
  api:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - postgres
      - qdrant

  worker:
    build: .
    command: python -m app.workers.document_worker
    env_file: .env
    depends_on:
      - postgres
      - qdrant

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: rag_service
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
```
