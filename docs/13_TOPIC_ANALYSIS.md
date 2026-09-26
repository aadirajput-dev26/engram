# 13 — Topic Identification & Word Cloud Analysis

## 1. Purpose

Deliver the "Automated Word Cloud and Topic Identification Module" requirement: surface recurring themes, key terms, and named entities across a selected document collection (workspace, folder, or explicit document set) to support faster insight retrieval from historical archives.

## 2. Pipeline

```
TopicAnalysisRequest (scope: org/workspace/document_ids)
  → Gather chunk text for all in-scope, READY documents
  → Preprocessing: tokenization, stopword removal (domain-aware stopword list, not just generic English),
     normalization (case-folding, lemmatization)
  → Keyword extraction: TF-IDF over the in-scope corpus
  → Topic modeling: cluster/label recurring themes
  → Named entity extraction: mine names, subsidiary names, locations, dates, organizations
  → Aggregate into word-cloud-ready frequency data
  → Persist TopicResult; mark job READY
```

## 3. Techniques Used

- **Keyword extraction:** TF-IDF (scikit-learn `TfidfVectorizer` or equivalent) computed over the in-scope chunk corpus — straightforward, transparent, no additional infra.
- **Topic modeling:** **Decision** — start with a lightweight approach (e.g., TF-IDF + clustering, or classical LDA) as the default, with **BERTopic as an optional, configurable upgrade** (`TOPIC_MODEL_BACKEND=lda|bertopic`) for when embedding-based topic quality is worth the extra compute cost (BERTopic uses the same embedding model already loaded for RAG, §`05`, so no new model dependency is introduced if enabled — it reuses `EMBEDDING_MODEL_NAME`).
  - **Alternative considered:** BERTopic as the only/default option. **Reason for not defaulting to it:** heavier compute per run than TF-IDF/LDA for what is, in the prototype, likely a modest document collection size; keeping it optional avoids over-provisioning the prototype infra while leaving a clear upgrade path.
- **Named entity extraction:** a standard NLP NER pipeline (e.g., spaCy) tuned/extended with a domain gazetteer (known mine/subsidiary names, reusing the `entity_alias` table from `06_STRUCTURED_DATA_EXTRACTION.md` §4) to catch domain-specific entities that generic NER models miss.

## 4. Scope Enforcement

Same authorization model as retrieval (`05_RETRIEVAL_AND_RERANKING.md` §9): the chunk corpus gathered for analysis is filtered by the caller's `allowed_document_ids`/`workspace_scope` before any text leaves the authorization boundary — never analyze then filter.

## 5. Asynchronous Execution

- Topic analysis over more than a small number of documents/chunks (configurable threshold, e.g., >20 documents or >2000 chunks) always runs as an async job (`14_ASYNC_PROCESSING.md`), reported via `job_id`/status polling as in `08_API_CONTRACTS.md` §7–8.
- Below the threshold, the same code path may still be invoked synchronously for responsiveness in small-workspace demos, but the API surface remains async-shaped (`job_id` returned immediately, even if resolved near-instantly) to avoid two different client code paths.

## 6. Output Consumption

- `word_cloud_data`: term + normalized frequency weight, directly consumable by any frontend word-cloud rendering library.
- `topics`: labeled clusters with representative document references — enables "drill into this topic" navigation back to source documents (reusing citation-style document/page references).
- `entities`: aggregated named entity counts, useful for both word-cloud-adjacent visualizations and as an input signal for the structured-extraction alias table (`06`) — new frequently-seen entity variants surfaced here are a natural feed for expanding `entity_alias`, though that reconciliation is a manual/administrative step in v1, not automatic.

## 7. Non-Goals (v1)

- Real-time/streaming topic updates as documents are added — v1 is run-on-demand per collection, not a continuously maintained live index. Flagged as a future enhancement if usage patterns demand it.
