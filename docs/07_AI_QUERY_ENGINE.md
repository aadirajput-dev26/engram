# 07 — AI Query Engine & Router

## 1. Engine Purpose

When a natural-language query arrives from a client application along with an authorized tenant scope (`org_id`, `workspace_id`), the **AI Query Engine** determines the optimal execution strategy:
1. **STRUCTURED:** Executes deterministic, parameterized SQL queries against normalized `ExtractedFact` tables in PostgreSQL (ideal for exact figures, KPIs, temporal comparisons, and arithmetic aggregations).
2. **UNSTRUCTURED (RAG):** Executes hybrid semantic and lexical retrieval followed by reranking and constrained LLM synthesis (ideal for conceptual, explanatory, or policy questions).
3. **HYBRID:** Jointly executes structured SQL and unstructured retrieval, fusing exact metrics and narrative context into a unified, cited answer.

---

## 2. Intent Classification & Routing

```
Natural Language User Query + Tenant Scope (API Key)
  │
  ▼
[Intent & Entity Classifier]
  ├── Extracts targeted metrics, entities, dates, and comparison intents
  ├── Outputs strict Pydantic-validated classification schema:
  │     {
  │       "route": "STRUCTURED" | "UNSTRUCTURED" | "HYBRID",
  │       "target_metrics": ["revenue", "operating_margin"],
  │       "target_entities": ["Division Alpha", "Product Line B"],
  │       "temporal_periods": ["2023", "2024"],
  │       "is_comparison": true,
  │       "confidence": 0.94
  │     }
  │
  ├───────────────────────────────────┬───────────────────────────────────┐
  │                                   │                                   │
  ▼ (if STRUCTURED)                   ▼ (if UNSTRUCTURED)                 ▼ (if HYBRID)
Structured SQL Track               Hybrid RAG Track                    Dual Fusion Track
(Exact metrics via SQL)            (Semantic/Lexical + Reranker)       (SQL facts + Reranked prose)
```

- **Classification Mechanism:** Uses a fast, low-latency LLM call or fine-tuned sequence classifier outputting strict JSON conforming to a Pydantic model (`QueryClassification`).
- **Safety Fallback:** If classification confidence is marginal or parsing fails, the router defaults to **`HYBRID`** mode, ensuring both structured data and narrative evidence are queried rather than risking missing information.

---

## 3. Query Archetypes & Routing Matrix

| Query Archetype | Example Query | Selected Route | Execution Behavior |
|---|---|---|---|
| **Exact Metric Lookup** | *"What was the operating revenue for Division Alpha in FY2023?"* | `STRUCTURED` | Direct SQL point query against normalized facts. Zero LLM hallucination risk. |
| **Comparative / Aggregation** | *"What was the total capital expenditure across all business units in 2024?"* | `STRUCTURED` | Deterministic SQL `SUM()` aggregation grouped by entity. |
| **Qualitative / Explanatory** | *"What operational risks were identified regarding international supply chains?"* | `UNSTRUCTURED` | Dense vector (Qdrant) + Lexical FTS search, RRF fusion, cross-encoder rerank, and synthesis. |
| **Multi-Faceted Synthesis** | *"Compare the decline in regional profit margin with the operational challenges cited in the annual review."* | `HYBRID` | Retrieves exact margin numbers via SQL and explanatory paragraphs via RAG; synthesizes both into a unified answer. |

---

## 4. Structured Path: Deterministic Security & Correctness

> **Core Security Invariant:** The LLM is **never permitted to generate unconstrained, raw SQL strings**. All database queries are executed via pre-compiled, parameterized query templates.

### 4.1 Parameterized Query Execution
1. The classifier parses query intent into a strongly typed `StructuredQueryPlan` (containing sanitized strings for entity, metric, and period).
2. The query plan maps deterministically to a verified Python query template using the ORM / query builder:
   - `get_metric_by_entity_and_period(entity, metric, period, workspace_id)`
   - `get_metric_aggregate(entities[], metric, period, workspace_id)`
   - `compare_metric_temporal_delta(entity, metric, period_start, period_end, workspace_id)`
3. Mandatory Multi-Tenant Predicate: Every template parameterizes `workspace_id` and `org_id`. A query cannot be constructed without these security constraints.
4. Unsupported Queries: If a query plan cannot map cleanly to a pre-validated template, the engine falls back to `UNSTRUCTURED` RAG rather than executing unvetted dynamic SQL.

---

## 5. Unstructured (RAG) Path

For qualitative, descriptive, or policy questions:
1. **Hybrid Retrieval:** Dispatches parallel queries to Qdrant (dense vectors) and PostgreSQL FTS (lexical GIN index) scoped by `workspace_id`.
2. **Fusion & Reranking:** Applies Reciprocal Rank Fusion (RRF) to merge candidate pools, followed by cross-encoder scoring to yield top-$K$ passages.
3. **Synthesis:** Injects reranked passages into an LLM prompt with strict grounding constraints.
4. **Verification:** Validates that all factual claims match cited passages and outputs the answer with source references.

---

## 6. Hybrid Fusion Path

When answering complex enterprise questions that bridge numbers and explanations:
1. **Structured Retrieval:** Fetches exact metric rows from PostgreSQL into a structured evidence table.
2. **Context-Biased Retrieval:** Uses the entities, metrics, and source pages of the structured facts to guide hybrid retrieval, ensuring narrative chunks discussing those exact numbers are retrieved.
3. **Unified Context Assembly:** Injects both evidence types into the synthesis prompt with distinct citation tags:
   - `[F1]`, `[F2]` for verified structured facts (exact numbers and dates).
   - `[C1]`, `[C2]` for narrative context chunks.
4. **Coordinated Verification:** The validation engine enforces exact equality for numeric claims referencing `[F#]` tags and semantic entailment for claims referencing `[C#]` tags.

---

## 7. Graceful Failure & Zero-Hallucination Policy

- When retrieved evidence does not support an answer, the engine outputs `no_evidence: true` and a clear explanatory sentinel (`"No supporting evidence found in the ingested documents."`).
- The system explicitly avoids generating speculative or unverified statements.
