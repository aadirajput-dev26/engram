# 18 — Implementation Roadmap & Milestones

This document outlines the phased engineering milestones for the RAG Pipeline microservice, defining core platform capabilities, active deliverables, and planned roadmap extensions.

---

### Phase 0 — Microservice Scaffolding & Foundations
- **Objective:** Establish the modular FastAPI service architecture with clean domain separation, asynchronous database sessions, and configuration management.
- **Key Deliverables:**
  - FastAPI application structure (`app/core`, `app/api/v1`, `app/models`, `app/services`, `app/workers`).
  - Asynchronous SQLAlchemy database engine with Alembic migrations.
  - Configuration management via Pydantic Settings (`app/core/config.py`).
  - Structured logging and standard HTTP error envelopes.

---

### Phase 1 — Scoped Authentication & Multi-Tenant Isolation
- **Objective:** Implement tenant-isolated API key authentication (`sk-engram-...`) with automated scope resolution.
- **Key Deliverables:**
  - `Organization`, `Workspace`, `User`, and `ApiKey` database entities.
  - Cryptographic validation: SHA-256 key hashing with constant-time verification.
  - Automatic `org_id` and `workspace_id` injection into request dependency contexts.
  - Removal of redundant tenant parameters from client-facing endpoints.

---

### Phase 2 — Unified Document Ingestion Pipeline
- **Objective:** Deploy the unified `/api/v1/documents/ingest` endpoint supporting files and URLs.
- **Key Deliverables:**
  - Streaming file upload handling with MIME-type sniffing.
  - SHA-256 content hashing for deduplication and idempotent re-upload short-circuiting.
  - Asynchronous background task dispatching with persistent PostgreSQL job queue.

---

### Phase 3 — Document Parsing & OCR Engine
- **Objective:** Support high-accuracy layout extraction across digital and scanned documents.
- **Key Deliverables:**
  - Native text extraction via `PyMuPDF` (`fitz`) and `pdfplumber`.
  - Offline OCR fallback (PaddleOCR / Tesseract) executed per page on rasterized images.
  - Optical character confidence tracking per page.

---

### Phase 4 — Hierarchical Structure Parsing (PageIndex Model)
- **Objective:** Construct a hierarchical navigation tree representing document structure.
- **Key Deliverables:**
  - Section, subsection, and heading level (H1, H2, H3) detection using typographic heuristics.
  - PageIndex tree mapping sections to page ranges and character offsets.
  - Tabular region detection preserving cell matrices.

---

### Phase 5 — Structure-Aware Semantic Chunking
- **Objective:** Chunk narrative text while preserving natural grammatical and section boundaries.
- **Key Deliverables:**
  - Boundary-constrained paragraph aggregation (respecting 350–600 token budgets).
  - Sentence-boundary splitting with configurable overlap for oversized passages.
  - Table isolation: generating dedicated table chunks with preserved column headers.

---

### Phase 6 — Hybrid Vector & Lexical Indexing
- **Objective:** Index document chunks into both dense vector and relational keyword stores.
- **Key Deliverables:**
  - In-process or endpoint dense embedding generation using sentence-transformer models.
  - Qdrant vector index upsert with mandatory multi-tenant payload filters (`org_id`, `workspace_id`).
  - PostgreSQL full-text search (`tsvector` with GIN indexing) for lexical keyword matching.

---

### Phase 7 — Hybrid Retrieval & Rank Fusion (RRF)
- **Objective:** Merge semantic and lexical candidate pools into an optimized candidate list.
- **Key Deliverables:**
  - Parallel query dispatching to Qdrant and PostgreSQL FTS.
  - Candidate deduplication and Reciprocal Rank Fusion (RRF) scoring ($k=60$).
  - Candidate pool truncation to top-$M$ (default: 40 candidates).

---

### Phase 8 — Cross-Encoder Reranking
- **Objective:** Maximize context relevance through deep query-passage cross-attention scoring.
- **Key Deliverables:**
  - Cross-encoder reranker inference over top-$M$ candidates.
  - Selection of top-$K$ passages (default: 8–12) within configured prompt token budgets.
  - Source diversity enforcement (limiting max chunks per single document).

---

### Phase 9 — Query Router & Grounded Synthesis
- **Objective:** Route incoming queries to optimal execution tracks and generate grounded answers.
- **Key Deliverables:**
  - Query intent classification (`STRUCTURED`, `UNSTRUCTURED`, `HYBRID`).
  - Grounded answer generation prompt template with immutable citation markers.
  - Explicit `NO_EVIDENCE_FOUND` fallback handling.

---

### Phase 10 — Claim Verification & Provenance Engine
- **Objective:** Enforce zero-hallucination guarantees via post-generation verification.
- **Key Deliverables:**
  - Programmatic claim decomposition from generated answers.
  - Numeric verification checking generated figures against underlying structured facts.
  - Citation attachment linking claims to document titles, pages, and verbatim excerpts.

---

### Phase 11 — Structured Fact Extraction
- **Objective:** Persist tabular and quantitative data into relational `ExtractedFact` tables.
- **Key Deliverables:**
  - Deterministic table parsing mapping cell matrices to typed entity-metric tuples.
  - Metric and unit normalization (converting scalar values and currency units).
  - Entity alias resolution table for mapping organizational acronyms.

---

### Phase 12 — Collections & Document Organization
- **Objective:** Enable workspace users to organize documents into logical collections.
- **Key Deliverables:**
  - `Collection` model and `/api/v1/collections` endpoints.
  - Scoped document queries filtering by collection ID.

---

### Phase 13 — Corpus Analytics & Topic Modeling *(Roadmap)*
- **Objective:** Deliver thematic clustering and term frequency analytics across document collections.
- **Key Deliverables:**
  - TF-IDF salience extraction and word-cloud frequency formatting.
  - Topic clustering (NMF / LDA or BERTopic semantic mode).
  - Asynchronous execution endpoints: `POST /api/v1/topics` and `GET /api/v1/topics/{job_id}`.

---

### Phase 14 — Automated Report Generation *(Roadmap)*
- **Objective:** Enable multi-section analytical report drafting directly from ingested evidence.
- **Key Deliverables:**
  - Extensible report templates (`executive_summary`, `operational_review`, `custom_outline`).
  - Iterative section-by-section evidence retrieval and synthesis.
  - DOCX / PDF document rendering with embedded bibliographies.
  - Asynchronous execution endpoints: `POST /api/v1/reports/generate` and `GET /api/v1/reports/{job_id}`.

---

### Phase 15 — Security Hardening & Threat Mitigation
- **Objective:** Validate end-to-end security posture and adversarial defenses.
- **Key Deliverables:**
  - Penetration testing against indirect prompt injection in document text.
  - Multi-tenant boundary verification ensuring zero cross-workspace data leakage.
  - Decompression bomb defenses and parser memory limits.

---

### Phase 16 — Golden Dataset Benchmarking & QA
- **Objective:** Empirically evaluate retrieval recall, citation precision, and end-to-end latency.
- **Key Deliverables:**
  - Version-controlled golden evaluation dataset covering structured, unstructured, and hybrid queries.
  - Automated evaluation harness measuring routing accuracy, recall@K, and numeric exactness.

---

### Phase 17 — Production Containerization & Cloud Deployment
- **Objective:** Deploy horizontally scalable production infrastructure.
- **Key Deliverables:**
  - Multi-replica API deployment behind layer-7 load balancer.
  - Auto-scaling worker cluster for async document processing.
  - High-availability PostgreSQL and Qdrant cluster configurations.
