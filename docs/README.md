# Documentation Pack — CMPDI/CIL Document Intelligence & RAG Platform

This `docs/` folder is the **single source of truth for implementation** for this Smart India Hackathon project. It is written for both human engineers and AI coding agents (Claude Code, Codex, Google Antigravity, etc.).

## Purpose of Each Document

| File | Purpose |
|---|---|
| `00_PROJECT_CONTEXT.md` | Origin of the project, the problem statement it responds to, what already exists, and the non-negotiable constraints carried through every other document. |
| `01_PRD.md` | Product requirements: users/roles, user journeys, functional and non-functional requirements, success criteria for the SIH demo. |
| `02_SYSTEM_ARCHITECTURE.md` | The target system architecture: Node.js Backend core + new FastAPI AI service, service boundaries, cross-service authentication/authorization design, data ownership, reusability boundary. |
| `03_RAG_PIPELINE_SPEC.md` | The end-to-end hybrid (structured + unstructured) document-intelligence/RAG pipeline, and why a generic PDF→chunks→vector-DB→LLM pipeline is insufficient for this domain. |
| `04_DOCUMENT_PROCESSING_SPEC.md` | Ingestion, classification, OCR, structure understanding, metadata extraction, structure-aware chunking, versioning, large-document handling, failure handling. |
| `05_RETRIEVAL_AND_RERANKING.md` | Embedding strategy, vector index design, keyword retrieval, candidate fusion, reranking, context selection, and authorization filtering at the retrieval layer. |
| `06_STRUCTURED_DATA_EXTRACTION.md` | The structured-fact schema (production, target, achievement, mine, subsidiary, coal grade, etc.), extraction methods, normalization, validation. |
| `07_AI_QUERY_ENGINE.md` | The query router deciding structured vs. RAG vs. hybrid handling, and the safety design preventing arbitrary LLM-generated SQL. |
| `08_API_CONTRACTS.md` | REST API definitions for the FastAPI service: ingestion, status, processing, query, search, extract, topics, reports. |
| `09_DATA_MODELS.md` | Pydantic models for every domain object, and PostgreSQL vs. Qdrant responsibility. |
| `10_MULTI_TENANCY_RBAC.md` | Organization/Workspace/Folder/Document hierarchy, roles, capability-based permissions, document-level authorization, enforcement points. |
| `11_CITATION_AND_VALIDATION.md` | The evidence→claims→verification→response pipeline that prevents hallucination and ensures traceable, cited answers. |
| `12_REPORT_GENERATION.md` | Automated report generation module: pipeline, section-level evidence/validation, output rendering, review/approval. |
| `13_TOPIC_ANALYSIS.md` | Word cloud and topic identification module: keyword extraction, topic modeling, named entity extraction, async execution. |
| `14_ASYNC_PROCESSING.md` | The async job-queue architecture (Postgres-backed, no Celery/Redis), worker design, document processing lifecycle and retry semantics. |
| `15_DEPLOYMENT_ARCHITECTURE.md` | Prototype vs. production deployment topology, and why large documents don't require a different architecture, only different time/throughput budgets. |
| `16_SECURITY.md` | Authentication/authorization boundaries, secrets management, upload security, RAG prompt-injection defenses, SQL-injection prevention, data-leakage prevention. |
| `17_TESTING_STRATEGY.md` | Unit/integration testing, the golden RAG evaluation dataset, metrics measured, and the principle that no accuracy number is claimed without measurement. |
| `18_IMPLEMENTATION_ROADMAP.md` | Phased roadmap (Phase 0–18), each with objective, modules, dependencies, tasks, acceptance criteria, tests, and failure modes. |
| `19_ENVIRONMENT_VARIABLES.md` | Every required environment variable, its owner service, and its purpose. No real secret values ever appear here. |
| `20_AI_CODING_RULES.md` | Binding rules for AI coding agents working on this codebase. |

## Recommended Reading Order for an AI Coding Agent

**Before any implementation work, in this order:**

1. `00_PROJECT_CONTEXT.md` — understand what problem this solves and what already exists.
2. `01_PRD.md` — understand what "done" looks like.
3. `02_SYSTEM_ARCHITECTURE.md` — understand the two-service architecture and the authorization handoff between them. This is the most load-bearing document; nearly everything else depends on it.
4. `10_MULTI_TENANCY_RBAC.md` — understand the tenancy/permission model referenced by almost every other document.
5. `20_AI_CODING_RULES.md` — internalize the binding engineering rules before writing any code.

**Before implementing the RAG/document-intelligence core:**

6. `03_RAG_PIPELINE_SPEC.md`
7. `04_DOCUMENT_PROCESSING_SPEC.md`
8. `05_RETRIEVAL_AND_RERANKING.md`
9. `06_STRUCTURED_DATA_EXTRACTION.md`
10. `07_AI_QUERY_ENGINE.md`
11. `11_CITATION_AND_VALIDATION.md`

**Before implementing APIs and data layer:**

12. `08_API_CONTRACTS.md`
13. `09_DATA_MODELS.md`
14. `14_ASYNC_PROCESSING.md`

**Before implementing the higher-level modules:**

15. `12_REPORT_GENERATION.md`
16. `13_TOPIC_ANALYSIS.md`

**Before deploying or hardening:**

17. `15_DEPLOYMENT_ARCHITECTURE.md`
18. `16_SECURITY.md`
19. `17_TESTING_STRATEGY.md`
20. `19_ENVIRONMENT_VARIABLES.md`

**Throughout the whole project:**

21. `18_IMPLEMENTATION_ROADMAP.md` — the phase-by-phase execution plan; consult before starting any phase of work.

## How to Use "VERIFY AGAINST EXISTING REPOSITORY" Markers

Several documents (notably `10_MULTI_TENANCY_RBAC.md`, `12_REPORT_GENERATION.md`, `18_IMPLEMENTATION_ROADMAP.md`, `19_ENVIRONMENT_VARIABLES.md`) contain the marker:

> **VERIFY AGAINST EXISTING REPOSITORY**

This means: the actual current implementation of the existing Node.js Backend application was not known at the time this documentation was written, and the coding agent must inspect the real codebase before implementing the affected piece — not assume the documented default is already true of the existing code.

## How Decisions Are Recorded

Wherever this pack made an implementation choice not strictly mandated by the original problem statement, it is labeled explicitly as:

> **Decision:** ... **Alternatives considered:** ... **Reason:** ...

If real-world implementation constraints require revisiting one of these decisions, update the decision block in place (per `20_AI_CODING_RULES.md` §19) rather than silently diverging from it.
