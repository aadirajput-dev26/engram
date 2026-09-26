# 20 — AI Coding Rules

These rules are binding on any AI coding agent (Claude Code, Codex, Google Antigravity, or others) working on this codebase. They apply in addition to, not instead of, the specific architectural decisions in documents `00`–`19`.

## 1. Before Writing Code

1. **Read all relevant documentation before modifying code.** At minimum: `00_PROJECT_CONTEXT.md`, `02_SYSTEM_ARCHITECTURE.md`, and the specific document(s) covering the area being changed. Do not infer architecture from code alone when documentation exists.
2. **Do not rewrite working Express functionality unnecessarily.** The Express application is the existing, working core business backend. Only touch it where this pack explicitly calls for integration (`18_IMPLEMENTATION_ROADMAP.md` Phase 13) or where a documented requirement demands it.
3. **Do not replace the architecture without explicit justification.** If a documented decision (marked "Decision" in any file) seems wrong once real implementation constraints are discovered, document the new decision (Decision / Alternatives Considered / Reason) and update the relevant `.md` file — do not silently diverge from documented architecture in code.
4. **Do not introduce dependencies without checking whether they are necessary.** In particular, do not add LangChain, Kubernetes, Celery, Redis, Ollama (as a production dependency), or separate embedding/reranker servers unless a concrete, documented requirement justifies it (per `09_SYSTEM_ARCHITECTURE.md` §9 / project brief §9). If a new dependency seems genuinely needed, document the decision and its justification before adding it.
5. **Where existing implementation details are unknown, do not invent them.** Any place this documentation says "VERIFY AGAINST EXISTING REPOSITORY," actually inspect the existing repository before implementing — do not guess and proceed as if the guess were confirmed.

## 2. While Writing Code

6. **Do not hide core RAG logic behind frameworks unnecessarily.** The team explicitly wants to understand and own the retrieval/embedding/reranking/generation pipeline. Prefer direct, readable Python implementations (using well-chosen libraries like PyMuPDF, sentence-transformers, Qdrant client) over wrapping the whole pipeline in a high-level orchestration framework that obscures what's happening.
7. **Keep modules small and testable.** Respect the reusable-core (`app/core/`) vs. domain-specific (`app/domain/`) boundary established in `02_SYSTEM_ARCHITECTURE.md` §7 and `18_IMPLEMENTATION_ROADMAP.md` Phase 0.
8. **Use Pydantic models** for every request/response and internal domain object crossing a module boundary, matching `09_DATA_MODELS.md`. Do not pass around untyped dicts for domain data.
9. **Use type hints** throughout Python code.
10. **Use structured logging** (not bare `print`), and never log full document content, full prompts, or secrets at default log levels (`16_SECURITY.md` §9).
11. **Handle errors explicitly.** Every I/O call (DB, object storage, Qdrant, LLM API, OCR) must have explicit error handling that results in a defined state (`FAILED`/`PARTIAL` stage status, structured API error response) — never an unhandled exception that silently loses job state.
12. **Never hard-code secrets.** All configuration comes from environment variables listed in `19_ENVIRONMENT_VARIABLES.md`; add new variables there when introducing new configuration.
13. **Never bypass tenant/document authorization.** Every data-access function that touches documents/chunks/facts must accept and apply an authorization scope as a mandatory parameter — there is no "trusted internal call" that skips this, per `16_SECURITY.md` §2 and §10 checklist.
14. **Preserve source metadata.** Any transformation of document content (OCR → text, text → chunks, chunks → facts) must carry forward `document_id`/`page_number`/`section_path` provenance. Never produce a chunk, fact, or citation that cannot be traced to its source.
15. **Never fabricate citations.** A citation must reference a `chunk_id`/`fact_id` that genuinely was part of the evidence used to produce the associated claim, verified by the mechanism in `11_CITATION_AND_VALIDATION.md`.
16. **Never return unsupported factual claims.** If evidence verification fails or no evidence exists, the correct output is an explicit "no evidence found" response, never a best-effort guess presented as fact.

## 3. Process Discipline

17. **Implement incrementally**, following the phase order in `18_IMPLEMENTATION_ROADMAP.md` unless a specific phase's dependencies are already satisfied and parallelization is explicitly noted as safe.
18. **Run tests after meaningful changes.** Unit tests for the module changed, plus relevant integration tests where the change crosses a service boundary or touches authorization/retrieval logic.
19. **Update documentation when architecture changes.** If an implementation detail forces a deviation from a documented "Decision," update that document's Decision/Alternatives/Reason block in the same change, not as a follow-up "someday" task.
20. **Do not create duplicate functionality.** Before implementing a new utility (e.g., another chunker, another job-queue mechanism, another LLM client wrapper), check whether an existing one in `app/core/` already serves the purpose and should be extended instead.
21. **Prefer simple solutions over unnecessary abstractions.** E.g., prefer the fixed structured-query-template approach (`07_AI_QUERY_ENGINE.md` §4) over building a generic query DSL until the documented evolution trigger is actually reached.

## 4. Consistency Rule

If a decision appears in multiple documents (e.g., the choice of Postgres FTS over a dedicated search engine, appearing in both `05` and `15`), any change to that decision must be propagated to every document that references it, to avoid contradictions between files.
