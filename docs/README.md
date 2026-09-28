# Documentation Pack — Enterprise RAG Pipeline Microservice

This `docs/` repository serves as the definitive engineering specification and architectural blueprint for the **Universal RAG Pipeline Microservice** ("RAG-as-a-Service"). It is written for software engineers, systems architects, and AI coding agents.

---

## 1. Documentation Index

| File | Core Subject |
|---|---|
| [`00_PROJECT_CONTEXT.md`](00_PROJECT_CONTEXT.md) | Origin, high-level objectives, problem statement, microservice boundaries, and non-negotiable architectural constraints. |
| [`01_PRD.md`](01_PRD.md) | Product Requirements Document: multi-tenant capabilities, functional workflows, non-functional requirements, and acceptance criteria. |
| [`02_SYSTEM_ARCHITECTURE.md`](02_SYSTEM_ARCHITECTURE.md) | High-level system architecture, client application integration, API key scoping, datastore topologies, and reusability boundaries. |
| [`03_RAG_PIPELINE_SPEC.md`](03_RAG_PIPELINE_SPEC.md) | End-to-end Dual-Track RAG pipeline architecture (Structured Extraction Track + Unstructured Narrative Track) and grounded query synthesis. |
| [`04_DOCUMENT_PROCESSING_SPEC.md`](04_DOCUMENT_PROCESSING_SPEC.md) | Ingestion validation, multi-format media handling, offline OCR fallback, PageIndex layout tree parsing, structure-aware semantic chunking, and deduplication. |
| [`05_RETRIEVAL_AND_RERANKING.md`](05_RETRIEVAL_AND_RERANKING.md) | Hybrid retrieval pipeline: dense vector search (Qdrant), lexical Full-Text Search (PostgreSQL GIN), Reciprocal Rank Fusion (RRF), and cross-encoder reranking. |
| [`06_STRUCTURED_DATA_EXTRACTION.md`](06_STRUCTURED_DATA_EXTRACTION.md) | Universal structured fact extraction (`ExtractedFact`), deterministic table parsing, pattern extraction, unit normalization, and alias resolution. |
| [`07_AI_QUERY_ENGINE.md`](07_AI_QUERY_ENGINE.md) | Query intent router (`STRUCTURED`, `UNSTRUCTURED`, `HYBRID`), parameterized template execution, zero-hallucination policies, and dual-track fusion. |
| [`08_API_CONTRACTS.md`](08_API_CONTRACTS.md) | REST API specifications for `/api/v1`: unified document ingestion, status polling, paginated chunk inspection, query execution, and search. |
| [`09_DATA_MODELS.md`](09_DATA_MODELS.md) | Pydantic and SQLAlchemy ORM models, relational database schemas, and storage distribution across PostgreSQL, Qdrant, and Object Storage. |
| [`10_MULTI_TENANCY_RBAC.md`](10_MULTI_TENANCY_RBAC.md) | Tenancy hierarchy (`Organization` → `Workspace` → `Collection` → `Document`), automated API key scope resolution, and native data isolation. |
| [`11_CITATION_AND_VALIDATION.md`](11_CITATION_AND_VALIDATION.md) | Evidentiary grounding, prompt boundaries, programmatic numeric validation, narrative entailment checks, and rich citation payloads. |
| [`12_REPORT_GENERATION.md`](12_REPORT_GENERATION.md) | Automated analytical report drafting: modular section decomposition, template synthesis, bibliography compilation, and DOCX/PDF rendering. |
| [`13_TOPIC_ANALYSIS.md`](13_TOPIC_ANALYSIS.md) | Corpus analytics, keyword salience (TF-IDF), thematic clustering, named entity recognition, and word-cloud data payloads. |
| [`14_ASYNC_PROCESSING.md`](14_ASYNC_PROCESSING.md) | PostgreSQL-native task queue (`SKIP LOCKED`), worker lifecycles, resumable page-batched execution, and poison-pill isolation. |
| [`15_DEPLOYMENT_ARCHITECTURE.md`](15_DEPLOYMENT_ARCHITECTURE.md) | Deployment topologies (single-node evaluation vs. high-availability production), horizontal scaling economics, and Docker Compose configurations. |
| [`16_SECURITY.md`](16_SECURITY.md) | Security threat model, indirect prompt injection defense, SQL injection elimination, binary upload safety, and cryptographic key hygiene. |
| [`17_TESTING_STRATEGY.md`](17_TESTING_STRATEGY.md) | Empirical testing methodology: unit testing, integration tests, golden evaluation datasets, precision benchmarks, and security verification. |
| [`18_IMPLEMENTATION_ROADMAP.md`](18_IMPLEMENTATION_ROADMAP.md) | Phased engineering roadmap: completed milestones, active deliverables, and planned roadmap extensions. |
| [`19_ENVIRONMENT_VARIABLES.md`](19_ENVIRONMENT_VARIABLES.md) | Comprehensive environment configuration reference for application settings, datastore connections, and model parameters. |
| [`20_AI_CODING_RULES.md`](20_AI_CODING_RULES.md) | Binding architectural constraints, security rules, and code quality standards for engineers and AI coding assistants. |
| [`rag_er_diagram.md`](rag_er_diagram.md) | Visual Entity-Relationship diagram illustrating PostgreSQL database tables, relationships, and foreign keys. |
| [`testing_report.md`](testing_report.md) | Empirical test suite execution logs, verification results, and coverage metrics. |

---

## 2. Recommended Reading Order

### For Understanding System Architecture & Security
1. `00_PROJECT_CONTEXT.md`
2. `01_PRD.md`
3. `02_SYSTEM_ARCHITECTURE.md`
4. `10_MULTI_TENANCY_RBAC.md`
5. `16_SECURITY.md`
6. `20_AI_CODING_RULES.md`

### For Implementing Document Processing & Ingestion
1. `04_DOCUMENT_PROCESSING_SPEC.md`
2. `06_STRUCTURED_DATA_EXTRACTION.md`
3. `14_ASYNC_PROCESSING.md`
4. `09_DATA_MODELS.md`

### For Implementing Search, Retrieval & Grounded Querying
1. `03_RAG_PIPELINE_SPEC.md`
2. `05_RETRIEVAL_AND_RERANKING.md`
3. `07_AI_QUERY_ENGINE.md`
4. `11_CITATION_AND_VALIDATION.md`
5. `08_API_CONTRACTS.md`

### For Operations, Deployment & Quality Assurance
1. `15_DEPLOYMENT_ARCHITECTURE.md`
2. `17_TESTING_STRATEGY.md`
3. `19_ENVIRONMENT_VARIABLES.md`
4. `18_IMPLEMENTATION_ROADMAP.md`
