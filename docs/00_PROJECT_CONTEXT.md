# 00 — Project Context

## 1. Origin

This project responds to a Smart India Hackathon (SIH) problem statement issued in the context of **CMPDI (Central Mine Planning & Design Institute)**, **Coal India Limited (CIL) subsidiaries**, and the **Ministry of Coal**.

CMPDI/CIL subsidiaries are regularly required to produce geological, mining, and production-figure reports for the Ministry of Coal, including responses to parliamentary and high-priority administrative inquiries. Source material spans scanned PDFs, digital PDFs, Word documents, spreadsheets, images, historical archives, geological/mining documents, production reports, and statistical reports.

## 2. Problem Being Solved

The current workflow is manual. This produces:

- High dependence on individual subject-matter expertise (bus-factor risk).
- Delays in report generation and analytics.
- Higher probability of manual transcription/compilation errors.
- Limited ability to quickly retrieve insights from historical archives.

## 3. Stated Objectives (from the problem statement)

1. Deploy an automated platform for AI-assisted geological, mining, and production-figure document processing and reporting.
2. Enhance data validation, consistency, and traceability across historical and contemporary datasets.
3. Build an efficient, scalable foundation for future digital transformation initiatives within each CIL subsidiary and the Ministry of Coal.

## 4. Desired Solution Components (from the problem statement)

1. **Automated Report Generation Platform**
2. **Automated Word Cloud and Topic Identification Module**
3. **AI-Based Query and Response System**

## 5. Expected Benefits (from the problem statement)

- Reduction in report preparation time.
- Improved accuracy in structured extraction and report generation.
- Maximum automation of repetitive workflows.
- Faster response to high-level inquiries and parliamentary questions.
- Improved accessibility, transparency, and standardization.
- Better use of historical information for decision support.

## 6. What Already Exists

- A working web portal built primarily on **Node.js Backend**.
- Conceptual structure already in place: `User → Folder/Workspace → Documents → Analytics → Reports → Report Generation → AI Assistant`.
- An existing open-source RAG implementation is currently wired into the portal. **This dependency is being replaced** by a custom, domain-specific document-intelligence/RAG pipeline, built as a separate service (see `02_SYSTEM_ARCHITECTURE.md`).
- Exact current internals of the Node.js Backend app (schema, auth mechanism, folder model, existing RAG integration points) are **not fully known** to this documentation pack. Wherever such details matter, this pack marks them explicitly as:

  > **VERIFY AGAINST EXISTING REPOSITORY**

  Coding agents must treat these as open questions to resolve against the actual codebase before implementing, not as license to guess.

## 7. Quality Assurance

Comprehensive testing has been performed. Refer to `testing_report.md` and `TEST_RESULTS_35_PAGE_REPORT.md` for detailed test coverage and RAG precision metrics.

## 8. What This Documentation Pack Is

A production-oriented engineering specification, written for both human engineers and AI coding agents (Claude Code, Codex, Google Antigravity, etc.), describing:

- The target system architecture (`02`).
- A domain-specific, hybrid (structured + unstructured) RAG pipeline (`03`–`07`).
- API contracts and data models for the new FastAPI AI service (`08`, `09`).
- Multi-tenancy/RBAC design shared across Node.js Backend and FastAPI (`10`).
- Citation, validation, report generation, and topic analysis modules (`11`–`13`).
- Async processing architecture (`14`).
- Deployment, security, and testing strategy (`15`–`17`).
- A phased implementation roadmap and machine-readable coding rules (`18`, `20`).
- Required environment variables (`19`).

## 8. What This Documentation Pack Is Not

- It is **not** application code.
- It does **not** rewrite the Node.js Backend application into another framework.
- It does **not** invent unstated requirements. Where the source problem statement is silent, this pack makes an explicit **architectural decision** and labels it as such (Decision / Alternatives Considered / Reason), rather than presenting it as a mandated requirement.
- It does **not** assume unlimited infrastructure. Prototype (SIH demo) and production concerns are explicitly separated throughout (see `15_DEPLOYMENT_ARCHITECTURE.md`).

## 9. Non-Negotiable Constraints Carried Through All Documents

These constraints are treated as hard requirements in every subsequent document. Any coding agent must not silently violate them:

1. The existing Node.js Backend application is the system of record for identity, organization, workspace, permissions, and document access. It is **not** rewritten.
2. A new, separate **FastAPI AI/Document Intelligence microservice** is introduced. It never independently authenticates end users and never authorizes access beyond the scope Node.js Backend grants it per request.
3. The RAG design is **hybrid**: structured facts go to PostgreSQL and are queried with parameterized/templated SQL; unstructured narrative goes through chunking, embeddings, keyword search, and reranking.
4. No fixed-size-only chunking. Chunking must be structure-aware.
5. Every AI-generated answer must be traceable to source document/page/section/chunk, and the system must prefer "no evidence found" over hallucination.
6. Large documents (up to hundreds of MB) must be processed via streaming, page-batched, asynchronous, resumable pipelines — never loaded fully into memory.
7. The LLM provider is configurable via environment variables (OpenAI-compatible interface), not hard-coded. Default target provider: GTWY (OpenAI-compatible) serving GPT-5 nano.
8. No subsidiary names are hard-coded into the architecture; the system is a generic multi-organization platform.
9. Avoid introducing LangChain, Kubernetes, Celery, Redis, Ollama (as a production dependency), or separate embedding/reranker servers unless a concrete, documented requirement justifies it. Ollama is permitted only as an optional local-dev convenience.

## 10. Reading Order

See `README.md` in this `docs/` folder for the full recommended reading order for coding agents.
