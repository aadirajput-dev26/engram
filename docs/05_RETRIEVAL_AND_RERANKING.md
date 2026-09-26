# 05 — Retrieval and Reranking

## 1. Pipeline

```
Query text + scope (org/workspace/document_ids)
  → Query understanding (normalize, detect entities: years, mine names, metrics)
  → Authorization filter (mandatory, applied at the index-query level, not post-filtering)
  → Semantic retrieval (Qdrant, top-N1)
  → Keyword retrieval (Postgres full-text search, top-N2)
  → Candidate fusion (dedupe by chunk_id, combine scores)
  → Reranking (cross-encoder, top-K)
  → Context selection (token-budget-aware assembly for the LLM prompt)
```

## 2. Embedding Strategy

- **Model:** a sentence-transformers-compatible embedding model, configurable via `EMBEDDING_MODEL_NAME` (default recommendation: `BAAI/bge-base-en-v1.5` or a comparable open, self-hostable model). Run in-process within the FastAPI/worker Python environment — **no separate embedding server**.
- **Decision:** self-hosted sentence-transformers model rather than an embedding API. **Alternatives considered:** OpenAI/GTWY embedding endpoint. **Reason:** avoids per-chunk API cost and external latency for what is typically the highest-volume operation (every chunk of every document), keeps embeddings reproducible/offline-capable, and keeps the LLM provider swap independent of the embedding pipeline. This can be revisited if a hosted embedding endpoint proves materially better for domain terminology.
- Embeddings are computed per chunk at indexing time and per query at retrieval time, using the same model (critical for cosine-similarity validity).
- Vector dimension and distance metric (cosine) are fixed by the chosen model and configured once in the Qdrant collection schema.

## 3. Vector Index (Qdrant)

- One Qdrant collection per deployment (not per organization) — **Decision**. Multi-tenancy is enforced via a **mandatory payload filter** on `org_id`/`workspace_id`/`document_id` attached to every query, using Qdrant's native filtering (not application-side post-filtering, which would leak result counts/timing and waste retrieval budget on unauthorized candidates).
  - **Alternative considered:** one Qdrant collection per organization. **Reason for rejection:** operationally heavier at scale (collection sprawl, harder to run a single reranking/tuning pipeline) with no retrieval-quality benefit, since payload filtering is efficient in Qdrant for this cardinality.
- Payload stored alongside each vector: `chunk_id`, `document_id`, `org_id`, `workspace_id`, `page_number(s)`, `section_path`, `chunk_type`, `content_hash`, `document_version_id`.
- `top-N1` (semantic candidates before fusion): configurable, default suggested 30.

## 4. Keyword Retrieval

- **Decision:** use PostgreSQL native full-text search (`tsvector`/`tsquery` + GIN index) as the keyword/BM25-equivalent retrieval mechanism, rather than deploying a separate search engine (Elasticsearch/OpenSearch) or a standalone BM25 library service.
  - **Alternatives considered:** (a) Elasticsearch/OpenSearch — rejected for the prototype as an unjustified extra infra dependency (violates the "avoid technologies without concrete requirement" principle); (b) an in-process BM25 library (e.g., `rank_bm25`) computed over the full corpus at query time — viable for small corpora but does not scale/index incrementally as well as a database-backed index.
  - **Reason:** Postgres is already a required dependency; its FTS is sufficient for exact term/entity matching (mine names, years, technical terms) at prototype and moderate production scale, and keeps operational surface area small. If corpus size or keyword-relevance quality later demands it, this is the documented upgrade path to a dedicated search engine (flagged in `15_DEPLOYMENT_ARCHITECTURE.md` production section).
- Each chunk's text is indexed into a `chunk_search` table with a generated `tsvector` column and GIN index, plus the same authorization/scope columns as Qdrant payload for filtering.
- `top-N2` (keyword candidates before fusion): configurable, default suggested 30.

## 5. Candidate Fusion

- Candidates from semantic and keyword retrieval are merged by `chunk_id`.
- Fusion score: **Decision** — reciprocal rank fusion (RRF), a well-understood, parameter-light method: `score(chunk) = Σ 1 / (k + rank_in_list)` across whichever lists the chunk appeared in (k default 60). **Alternative considered:** weighted linear combination of raw semantic similarity and BM25/FTS rank scores — rejected as the first default because raw score scales from the two systems are not directly comparable without calibration; RRF avoids needing that calibration. Weighted combination remains available as a tunable alternative once evaluation data (see `17_TESTING_STRATEGY.md`) justifies it.
- Fused list is truncated to a configurable `top-M` (default suggested 40) before reranking.

## 6. Reranking

- **Model:** a cross-encoder reranker, configurable via `RERANKER_MODEL_NAME` (default recommendation: `BAAI/bge-reranker-base` or comparable), run in-process (no separate reranker server), same rationale as embeddings (§2).
- Reranker scores each (query, candidate chunk) pair directly (more accurate than bi-encoder similarity, more expensive per pair — hence only run over the fused top-M, not the whole corpus).
- Output: top-K reranked chunks (default suggested K = 8–12) passed to context selection.

## 7. Context Selection

- Chunks are assembled into the LLM context in **descending rerank score**, subject to:
  - A total token budget (configurable, tied to the target LLM's context window and `max_tokens` reserved for the answer).
  - A per-document cap (configurable, e.g., no more than 4 chunks from a single document) to encourage evidence diversity for comparison-style questions, unless the query is clearly single-document-scoped.
- Each included chunk is tagged with a stable citation marker (e.g., `[C1]`, `[C2]`) mapped to its `chunk_id`/`document_id`/`page_number`/`section_path` for citation generation (see `11_CITATION_AND_VALIDATION.md`).

## 8. Optimizing for Exact Figures, Names, Dates

Because pure semantic retrieval under-performs on exact tokens (numbers, proper nouns, dates), this pipeline structurally compensates via:
1. The keyword/FTS leg of hybrid retrieval, which matches exact terms well.
2. The **query router** (see `07_AI_QUERY_ENGINE.md`) diverting genuinely structured/numeric questions to the structured-data path entirely, bypassing retrieval-based uncertainty for exact figures.
3. Query understanding extracting explicit entities (years, mine names, metric names) from the user's question and using them as **mandatory metadata filters** (not just soft ranking signals) on both Qdrant and Postgres FTS queries when confidently detected — e.g., a detected year "2023" filters candidates to chunks/facts whose extracted date range includes 2023.

## 9. Authorization Filtering (repeat, load-bearing)

Every retrieval call — semantic, keyword, and structured — must include the caller's resolved scope (`org_id`, `workspace_id`, `allowed_document_ids`) as a **native filter clause**, not a post-hoc filter applied after fetching results. This is validated in integration tests (see `17_TESTING_STRATEGY.md`) by asserting that no result outside the granted scope is ever returned, even when it would otherwise rank highly.
