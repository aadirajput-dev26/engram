# 18 — Implementation Roadmap

Each phase lists: objective, files/modules to create, dependencies, implementation tasks, acceptance criteria, tests, and possible failure modes. Phases are sequential but later phases may be parallelized once their dependencies are satisfied (noted per phase).

---

### Phase 0 — Repository and Architecture Setup
**Objective:** establish the new FastAPI service as a separate deployable unit alongside the existing Node.js Backend, with the reusable-core / domain-specific-layer module boundary from `02_SYSTEM_ARCHITECTURE.md` §7 baked into the folder structure from day one.
**Modules:** `ai-service/` repo or subdirectory with `app/core/` (ingestion, ocr, structure, chunking, embeddings, retrieval, rerank, query_router framework, validation framework, jobs) and `app/domain/` (mining-specific extraction schemas, report templates, topic vocab).
**Dependencies:** none.
**Tasks:** scaffold FastAPI app, dependency management (e.g., `pyproject.toml`), Docker Compose for local dev (`15_DEPLOYMENT_ARCHITECTURE.md` §6), CI skeleton, structured logging setup, config loading (`19_ENVIRONMENT_VARIABLES.md`).
**Acceptance criteria:** service boots locally via Docker Compose; health-check endpoint responds; CI runs (even with zero tests initially).
**Tests:** smoke test for health endpoint.
**Failure modes:** dependency version conflicts (PyMuPDF/PaddleOCR native deps) — pin versions early.

### Phase 1 — FastAPI Service Skeleton
**Objective:** service-to-service auth and scope-token verification working end-to-end before any real feature is built.
**Modules:** `app/core/auth/` (service-key check, scope-token verification), `app/api/v1/` router skeleton.
**Dependencies:** Phase 0.
**Tasks:** implement `X-Service-Key` middleware; implement scope-token JWT verification (`AI_SCOPE_TOKEN_SECRET`); implement the common error envelope (`08_API_CONTRACTS.md` §0).
**Acceptance criteria:** a request without a valid service key/scope token is rejected (401/403); a valid one passes through to a stub handler.
**Tests:** unit tests for auth middleware (valid/expired/tampered/missing token cases).
**Failure modes:** clock skew causing false expiry rejections — allow small leeway window.

### Phase 2 — Document Ingestion
**Objective:** implement `POST /documents/ingest` and `GET /documents/{id}/status` against object storage and the AI PostgreSQL schema.
**Modules:** `app/core/ingestion/` (validation, classification stub, object storage client), `app/db/models/document.py`, `app/db/models/processing_job.py`.
**Dependencies:** Phase 1; object storage and PostgreSQL reachable.
**Tasks:** file validation (§`04` MIME/size/hash), idempotent content-hash short-circuit, job creation, status endpoint.
**Acceptance criteria:** uploading a fixture file creates a `Document`/`DocumentVersion`/`ProcessingJob` row and returns `QUEUED`; re-uploading the identical file returns `ALREADY_PROCESSED`.
**Tests:** integration tests per `17_TESTING_STRATEGY.md` §3 (ingestion end-to-end, idempotency).
**Failure modes:** large file upload timeouts — verify pre-signed upload path works for files above the direct-upload threshold.

### Phase 3 — PDF Parsing and OCR
**Objective:** implement page-batched classification, native text extraction, and OCR fallback.
**Modules:** `app/core/ocr/` (PaddleOCR wrapper), `app/core/parsing/` (PyMuPDF wrapper), `app/db/models/page.py`.
**Dependencies:** Phase 2.
**Tasks:** per-page classification, page-batch processing loop with checkpointing, OCR confidence capture, per-file/page exception isolation (`16_SECURITY.md` §7).
**Acceptance criteria:** a mixed digital+scanned fixture PDF produces correct per-page `source_type` and reasonable OCR text on scanned pages.
**Tests:** unit tests on fixtures (§`17` parsing); resumability test (kill mid-batch, resume).
**Failure modes:** OCR memory spikes on very high-DPI renders — enforce configurable DPI cap.

### Phase 4 — Structure Extraction / PageIndex
**Objective:** build the hierarchical section/table structure tree.
**Modules:** `app/core/structure/` (heading detection, PageIndex tree builder, table region detector), `app/db/models/section.py`, `app/db/models/table.py`.
**Dependencies:** Phase 3.
**Tasks:** heuristic heading/section detection; table detection; `section_path` generation.
**Acceptance criteria:** fixture document's known section structure is reproduced within acceptable heuristic tolerance (defined per fixture, not claimed universally).
**Tests:** unit tests per `17` structure understanding.
**Failure modes:** archival scans with inconsistent formatting defeating heuristics — flagged as a known heuristic-approach limitation (see `04_DOCUMENT_PROCESSING_SPEC.md` §5 decision note); escalate to ML layout model only if evaluation shows it's needed.

### Phase 5 — Chunking and Metadata
**Objective:** structure-aware chunker producing `Chunk` records.
**Modules:** `app/core/chunking/`.
**Dependencies:** Phase 4.
**Tasks:** implement algorithm from `04_DOCUMENT_PROCESSING_SPEC.md` §7; content-hash-based dedup linking (§8).
**Acceptance criteria:** chunks never cross section boundaries in fixtures; token budgets respected; tables chunked separately.
**Tests:** unit tests per `17` chunking.

### Phase 6 — Embeddings and Qdrant
**Objective:** embed chunks and index into Qdrant with correct payload/filters.
**Modules:** `app/core/embeddings/`, `app/core/vectorstore/` (Qdrant client wrapper).
**Dependencies:** Phase 5; Qdrant reachable.
**Tasks:** load configurable embedding model; batch-embed; upsert to Qdrant with full payload (`05_RETRIEVAL_AND_RERANKING.md` §3).
**Acceptance criteria:** a known chunk is retrievable by a semantically related query; payload filter by `org_id`/`workspace_id`/`document_id` correctly excludes non-matching vectors.
**Tests:** integration tests per `17` Qdrant integration.

### Phase 7 — Hybrid Retrieval
**Objective:** implement semantic + keyword retrieval and RRF fusion.
**Modules:** `app/core/retrieval/` (semantic, keyword/FTS, fusion).
**Dependencies:** Phase 6; Postgres FTS index migration applied.
**Tasks:** Postgres `tsvector`/GIN index migration and query function; RRF fusion implementation.
**Acceptance criteria:** fusion ordering matches expected ordering on synthetic fixture per `17` retrieval scoring tests.
**Tests:** unit tests (fusion), integration tests (end-to-end hybrid retrieval on fixture corpus).

### Phase 8 — Reranking
**Objective:** integrate cross-encoder reranker over fused candidates.
**Modules:** `app/core/rerank/`.
**Dependencies:** Phase 7.
**Tasks:** load configurable reranker model; score fused candidates; truncate to top-K; context-selection token-budget assembly.
**Acceptance criteria:** reranker correctly promotes the most relevant fixture chunk to top-1 in a constructed test case.
**Tests:** unit tests per `17`.

### Phase 9 — RAG Answer Generation
**Objective:** implement the constrained LLM answer-generation call.
**Modules:** `app/core/generation/` (prompt templates, LLM client wrapper using configurable OpenAI-compatible endpoint).
**Dependencies:** Phase 8; LLM endpoint configured.
**Tasks:** implement evidence-block prompt construction (`11_CITATION_AND_VALIDATION.md` §3); implement `NO_EVIDENCE_FOUND` sentinel handling.
**Acceptance criteria:** RAG answer to a golden-dataset narrative question cites the expected page(s).
**Tests:** golden-dataset evaluation subset (RAG questions only) per `17` §4–5.

### Phase 10 — Citation and Validation
**Objective:** implement claim extraction, evidence verification, numeric consistency checks.
**Modules:** `app/core/validation/`.
**Dependencies:** Phase 9; Phase 11 (structured facts) for numeric checks — may be developed in parallel with stubbed fact data.
**Tasks:** implement claim parsing, per-claim verification, response downgrade logic (§`11`).
**Acceptance criteria:** deliberately mismatched-number fixture is caught and corrected/stripped; prompt-injection fixture does not leak out-of-scope content (`17` §7).
**Tests:** unit + security-focused tests per `17` §2, §7.

### Phase 11 — Structured Extraction
**Objective:** implement table parser, regex extractor, and LLM-assisted fallback for `ExtractedFact`.
**Modules:** `app/domain/extraction/` (this is domain-specific layer — see Phase 0 module boundary).
**Dependencies:** Phase 4 (tables/structure available). Can proceed in parallel with Phases 6–10.
**Tasks:** implement extraction priority order (§`06` §3), normalization, alias table, validation flags.
**Acceptance criteria:** fixture tables produce correct `ExtractedFact` rows matching golden-dataset expected structured values.
**Tests:** unit tests per `17` structured extraction.

### Phase 12 — SQL/RAG Query Router
**Objective:** implement query classification and the fixed structured-query-template execution path.
**Modules:** `app/core/query_router/` (classification framework, reusable), `app/domain/query_templates/` (domain-specific templates).
**Dependencies:** Phases 7–11.
**Tasks:** implement `QueryClassification`/`StructuredQueryPlan` schemas; implement template functions (§`07` §4); implement hybrid fusion of structured + RAG evidence.
**Acceptance criteria:** the three canonical example questions (`07` §3) route correctly and produce correct/cited answers against the golden dataset.
**Tests:** golden-dataset full evaluation (`17` §4–5).

### Phase 13 — Node.js Backend Integration
**Objective:** wire Node.js Backend to mint scope tokens and call the FastAPI service for ingest/status/query/search/topics/reports.
**Modules:** Node.js-side: scope-token minting service, FastAPI client wrapper, new/extended endpoints proxying to FastAPI.
**Dependencies:** Phases 2, 9, 12 minimally; full feature set ideally complete.
**Tasks:** **VERIFY AGAINST EXISTING REPOSITORY** for current Node.js Backend auth/session structure before implementing scope-token minting; implement `AI_SERVICE_API_KEY`/`AI_SCOPE_TOKEN_SECRET` usage on the Node.js Backend side; add UI-facing endpoints that proxy to the FastAPI contracts in `08`.
**Acceptance criteria:** an authenticated Node.js Backend authenticated user can upload a document and receive an AI-generated, cited answer through the full stack.
**Tests:** integration tests per `17` §3 (Node.js Backend → FastAPI integration); manual E2E smoke test.
**Failure modes:** mismatched assumptions about existing folder/workspace schema — resolve via the VERIFY items in `10_MULTI_TENANCY_RBAC.md` §7 before writing integration code.

### Phase 14 — Topic Analysis
**Objective:** implement `/topics` endpoint and pipeline.
**Modules:** `app/domain/topics/` (or `app/core/topics/` for the reusable TF-IDF/NER framework, with domain gazetteer in `app/domain/`).
**Dependencies:** Phase 6 (embeddings, if BERTopic backend enabled), Phase 11 (alias table reuse).
**Tasks:** implement TF-IDF keyword extraction, topic modeling (LDA default, BERTopic optional), NER with domain gazetteer, async job wiring (Phase 14 relies on Phase-0 job-queue infra — see Async Processing phase note below).
**Acceptance criteria:** running topic analysis on the demo document collection produces coherent keywords/topics/word-cloud data.
**Tests:** unit tests (keyword extraction correctness on fixtures), manual qualitative review of topic coherence (no numeric accuracy claim is meaningful for unsupervised topics).

> Note: the async job-queue infrastructure itself (`14_ASYNC_PROCESSING.md`) should be built as part of Phase 2 (ingestion needs it immediately) and reused, not rebuilt, by Phases 14/15.

### Phase 15 — Report Generation
**Objective:** implement `/reports/generate` pipeline and DOCX/PDF rendering.
**Modules:** `app/domain/reports/` (templates, section definitions), `app/core/reports/` (generation engine reusing query router + validation).
**Dependencies:** Phase 12 (query router), Phase 10 (validation).
**Tasks:** implement report outline resolution, per-section evidence gathering/generation/validation loop (`12` §3), DOCX rendering.
**Acceptance criteria:** a `production_summary` report for the demo document generates with valid citations on every populated section, and explicit placeholders where evidence is missing.
**Tests:** integration test per `17` §3 (report generation end-to-end).

### Phase 16 — Security and Tenant Isolation Hardening
**Objective:** dedicated pass to verify every checklist item in `16_SECURITY.md` §10 across the whole system.
**Modules:** cross-cutting; no new modules, primarily tests and review.
**Dependencies:** all functional phases substantially complete.
**Tasks:** run the security-focused test suite (`17` §7); manual code review against the `16_SECURITY.md` §10 checklist; penetration-style manual testing of scope-bypass attempts.
**Acceptance criteria:** all security-focused tests pass; checklist fully satisfied.
**Tests:** `17` §7 test suite.

### Phase 17 — Testing / Evaluation
**Objective:** finalize and run the full golden-dataset evaluation; establish baseline metrics.
**Modules:** `tests/golden_dataset/`, evaluation harness script.
**Dependencies:** Phases 9–12 complete.
**Tasks:** curate golden dataset (`17` §4) from the actual demo document; run evaluation harness; record baseline metrics (§`17` §5) — no metric is claimed before this phase produces it.
**Acceptance criteria:** baseline metrics recorded and reviewed; any glaring retrieval/citation failures fixed before demo.
**Tests:** the evaluation harness itself is the test.

### Phase 18 — Deployment
**Objective:** deploy prototype topology (`15_DEPLOYMENT_ARCHITECTURE.md` §2) and verify end-to-end in the deployed environment.
**Modules:** deployment configs (Render service definitions, environment variable groups, Docker images).
**Dependencies:** all prior phases.
**Tasks:** provision managed Postgres, Qdrant Cloud, object storage; configure environment variables (`19`); deploy Node.js Backend, FastAPI, worker, frontend; run the full demo script (`01_PRD.md` §7) against the deployed environment.
**Acceptance criteria:** all SIH demo success criteria (`01_PRD.md` §7) pass in the deployed environment, not just locally.
**Tests:** manual E2E demo rehearsal.

## Cross-Cutting Open Items (not blocking, but flagged)

- Multi-turn conversational context for `/query` — not detailed (see `08_API_CONTRACTS.md` §4 note).
- Document-level access-grant overrides beyond workspace-level — flagged as roadmap item in `10_MULTI_TENANCY_RBAC.md` §4.
- Malware scanning on upload — flagged in `16_SECURITY.md` §5.
- Dynamic query-builder DSL as a v2 evolution of the fixed-template structured query path — flagged in `07_AI_QUERY_ENGINE.md` §4.
- ML-based document layout understanding as a fallback if heuristic structure detection proves insufficient on real archival scans — flagged in `04_DOCUMENT_PROCESSING_SPEC.md` §5.
