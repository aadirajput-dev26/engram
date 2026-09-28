# 01 — Product Requirements Document (PRD)

## 1. Product Summary

The **RAG Pipeline Microservice** is a high-performance, enterprise-grade "RAG-as-a-Service" infrastructure designed to power document intelligence, semantic search, structured data extraction, and grounded generative synthesis across multi-tenant enterprise environments.

The microservice enables client applications to ingest complex, heterogenous business documents (including digital PDFs, scanned documents, spreadsheets, Word files, and images), analyze their visual and syntactic structure, index them into hybrid vector and relational stores, and execute precision queries backed by verifiable, page-level citations.

---

## 2. Multi-Tenancy & Authorization Model

The RAG Pipeline operates strictly as an infrastructure microservice. User identity management, billing, and front-end authorization are managed upstream by consuming Client Applications. The microservice enforces strict data isolation through hierarchical scoping:

| Scope Level | Description | Isolation Guarantee |
|---|---|---|
| **Organization (`org_id`)** | Top-level enterprise tenant. | Complete cryptographic and relational database separation. |
| **Workspace (`workspace_id`)** | Functional project, department, or team container within an organization. | Vector collections, document catalogs, and database rows are partitioned by workspace. |
| **API Key (`x-api-key`)** | Scoped cryptographic credential passed in request headers. | The service validates and automatically resolves the API key to its authorized `org_id` and `workspace_id`. |

---

## 3. Primary Workflows & Capabilities

### 3.1 Asynchronous Document Ingestion & Processing
A client application submits a document (digital PDF, scanned PDF, DOCX, XLSX, CSV, image) to the ingestion endpoint. The microservice:
1. Validates the file signature and stores the raw binary in object storage.
2. Dispatches an asynchronous processing job.
3. Automatically classifies the document format and applies appropriate extraction (native parsing or OCR).
4. Dissects layout structure (pages, sections, tables, paragraphs).
5. Splits content into the Dual-Track pipeline: structured tabular facts into PostgreSQL, and semantic narrative chunks into Qdrant and Postgres Full-Text Search.
6. Updates processing job status to `READY` with comprehensive extraction metrics.

### 3.2 Grounded AI Query & Question-Answering
A client application submits a natural language question scoped by API key to an authorized workspace or specific document subset:
1. The service analyzes query intent to classify it as `STRUCTURED`, `UNSTRUCTURED`, or `HYBRID`.
2. Structured queries execute parameterized SQL against normalized fact tables.
3. Unstructured queries perform hybrid dense vector retrieval (Qdrant) and lexical keyword search (PostgreSQL FTS), fused via Reciprocal Rank Fusion (RRF) and reranked via a cross-encoder model.
4. Generative synthesis produces a factual answer constrained strictly to retrieved context.
5. Every statement is validated and stamped with exact provenance citations (document, page, section, chunk). If insufficient evidence is found, the service returns `NO_EVIDENCE_FOUND`.

### 3.3 Corpus Analytics & Topic Extraction
A client application requests lexical and thematic analysis across a selected set of documents:
- Extracts high-frequency keywords, key phrases, and domain entities.
- Computes TF-IDF distributions and cluster topics.
- Generates data formatted for topic visualization and word-cloud generation.

### 3.4 Automated Document & Report Synthesis
A client application requests a structured analytical report covering specific topics or entities:
- Gathers relevant structured metrics and supporting narrative evidence across the corpus.
- Drafts structured report sections adhering to predefined templates.
- Enforces strict evidence citation for all included metrics and claims.
- Exports structured report objects or downloadable artifacts.

---

## 4. Functional Requirements

### FR-1: Ingestion & Document Processing Engine
- **Unified Ingestion:** Provide robust endpoints accepting single and batched uploads with MIME type detection and file validation.
- **Multi-Format Support:** Handle digital PDFs, scanned PDFs (OCR via Tesseract/vision models), DOCX, XLSX, CSV, and image files.
- **Hierarchical Layout Parsing:** Construct a tree representing document structure: Document → Pages → Sections → Subsections → Paragraphs / Tables.
- **Asynchronous & Resumable Execution:** Employ worker-driven job execution with status tracking (`PENDING`, `PROCESSING`, `READY`, `FAILED`) capable of processing large documents without memory exhaustion.

### FR-2: Dual-Track Indexing Architecture
- **Structured Track:** Extract tabular records, financial/operational KPIs, and key-value pairs into typed relational tables with page coordinates.
- **Unstructured Track:** Chunk narrative prose using layout-aware boundary preservation (avoiding splitting sentences across arbitrary character counts).
- **Hybrid Vector & Lexical Indexing:** Compute dense embeddings for semantic search in Qdrant; index text with language-specific stems in PostgreSQL for exact lexical search.

### FR-3: Intelligent Retrieval & Reranking
- **Query Classification:** Automatically detect whether a query is computational/tabular, semantic/narrative, or a hybrid combination.
- **Hybrid Retrieval:** Retrieve candidate sets from both dense vector space and full-text keyword indices.
- **Rank Fusion & Reranking:** Combine retrieval streams using Reciprocal Rank Fusion (RRF) and apply cross-encoder reranking to produce optimal context windows.

### FR-4: Verifiable Synthesis & Hallucination Prevention
- **Context-Bound LLM Inference:** Strictly instruct the LLM provider to answer solely based on provided evidence chunks.
- **Automated Claim Verification:** Post-process generated answers to ensure every factual and numerical claim maps directly to a cited source chunk.
- **Citation Metadata:** Include full source attribution in API responses: document ID, document title, page number, section title, and verbatim excerpt.
- **Graceful Failure:** Return explicit `NO_EVIDENCE_FOUND` sentinels rather than speculative hallucinations when evidence is absent.

### FR-5: Document Corpus Analytics
- Provide endpoints to compute keyword frequencies, TF-IDF scores, and thematic clusters across designated document subsets.
- Support asynchronous execution for corpus-wide analytical operations.

### FR-6: Multi-Tenant Data Isolation
- Enforce strict database-level and vector-level filtering on all operations using resolved `workspace_id` and `org_id` context.
- Prevent cross-tenant data leaks across all query and ingestion pipelines.

---

## 5. Non-Functional Requirements

| Metric / Dimension | Specification |
|---|---|
| **Architecture** | Stateless, horizontally scalable FastAPI microservice. |
| **LLM Provider Portability** | Configurable via environment variables adhering to OpenAI-compatible API standards (supporting OpenAI, Azure OpenAI, Ollama, vLLM, Anthropic proxies). |
| **Data Isolation** | Multi-tenant isolation enforced at the data layer for every query and storage operation. |
| **Resilience & Scalability** | Background processing offloaded to async job runners; streaming file handling to guarantee low memory footprints. |
| **Accuracy & Traceability** | 100% of generated factual assertions must be traceable to cited evidence; unsupported claims are eliminated or flagged. |
| **Observability** | Structured JSON logging, detailed job stage tracking, and latency metrics across ingestion and retrieval pipelines. |

---

## 6. Scope Boundaries

### In Scope (Microservice Responsibilities):
- Document ingestion, validation, OCR, layout extraction, and structure parsing.
- Dual-track indexing (PostgreSQL structured facts + Qdrant vectors + PostgreSQL FTS).
- Query routing, hybrid retrieval, reranking, generative synthesis, and citation verification.
- Topic analysis and report generation logic.
- Asynchronous task lifecycle management.

### Out of Scope (Client Application Responsibilities):
- End-user authentication (SSO, OAuth, password management).
- User interface presentation (web dashboards, mobile interfaces).
- Billing, subscription tiers, and organizational user management.
- Direct interaction with vector databases or internal LLM keys.

---

## 7. Verification & Acceptance Criteria

1. **Ingestion Reliability:** Successfully upload and process complex digital and scanned documents through all stages to `READY` state without data corruption.
2. **Retrieval Precision:** Demonstrate that hybrid search (vector + keyword + reranking) retrieves exact target evidence with higher precision than single-mode vector search.
3. **Citation Integrity:** Ensure every response to an evidence-seeking query contains valid, verifiable page and chunk references.
4. **Tenant Isolation:** Verify that requests using an API key for Workspace A cannot retrieve or search documents belonging to Workspace B under any circumstances.
5. **Hallucination Rejection:** When queried on topics not covered in ingested documents, the service reliably outputs `NO_EVIDENCE_FOUND`.
