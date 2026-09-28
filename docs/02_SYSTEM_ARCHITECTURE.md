# 02 — System Architecture

## 1. High-Level Diagram (conceptual)

```
                        ┌─────────────────────┐
                        │  Client Application │
                        │ (Web, Mobile, etc.) │
                        └──────────┬───────────┘
                                   │ HTTPS + X-Api-Key
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
                 │ (OpenAI-compatible)   │
                 └───────────────────────┘
```

> **Note:** For a detailed breakdown of the database entities and relationships inside the PostgreSQL schema, refer to `rag_er_diagram.md`.

## 2. Logical Components

### 2.1 Client Application (The Consumer)
The client application is any external system that integrates with the RAG Pipeline. It is responsible for:
- Authenticating its own end-users.
- Managing its own organizations, workspaces, and folder structures.
- Enforcing Role-Based Access Control (RBAC) and permissions.
- Orchestrating calls to the FastAPI service by passing explicit API Keys that resolve to secure tenant contexts.

The Client Application does **not** perform OCR, parsing, embedding, retrieval, or LLM calls directly. It delegates all document intelligence workloads to the FastAPI service.

### 2.2 FastAPI AI / Document Intelligence Service (RAG Pipeline)
This standalone microservice is responsible for the entire AI lifecycle:
- Document ingestion, validation, and classification.
- OCR (scanned) / parsing (digital) content extraction.
- Structure understanding (pages, sections, subsections, tables) using hierarchical modeling.
- Structured fact extraction into its own PostgreSQL tables.
- Structure-aware chunking, embeddings, vector indexing (Qdrant) and keyword indexing (PostgreSQL full-text search).
- Hybrid retrieval, reranking, and RAG answer generation.
- Query routing (structured / RAG / hybrid).
- Citation attachment and answer validation.
- AI-assisted report drafting (data retrieval + section generation + source attachment).
- Async job orchestration for all of the above.

The FastAPI microservice does **not**:
- Authenticate end-users.
- Store user/organization identity as the source of truth (it relies on the Client Application to manage identity).

## 3. Cross-Service Authentication & Authorization

The FastAPI service does not authenticate end users directly, nor does it perform complex RBAC evaluations. The design is strictly API-Key based:

1. **Authentication:** The Client Application authenticates to FastAPI using a secure API key (`X-Api-Key` header). This proves the request came from a trusted tenant.
2. **Implicit Tenant Context:** The API key securely resolves to a specific `workspace_id` and `org_id` within the FastAPI database.
3. **Data Isolation:** FastAPI uses this resolved context to apply a **native filter** at the data-access layer (e.g., `WHERE workspace_id = ...`) for all database and vector store queries, ensuring absolute data isolation between tenants.

## 4. Data Ownership Summary

| Data | Store |
|---|---|
| Processing jobs & status | AI PostgreSQL schema |
| Extracted structured facts | AI PostgreSQL schema |
| Pages, sections, chunks, tables (metadata) | AI PostgreSQL schema |
| Chunk embeddings | Qdrant Vector DB |
| Raw uploaded files & processing intermediates | Object Storage (S3-compatible) |
| Citations / evidence trails for AI answers | AI PostgreSQL schema |

## 5. Deployment Topology

The service is designed to be deployed as a highly scalable microservice stack.
- **API Server:** Horizontally scalable FastAPI application (Dockerized).
- **Relational DB:** Managed PostgreSQL instance.
- **Vector DB:** Qdrant Cloud or self-hosted Qdrant cluster.
- **Storage:** AWS S3, Cloudflare R2, or MinIO.

## 6. Reusability Boundary

The FastAPI service is architected as a general **Document Intelligence / RAG Engine** that can serve any industry:

- **Reusable core** (domain-agnostic): ingestion, OCR, structure understanding, chunking, embeddings, hybrid retrieval, reranking, query routing framework, citation/validation framework, async job engine.
- **Domain-specific layer** (swappable): structured-fact extraction schemas, report templates, and topic-analysis tuning can be swapped depending on the Client Application's industry (e.g., healthcare, legal, or mining).
