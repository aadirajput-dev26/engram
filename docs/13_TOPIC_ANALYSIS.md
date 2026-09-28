# 13 — Corpus Analytics & Topic Modeling

## 1. Engine Purpose

The Corpus Analytics & Topic Modeling engine analyzes document collections to surface recurring themes, salient keywords, named entities, and conceptual clusters across historical archives and multi-document repositories, producing structured feeds for visualizations and exploratory search.

---

## 2. Analytical Pipeline

```
Topic Analysis Request (Target Scope: workspace_id / document_ids)
  │
  ▼
[Corpus Extraction & Preprocessing]
  ├── Gathers text chunks for all designated, `READY` documents
  ├── Normalization: Case folding, punctuation removal, lemmatization
  └── Stopword Filtering: Combines standard language stopwords with enterprise noise words
  │
  ▼
[Salience & Statistical Modeling]
  ├── TF-IDF Vectorization: Computes term importance scores across the selected corpus
  ├── Topic Modeling:
  │     ├── Lightweight Mode: Non-negative Matrix Factorization (NMF) or Latent Dirichlet Allocation (LDA)
  │     └── Semantic Mode: BERTopic / sentence-embedding clustering (utilizing existing embedding model)
  └── Named Entity Recognition (NER): Identifies organizations, facilities, dates, currencies, and products
  │
  ▼
[Payload Serialization & Result Caching]
  ├── Formats term frequencies for Word Cloud rendering
  ├── Compiles labeled topics with representative document references
  └── Persists `TopicResult` and marks job `READY`
```

---

## 3. Techniques & Algorithms

- **Keyword Salience (TF-IDF):** Evaluates term frequency inversely scaled by document frequency, isolating terms that are distinctively characteristic of the analyzed collection.
- **Thematic Clustering:** Groups conceptually related chunks into coherent topics with representative keywords and sample passages.
- **Named Entity Recognition (NER):** Extracts business entities, locations, financial quantities, and temporal expressions, cross-referencing with the enterprise `entity_aliases` table to resolve organizational acronyms.

---

## 4. Scope Isolation & Multi-Tenancy

Corpus analysis is strictly partitioned by the caller's tenant credentials. The engine enforces mandatory relational filters on `org_id` and `workspace_id` when assembling candidate chunks, guaranteeing that analytics never incorporate data across tenant boundaries.

---

## 5. Asynchronous Job Execution

Analyzing extensive document corpora can be computationally demanding. The analysis engine executes asynchronously:
- Requests return an immediate HTTP `202 Accepted` with a `job_id`.
- The task runs in a background worker process.
- Completed results are polled via `GET /api/v1/topics/{job_id}`.

---

## 6. Output Schemas & Client Consumption

The output payload provides structured objects designed for direct front-end visualization:

- `word_cloud_data`: Array of `{ "term": str, "weight": float, "frequency": int }` ready for word-cloud components.
- `topics`: Array of `{ "topic_id": str, "label": str, "top_terms": list[str], "document_references": list[UUID] }`.
- `entities`: Aggregated named entity counts categorized by entity type (`ORGANIZATION`, `PRODUCT`, `LOCATION`, `DATE`).
