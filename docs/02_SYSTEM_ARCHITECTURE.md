# 02 — System Architecture

## 1. High-Level Diagram (conceptual)

```
                        ┌─────────────────────┐
                        │      Frontend        │
                        │ (existing; VERIFY)   │
                        └──────────┬───────────┘
                                   │ HTTPS (user session/JWT)
                                   ▼
                        ┌─────────────────────┐
                        │   Node.js Core API (`BACKEND`)   │
                        │ (existing, extended) │
                        │  - Auth / RBAC       │
                        │  - Organizations     │
                        │  - Workspaces        │
                        │  - Documents (CRUD)  │
                        │  - Reports (CRUD)    │
                        │  - Analytics (proxy) │
                        │  - PostgreSQL (app)  │
                        └──────────┬───────────┘
                                   │ Internal HTTPS
                                   │ + X-Api-Key header (see §4)
                                   ▼
                        ┌─────────────────────────────┐
                        │  FastAPI AI / Document       │
                        │  Intelligence Service (new)  │
                        │  - Ingestion & OCR            │
                        │  - Structure understanding    │
                        │  - Structured extraction      │
                        │  - Chunking & embeddings      │
                        │  - Hybrid retrieval + rerank  │
                        │  - Query router (SQL/RAG)     │
                        │  - Citation & validation       │
                        │  - Topic/word-cloud analysis   │
                        │  - Report drafting              │
                        └───┬─────────┬──────────┬───────┘
                            │         │          │
                 ┌──────────▼──┐ ┌────▼─────┐ ┌──▼─────────────┐
                 │ PostgreSQL   │ │  Qdrant   │ │ Object Storage │
                 │ (AI-domain:  │ │ (vectors) │ │ (raw files +   │
                 │ facts, jobs, │ │           │ │ intermediate   │
                 │ chunks meta) │ │           │ │ artifacts)     │
                 └──────────────┘ └───────────┘ └────────────────┘
                            │
                 ┌──────────▼───────────┐
                 │ Configurable LLM API  │
                 │ (OpenAI-compatible;   │
                 │  e.g. GTWY/GPT-5 nano)│
                 └───────────────────────┘
```

> **Decision:** Two separate PostgreSQL logical schemas/databases — one owned by Node.js Backend (identity/org/workspace/document metadata/report metadata), one owned by FastAPI (processing jobs, extracted structured facts, chunk/page/section metadata, citations). They may live on the same physical PostgreSQL instance to reduce prototype infra cost, but must be logically separated (separate schemas) so ownership stays clear. **Alternatives considered:** single shared schema (rejected — blurs ownership and creates migration coupling between two independently deployed services). **Reason:** independent deployability and clear ownership outweigh the minor duplication of `document_id`/`workspace_id` references.

## 2. Services

### 2.1 Node.js Core API (`BACKEND`) (existing, extended — not rewritten)
Owns:
- Authentication (session/JWT — **VERIFY AGAINST EXISTING REPOSITORY**).
- Organization, Workspace, Folder, Document metadata (existing hierarchy, extended per `10_MULTI_TENANCY_RBAC.md`).
- RBAC/capability enforcement for all end-user-facing actions.
- Report metadata (title, status, approvals) and final report file storage/retrieval.
- Proxying/orchestrating calls to the FastAPI service on behalf of authenticated, authorized users, passing explicit tenant context (org_id, workspace_id) in the request body.

Node.js Backend does **not** perform OCR, parsing, embedding, retrieval, or LLM calls directly. It delegates all of that to the FastAPI service.

### 2.2 FastAPI AI / Document Intelligence Service (new)
Owns:
- Document ingestion, validation, classification.
- OCR (scanned) / parsing (digital) content extraction.
- Structure understanding (pages, sections, subsections, tables) — PageIndex-style hierarchical modeling where useful.
- Structured fact extraction into its own PostgreSQL tables.
- Structure-aware chunking, embeddings, vector indexing (Qdrant) and keyword indexing (PostgreSQL full-text search — see `05_RETRIEVAL_AND_RERANKING.md` §2 for the decision rationale).
- Hybrid retrieval, reranking, and RAG answer generation.
- Query routing (structured / RAG / hybrid).
- Citation attachment and answer validation.
- Topic identification / word-cloud analysis.
- AI-assisted report drafting (data retrieval + section generation + source attachment).
- Async job orchestration for all of the above (see `14_ASYNC_PROCESSING.md`).

FastAPI does **not**:
- Authenticate end users.
- Decide what a user is allowed to see beyond enforcing the scope it is given.
- Store user/org/workspace identity as the source of truth (it may cache `org_id`/`workspace_id`/`document_id` references for its own indexing, but Node.js Backend remains authoritative).

### 2.3 Frontend
Existing frontend (**VERIFY AGAINST EXISTING REPOSITORY** for framework/specifics). Talks only to Node.js Backend. Never calls FastAPI directly. This keeps a single authentication/authorization boundary at the edge.

## 3. Why a Separate FastAPI Service (not an Node.js Backend rewrite)

- **Decision:** Introduce a new Python/FastAPI microservice for all AI/document-intelligence work; keep Node.js Backend as-is for business/application logic.
- **Alternatives considered:**
  1. Implement RAG/OCR/embeddings in Node.js within Node.js Backend. Rejected — the required ecosystem (PyMuPDF, PaddleOCR, sentence-transformers, rerankers, BM25/NLP tooling) is materially stronger and more transparent in Python; forcing this into Node would mean wrapping Python tools via subprocess anyway.
  2. Rewrite the whole application in FastAPI. Explicitly rejected by the project brief — the existing Node.js Backend app is not to be discarded.
- **Reason:** Clean separation of concerns, independent scalability (AI workloads are CPU/GPU/memory heavy and bursty; core business API is not), and it lets the AI engine be reused across future integrations without dragging in the Node.js Backend app.

## 4. Cross-Service Authentication & Authorization

The FastAPI service does not authenticate end users directly, nor does it perform complex RBAC evaluations. The design:

1. **Service-to-service authentication:** Node.js Backend authenticates to FastAPI using a static shared API key (`AI_SERVICE_API_KEY`, see `19_ENVIRONMENT_VARIABLES.md`), sent as the `X-Api-Key` header on every request. This proves the request came from the trusted Node.js Backend backend, not from an arbitrary client.
2. **Explicit Tenant Context:** For every request that touches user data, Node.js Backend explicitly passes the tenant context (e.g., `org_id`, `workspace_id`, `document_ids`) in the JSON payload or query parameters.
3. **Data Isolation:** FastAPI uses these passed parameters to apply a **native filter** at the data-access layer (e.g., `WHERE org_id = ... AND workspace_id = ...`) for all database and vector store queries, ensuring data isolation.
4. **Trust Boundary:** Because the request carries the `X-Api-Key`, FastAPI implicitly trusts the tenant parameters provided by Node.js Backend. Node.js Backend remains authoritative for all RBAC checks (e.g., verifying if the user has "documents.read" permission before proxying the call to FastAPI).

> **Decision:** Single shared API key with explicit tenant context in payloads. **Alternatives considered:** (a) Per-request JWT scope tokens — rejected as overly complex for a closed-network microservice pattern where Node.js Backend is already fully trusted. (b) Passing user sessions — rejected, because that couples FastAPI to Node.js Backend's session/auth format. **Reason:** The single `X-Api-Key` approach significantly simplifies both the Node.js Backend and FastAPI implementations while maintaining strong data isolation, as long as Node.js Backend remains fully responsible for RBAC.

See `16_SECURITY.md` for full threat modeling and `10_MULTI_TENANCY_RBAC.md` for the underlying permission model.

## 5. Data Ownership Summary

| Data | Owner | Store |
|---|---|---|
| Users, Orgs, Workspaces, Folders, Document records (identity/metadata), RBAC | Node.js Backend | Node.js Backend PostgreSQL schema |
| Report metadata, approvals, final report files | Node.js Backend | Node.js Backend PostgreSQL schema + object storage |
| Processing jobs & status | FastAPI | AI PostgreSQL schema |
| Extracted structured facts (production, targets, etc.) | FastAPI | AI PostgreSQL schema |
| Pages, sections, chunks, tables (metadata) | FastAPI | AI PostgreSQL schema |
| Chunk embeddings | FastAPI | Qdrant |
| Raw uploaded files & processing intermediates | Shared, but written only by the party that produced them | Object storage (bucket/prefix conventions in `04_DOCUMENT_PROCESSING_SPEC.md`) |
| Citations / evidence trails for AI answers and generated report sections | FastAPI | AI PostgreSQL schema |

## 6. Deployment Topology (prototype)

See `15_DEPLOYMENT_ARCHITECTURE.md` for full detail. Summary: Vercel (frontend), Render (Node.js Backend), Render/equivalent (FastAPI), managed PostgreSQL, Qdrant Cloud, external LLM API. Production topology separates out object storage, a scalable worker pool, and dedicated OCR/processing compute.

## 7. Reusability Boundary

The FastAPI service is architected as a general **Document Intelligence / RAG Engine** with a domain-specific extraction layer:

- **Reusable core** (organization-agnostic): ingestion, OCR, structure understanding, chunking, embeddings, hybrid retrieval, reranking, query routing framework, citation/validation framework, async job engine.
- **Domain-specific layer** (mining/geological/production-report specific, swappable): structured-fact extraction schemas (mine, subsidiary, coal grade, production/target/achievement, dispatch), report templates, topic-analysis vocabulary tuning.

This boundary is enforced by keeping domain extraction schemas and prompt templates in clearly separated modules (see `06_STRUCTURED_DATA_EXTRACTION.md` and code organization guidance in `18_IMPLEMENTATION_ROADMAP.md`), not by building a generic no-code platform.
