# 01 — Product Requirements Document (PRD)

## 1. Product Summary

A multi-organization platform that lets CMPDI, CIL subsidiaries, and Ministry of Coal users upload, process, search, query, and generate reports from geological/mining/production documents, with an AI layer that answers questions with cited, verifiable evidence and distinguishes between exact structured figures and narrative/contextual information.

## 2. Users and Roles

| Role | Description |
|---|---|
| SUPER_ADMIN | Platform-level administrator (spans organizations). Manages orgs, global settings. |
| ORG_ADMIN | Administers a single organization (e.g., a specific CIL subsidiary or CMPDI). Manages workspaces, members, permissions within the org. |
| MEMBER | Regular user within an org/workspace. Uploads documents, runs queries, generates reports (subject to capability grants). |
| VIEWER | Read-only access to documents, analytics, and reports within their scope. |

See `10_MULTI_TENANCY_RBAC.md` for the full capability model.

## 3. Primary User Journeys

### 3.1 Document Ingestion
A MEMBER uploads a scanned or digital PDF/DOCX/XLSX/CSV/image into a workspace folder. The system classifies, OCRs (if needed), extracts structure, extracts structured facts, chunks narrative content, embeds, and indexes it — asynchronously, with visible status.

### 3.2 Ask a Question (AI Assistant)
A user asks a natural-language question scoped to a workspace or document set. The system determines whether the question needs a structured query, a RAG (retrieval-augmented) answer, or both, and returns an answer with citations (document, page, section) or explicitly states no evidence was found.

### 3.3 Analytics / Topic Identification
A user selects a document collection and requests topic/keyword analysis. The system runs (asynchronously, for large collections) TF-IDF/keyword extraction, topic modeling, named entity extraction, and generates word-cloud-ready output.

### 3.4 Report Generation
A user requests a report (e.g., "production summary for Mine X, 2020–2024" or a parliamentary-question response draft). The system retrieves the relevant structured data and narrative evidence, drafts report sections, attaches sources to every factual claim, and produces a DOCX/PDF.

## 4. Functional Requirements

### FR-1 Document Management (Express, existing + extended)
- Upload documents into Organization → Workspace → Folder hierarchy.
- Track document metadata, version, and processing status.
- Enforce access control at document/workspace/organization level.

### FR-2 Document Intelligence Processing (FastAPI, new)
- Ingest and validate files (digital PDF, scanned PDF, DOCX, XLSX, CSV, images).
- OCR scanned content; parse digital content.
- Understand document structure (sections/subsections/tables/pages) using a PageIndex-style hierarchical approach where applicable.
- Extract structured facts (production, target, achievement, year, mine, subsidiary, coal grade, dispatch, quantity, etc.) into PostgreSQL.
- Chunk narrative content in a structure-aware manner; embed and index chunks (vector + keyword).
- Support asynchronous, resumable, page-batched processing for arbitrarily large files.

### FR-3 Query & Retrieval
- Route each query to structured / RAG / hybrid handling.
- Structured queries execute against PostgreSQL via parameterized, templated queries only — never free-form LLM-generated SQL.
- RAG queries use hybrid (semantic + keyword) retrieval with reranking, scoped to the caller's authorized documents.
- All AI answers include citations (document/page/section/chunk) or explicitly state no evidence was found.

### FR-4 Report Generation
- Generate structured report drafts combining retrieved structured data and cited narrative evidence.
- Never allow the LLM to generate factual report content purely from parametric memory without attached evidence.
- Export to DOCX/PDF.

### FR-5 Topic & Word-Cloud Analysis
- Run keyword frequency / TF-IDF / topic modeling / named entity extraction over a selected document collection.
- Support asynchronous execution for large collections.
- Produce word-cloud-ready frequency output and topic summaries.

### FR-6 Multi-Tenancy & RBAC
- Generic Organization model (no hard-coded subsidiaries).
- Organization → Workspace → Folder → Document hierarchy.
- Role-based + capability-based permission enforcement, consistently applied in both Express and the scope passed to FastAPI.

### FR-7 Traceability & Validation
- Every structured fact stores document/page/section provenance.
- Every RAG answer stores the retrieved evidence used to justify each generated claim.
- Numerical claims are checked for consistency against structured data or explicit source text before being returned.

## 5. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Scalability | Processing workers must scale independently of the API layer. Architecture must not assume documents fit in memory. |
| Portability | LLM provider configurable via environment variables (OpenAI-compatible). No vendor lock-in in code. |
| Security | Tenant/workspace/document isolation enforced at every layer; FastAPI never bypasses Express-issued authorization scope. |
| Traceability | No unsupported factual claims; system prefers explicit "no evidence found" responses. |
| Observability | Structured logging across both services; job/processing status is queryable at every stage. |
| Reusability | The AI service's core RAG/document-intelligence engine must not hard-code CMPDI/CIL-specific concepts into its architecture (domain-specific *content handling*, e.g., production/mine/grade extraction schemas, is expected and acceptable; hard-coded organization names/IDs are not). |

## 6. Out of Scope (for the initial implementation)

- Full enterprise SSO/identity federation (VERIFY AGAINST EXISTING REPOSITORY for current auth mechanism; not redesigned here).
- Real-time collaborative document editing.
- Mobile-native applications.
- Processing the full 267 MB reference document during the SIH demo (a representative 8–10 MB document is used instead — see `22` demo strategy in `18_IMPLEMENTATION_ROADMAP.md` and `15_DEPLOYMENT_ARCHITECTURE.md`).
- Building a generic, domain-agnostic SaaS RAG product. This is domain-specific document intelligence with reusable *infrastructure*, not a generic platform.

## 7. Success Criteria (Prototype / SIH Demo)

1. Upload and asynchronously process an 8–10 MB data-heavy report end to end (UPLOADED → READY).
2. Answer a structured numeric question correctly and cite the structured source.
3. Answer a narrative "why" question via RAG with page-level citations.
4. Answer a hybrid question combining structured figures and narrative explanation.
5. Generate a word cloud / topic summary for a document collection.
6. Generate a short report with attached sources.
7. Demonstrate that access is scoped — a user cannot query documents outside their authorized workspace.

Success is evaluated against the golden dataset defined in `17_TESTING_STRATEGY.md`, not against unverified claims of accuracy.
