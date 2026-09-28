# 05 — Retrieval and Reranking

## 1. Retrieval Pipeline Overview

```
Query Text + Tenant Scope (org_id / workspace_id / optional document_ids)
  │
  ├── 1. Query Understanding & Normalization (Tokenization, Entity & Date Detection)
  ├── 2. Native Multi-Tenant Filter Construction (Enforced at DB / Index level)
  │
  ├───────────────────────────────────┬───────────────────────────────────┐
  │                                   │                                   │
  ▼                                   ▼                                   │
Dense Semantic Retrieval           Lexical Keyword Search                 │
(Qdrant Vector DB, top-N1)        (PostgreSQL FTS / GIN, top-N2)          │
  │                                   │                                   │
  └─────────────────┬─────────────────┘                                   │
                    │                                                     │
                    ▼                                                     │
         3. Candidate Fusion                                              │
         (Reciprocal Rank Fusion - RRF across candidate sets, top-M)      │
                    │                                                     │
                    ▼                                                     │
         4. Cross-Encoder Reranking                                       │
         (Deep query-passage relevance scoring, top-K)                   │
                    │                                                     │
                    ▼                                                     │
         5. Dynamic Context Selection                                     │
         (Token budget packing, evidence diversity, citation tagging)    │
                    │                                                     │
                    ▼                                                     │
         Synthesized Evidence Payload for LLM Generation                  │
```

---

## 2. Embedding Architecture

- **Embedding Model:** Uses a Sentence-Transformers compatible dense embedding model configurable via environment variable (`EMBEDDING_MODEL_NAME`, default: `BAAI/bge-base-en-v1.5` or `text-embedding-3-small`).
- **In-Process vs. API Agility:** Operates in-process within the worker/FastAPI service or connects to an embedding endpoint, keeping embeddings self-contained, reproducible, and offline-capable without mandatory external vendor lock-in.
- **Symmetric Vector Projection:** Embeddings are generated with identical normalization and token pooling for both document chunk ingestion and runtime query processing to guarantee cosine similarity fidelity.
- **Metric Space:** Fixed vector dimensions (e.g., 768 or 1536) utilizing Cosine Distance for similarity ranking in Qdrant collections.

---

## 3. Dense Vector Index (Qdrant)

- **Collection Topology:** A centralized Qdrant collection per deployment with index-level payload partitioning.
- **Native Multi-Tenant Filtering:** Multi-tenancy is enforced via mandatory Qdrant payload filters on `org_id` and `workspace_id`. Filtering executes natively during index traversal (HNSW graph search with filter masks), ensuring zero vector leakage across tenants and no wasted candidate retrieval budgets.
- **Indexed Payload Schema:**
  - `chunk_id`: Unique identifier of the chunk.
  - `document_id`: Reference to parent document.
  - `org_id`: Enclosing organization.
  - `workspace_id`: Enclosing workspace.
  - `page_numbers`: Array of source page integers.
  - `section_path`: Human-readable section hierarchy string.
  - `chunk_type`: Semantic category (`paragraph`, `table`, `summary`).
  - `content_hash`: Cryptographic hash for deduplication.
  - `document_version_id`: Target document revision ID.
- **Candidate Pool Size (`top-N1`):** Configurable semantic candidate threshold (default: 30 candidates).

---

## 4. Lexical Keyword Retrieval (PostgreSQL FTS)

To complement semantic vector search with exact keyword and entity recall:
- **Engine Implementation:** Utilizes PostgreSQL Native Full-Text Search (`tsvector`, `tsquery`, and GIN indexing) co-located with relational metadata.
- **Rationale:** Avoids introducing heavy search cluster dependencies (Elasticsearch/OpenSearch) while providing sub-millisecond lexical matching for exact entity names, acronyms, product codes, fiscal quarters, and numeric identifiers.
- **Index Configuration:** Each text chunk is maintained with an automatically updated `tsvector` column indexed via GIN, alongside mandatory relational filters for `org_id` and `workspace_id`.
- **Candidate Pool Size (`top-N2`):** Configurable lexical candidate threshold (default: 30 candidates).

---

## 5. Candidate Fusion via Reciprocal Rank Fusion (RRF)

Candidates retrieved from dense semantic search and lexical keyword search are combined using **Reciprocal Rank Fusion (RRF)**:

$$\text{RRF\_Score}(d) = \sum_{m \in \{\text{dense}, \text{lexical}\}} \frac{1}{k + \text{rank}_m(d)}$$

- The smoothing constant $k$ is set to 60 by default.
- **Benefits:** Merges candidates across heterogeneous scoring domains (cosine similarity vs. BM25 rank) without requiring fragile score normalization or artificial weight balancing.
- **Candidate Truncation:** The merged candidate pool is truncated to a configurable candidate count `top-M` (default: 40 candidates) to feed the reranker.

---

## 6. Cross-Encoder Reranking

- **Model:** Employs a cross-encoder model configurable via `RERANKER_MODEL_NAME` (default: `BAAI/bge-reranker-base` or `cross-encoder/ms-marco-MiniLM-L-6-v2`).
- **Mechanism:** Unlike bi-encoder vector similarity (which computes independent embeddings for query and document), the cross-encoder processes query-chunk pairs simultaneously through joint attention layers, yielding substantially more accurate relevance scores.
- **Execution Efficiency:** Reranking is evaluated only over the pre-filtered `top-M` candidate pool (40 chunks), bounding inference latency while maximizing ranking quality.
- **Output:** Produces the final top-$K$ reranked evidence set (default: $K = 8 \text{ to } 12$ chunks).

---

## 7. Dynamic Context Assembly & Selection

Prior to passing retrieved chunks to the LLM generation prompt:
1. **Rerank Score Order:** Chunks are arranged in descending order of cross-encoder confidence.
2. **Context Window Token Budget:** Chunks are packed into the prompt up to a strictly configured token budget (reserving sufficient output tokens for answer generation).
3. **Source Diversity Enforcement:** Limits the maximum number of chunks selected from any single document (e.g., maximum 4 chunks per document) to promote holistic evidence gathering across multi-document repositories.
4. **Citation Tag Binding:** Each selected chunk is tagged with an immutable citation marker (e.g., `[E1]`, `[E2]`) mapping to its document ID, page number, and section coordinates.

---

## 8. Exact Token & Numeric Optimization

To overcome semantic drift when dealing with exact figures, dates, and entity identifiers:
1. **Dual Search Legs:** The lexical FTS leg guarantees retrieval when users query exact numbers, alphanumeric serials, or specialized terminology.
2. **Deterministic SQL Routing:** When queries strictly target structured metrics, the query router bypasses text retrieval and directly executes parameterized SQL.
3. **Entity Filtering:** Confidently extracted query entities (such as fiscal years or entity identifiers) are injected as hard metadata filters across both Qdrant and Postgres FTS queries.

---

## 9. Non-Negotiable Multi-Tenant Isolation

Every retrieval query—semantic, keyword, and structured—enforces the caller's authorized scope (`org_id`, `workspace_id`, and optional document filters) as an **immutable index-level filter**. Candidates from unauthorized workspaces are excluded before ranking, eliminating any risk of cross-tenant data exposure.
