# 12 — Report Generation

## 1. Purpose

Automate compilation of geological/mining/production reports and responses to administrative/parliamentary inquiries, while preserving full traceability to source documents.

## 2. Report Types (extensible, not exhaustive)

- `production_summary` — structured aggregate + narrative context for a mine/subsidiary/period.
- `parliamentary_response_draft` — answer to a specific inquiry question, structured similarly to a `hybrid` query response but formatted as a formal document with sections.
- `custom` — a user-defined outline of sections, each independently populated using the same evidence-gathering/validation pipeline.

New report types are added by defining a new `parameters` sub-schema and a section-template mapping — not by changing the core generation engine.

## 3. Generation Pipeline

```
ReportGenerateRequest (report_type, parameters, scope)
  → Resolve report outline (fixed template per report_type, or user-supplied outline for "custom")
  → For each section:
       → Formulate section-specific sub-query/queries (reusing the query router, 07_AI_QUERY_ENGINE.md)
       → Retrieve structured facts + RAG evidence for that section
       → Draft section content (LLM), constrained to retrieved evidence (same constraints as 11_CITATION_AND_VALIDATION.md)
       → Validate claims in the section (evidence verification pipeline)
       → Attach citations to the section
  → Assemble full report (ordered sections + a consolidated source list/bibliography)
  → Render to DOCX/PDF
  → Persist ReportDraft + citation trail
  → Notify Express (job completion) → Express persists report metadata & exposes to user
```

## 4. Explicit Non-Negotiable

> Do not blindly let the LLM generate an entire report from memory.

Enforced by: every section's content generation call is scoped to that section's retrieved evidence only (same evidence-block/citation-marker mechanism as `07`/`11`), and every section passes through claim validation before being included. A section for which no qualifying evidence is found is rendered with an explicit placeholder (e.g., "No supporting documentation was found for this section — manual input required") rather than omitted silently or filled with unsupported prose.

## 5. Structured + Narrative Fusion in Report Sections

Report sections routinely need both: e.g., a "Production Performance" section needs the exact production/target/achievement figures (structured) and the narrative explanation of variance (RAG). Each section's sub-query is classified/handled via the same `HYBRID` mechanism as `07_AI_QUERY_ENGINE.md` §6, reusing that logic rather than duplicating it — the report generator is a *consumer* of the query engine, not a separate reasoning path.

## 6. Output Rendering

- **DOCX:** rendered via a Python DOCX library (e.g., `python-docx`), using a base template (heading styles, standard header/footer for CMPDI/Ministry-style formatting — exact branding/template details: **VERIFY AGAINST EXISTING REPOSITORY / stakeholder input**, not invented here).
- **PDF:** either rendered directly or produced by converting the DOCX output (implementation choice, to be decided in Phase 15 based on available libraries in the deployment environment — flagged as an open implementation decision, not a fixed requirement).
- Every rendered report embeds a source list (document name, page, section) per section, and ideally per-claim footnote-style references where the output format supports it.

## 7. Asynchronous Execution

Report generation is always asynchronous (`POST /api/v1/reports/generate` returns a `job_id`; result fetched via `GET /api/v1/reports/{job_id}`), because it involves multiple retrieval/generation/validation passes (one or more per section) and can take longer than a typical synchronous request budget, especially for multi-section reports. See `14_ASYNC_PROCESSING.md`.

## 8. Review & Approval

- Generated reports are drafts by default (`ReportDraft.status`). The `reports.approve` capability (see `10_MULTI_TENANCY_RBAC.md`) gates whether a report is marked as finalized/approved within Express — this approval workflow lives in Express (it is business-process state, not AI-processing state), with FastAPI only ever producing drafts and their evidence trails.

## 9. Failure Handling

- If a section repeatedly fails validation (e.g., evidence is too sparse/contradictory), the report job status becomes `PARTIAL` with the failing sections flagged, not silently dropped and not blocking the sections that did succeed.
