# 20 — AI Coding Rules & Architectural Guidelines

These engineering rules are strictly binding on any AI coding agent or engineer modifying, refactoring, or extending this codebase.

---

## 1. Architectural Integrity & Boundaries

1. **Understand Before Modifying:** Always review the corresponding architectural specification (`docs/00` through `docs/19`) before altering existing modules. Do not infer system boundaries from partial code snippets.
2. **Preserve Modular Architecture:** Respect the separation between the universal engine core (`app/core/`, `app/services/`, `app/api/`) and domain-specific schemas or models (`app/domain/`, `app/models/`).
3. **No Unjustified Dependencies:** Do not introduce heavy external framework abstractions (such as LangChain, LlamaIndex, or Celery) when native, lightweight, and auditable implementations (PyMuPDF, sentence-transformers, Qdrant client, PostgreSQL `SKIP LOCKED` queues) already fulfill requirements.
4. **Configuration-Driven Parameters:** Never hard-code API endpoints, model identifiers, token budgets, or thresholds. Centralize all configuration in `app/core/config.py` backed by environment variables (`docs/19_ENVIRONMENT_VARIABLES.md`).

---

## 2. Security & Multi-Tenant Invariants

5. **Mandatory Tenant Scoping:** Every database query, vector search, and document operation **must enforce `org_id` and `workspace_id` scoping**. Never implement un-scoped or global queries that risk cross-tenant data exposure.
6. **No Free-Form LLM SQL:** Never pass raw LLM generation strings directly into SQL execution engines. All structured database interactions must use pre-compiled, parameterized templates or ORM query builders.
7. **Document Text as Untrusted Input:** Treat all document content as untrusted input. Encapsulate passages within explicit `<evidence>` XML delimiters and provide explicit instructions to prevent prompt injection.
8. **Cryptographic Secret Hygiene:** Plaintext API keys must never be logged or stored in database tables. Store only cryptographic hashes (`key_hash`) and short identification prefixes (`key_prefix`).

---

## 3. Data Flow, Grounding & Provenance

9. **Zero-Hallucination Fallback:** If retrieved context is insufficient to answer an inquiry, return the explicit sentinel `NO_EVIDENCE_FOUND`. Never invent or extrapolate factual assertions from parametric memory.
10. **Immutable Provenance Tracking:** Every text chunk, structured fact, and generated citation must retain full provenance coordinates (`document_id`, `document_version_id`, `page_number`, `section_path`).
11. **Post-Generation Fact Verification:** Generated answers must undergo programmatic claim extraction and numeric validation against underlying structured records or source chunks.

---

## 4. Code Quality & Implementation Standards

12. **Strong Typing with Pydantic & Type Hints:** All request/response contracts, intermediate payloads, and domain objects must use strict Pydantic schemas and Python type annotations.
13. **Structured Logging:** Use structured JSON loggers (`app/core/logging.py`) rather than raw `print()` statements. Never log sensitive document passages, full generation prompts, or authentication tokens.
14. **Deterministic Error Handling:** I/O operations (database queries, network requests, vector upserts, OCR subprocesses) must catch exceptions explicitly and transition job states to `FAILED` or `PARTIAL` with diagnostic codes rather than raising unhandled errors.
15. **Streaming & Bounded Memory:** Process multi-page documents using page-batched streaming pipelines. Avoid loading entire multi-hundred-megabyte files into memory buffers.
16. **Documentation Synchronization:** Whenever modifying API contracts, database schemas, or pipeline parameters, immediately update the relevant documentation files in `docs/` in the same commit.
