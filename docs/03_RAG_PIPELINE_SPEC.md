# 03 — RAG Pipeline Specification

## 1. Why Not a Generic PDF→Chunks→Embeddings→Vector DB→LLM Pipeline

The domain contains dense exact figures (production numbers, targets, achievements, mine names, years, coal grades) intermixed with narrative explanation. A pure vector-RAG pipeline:

- Frequently retrieves the wrong chunk for exact-figure questions (semantic similarity does not guarantee the correct row/year/mine is retrieved).
- Cannot reliably answer aggregate/comparison questions ("total production across all subsidiaries in 2023") because that requires computation over structured data, not text retrieval.
- Has no natural mechanism to guarantee numeric fidelity, which is essential for parliamentary-grade reporting.

Therefore this system splits information into two parallel tracks that are fused at query time.

## 2. End-to-End Pipeline (conceptual)

```
Document
  → Ingestion & validation
  → Classification (digital / scanned / office / spreadsheet / image)
  → OCR (if scanned) / native parsing (if digital)
  → Structure understanding (pages → sections → subsections → tables → paragraphs)
  → Metadata extraction (title, dates, doc type, subsidiary/mine hints)
  → [Structured extraction track]      [Unstructured chunking track]
       → candidate facts                 → structure-aware chunks
       → validation & normalization      → chunk metadata (doc/page/section)
       → PostgreSQL (structured facts)   → embeddings → Qdrant
                                          → keyword index (Postgres FTS)
  → READY (both tracks indexed; job status updated)

Query
  → Query understanding & classification (structured / RAG / hybrid)
  → [structured path]                  [RAG path]
       → parameter extraction            → semantic retrieval (Qdrant)
       → validated query plan            → keyword retrieval (Postgres FTS)
       → parameterized SQL execution     → candidate fusion
                                          → reranking
                                          → context selection
  → Answer composition (LLM), constrained to retrieved/queried evidence
  → Claim-to-evidence validation
  → Citation attachment
  → Response (or "no evidence found")
```

## 3. Pipeline Stages — Responsibilities

| Stage | Input | Output | Detail Doc |
|---|---|---|---|
| Ingestion & validation | Raw file bytes/object storage ref | Validated file, detected MIME/type | `04_DOCUMENT_PROCESSING_SPEC.md` |
| Classification | Validated file | `digital_pdf \| scanned_pdf \| docx \| xlsx \| csv \| image` | `04` |
| OCR/Parsing | Classified file | Raw page text + layout boxes | `04` |
| Structure understanding | Raw page text + layout | Section/subsection tree, table regions, PageIndex-style page map | `04` |
| Metadata extraction | Structure tree | Document-level metadata (title, dates, doc type, detected entities) | `04` |
| Structured extraction | Structure tree + tables + text | `ExtractedFact` rows in PostgreSQL | `06_STRUCTURED_DATA_EXTRACTION.md` |
| Chunking | Structure tree | Structure-aware `Chunk` records | `04` |
| Embedding & indexing | Chunks | Qdrant vectors + Postgres FTS rows | `05_RETRIEVAL_AND_RERANKING.md` |
| Query routing | User query + scope | Query plan (`structured`/`rag`/`hybrid`) | `07_AI_QUERY_ENGINE.md` |
| Retrieval & reranking | Query plan | Ranked evidence set | `05` |
| Answer generation | Evidence set + query | Draft answer + claims | `07`, `11_CITATION_AND_VALIDATION.md` |
| Validation | Draft answer + evidence | Verified answer or "no evidence found" | `11` |
| Citation attachment | Verified answer + evidence | Final `QueryResponse` with citations | `11` |

## 4. Structured vs. Unstructured — Decision Rule

Used both during **extraction** (what goes to Postgres vs. what stays as narrative chunks) and during **query routing** (see `07_AI_QUERY_ENGINE.md`).

A span of content is treated as **structured** if it expresses one or more discrete, typed facts of the form:
`(metric, value, unit, mine?, subsidiary?, coal_grade?, year/period, source_location)`
— e.g., a table row "Mine X | 2023 | Target: 4.2 MT | Achievement: 3.9 MT".

A span is treated as **unstructured/narrative** if it explains, justifies, describes, or recommends — e.g., "Production fell short of target due to heavy monsoon rainfall and equipment downtime at Mine X."

**Important:** the same document region can produce both — a table row becomes an `ExtractedFact`, and an adjoining paragraph explaining that row becomes a `Chunk`. They are cross-linked via `document_id` + `page_number` + (optionally) `section_id` so hybrid queries can join them.

## 5. Hallucination Prevention — Core Principle

The LLM is **never** asked to answer from parametric memory. Every prompt sent to the LLM for question-answering or report drafting includes only:
- The retrieved/queried evidence (structured rows and/or ranked chunks), each tagged with a citation ID.
- An explicit instruction to answer only from the provided evidence, and to say `NO_EVIDENCE_FOUND` (a defined sentinel) if the evidence does not answer the question.

Post-generation, a validation step checks that every factual/numeric claim in the answer maps back to a citation ID actually present in the evidence set (see `11_CITATION_AND_VALIDATION.md`). Claims that fail this check are stripped or the whole answer is downgraded to "no evidence found," rather than shown as-is.

## 6. Reusable Core vs. Domain-Specific Layer

- Reusable: stages 1–2 (ingestion/classification), OCR/parsing, structure understanding, chunking, embedding/indexing infrastructure, retrieval/reranking infrastructure, the query-routing *framework*, the validation/citation *framework*.
- Domain-specific: the structured-fact schema (`06_STRUCTURED_DATA_EXTRACTION.md`), extraction prompts/regex tuned for mining/production terminology, report templates (`12_REPORT_GENERATION.md`), and topic-analysis vocabulary (`13_TOPIC_ANALYSIS.md`).

This separation must be reflected in code module boundaries (see `18_IMPLEMENTATION_ROADMAP.md`, Phase 0).
