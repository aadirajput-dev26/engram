# 06 — Structured Data Extraction

## 1. Architectural Purpose

The Structured Data Extraction module extracts discrete, typed, queryable quantitative facts from enterprise documents into PostgreSQL. By persisting tabular and numeric facts into a strongly typed relational schema, exact computational questions (such as sums, averages, comparisons, and threshold evaluations) are resolved deterministically via parameterized SQL, bypassing the stochastic uncertainties of vector search.

---

## 2. Universal Extracted Fact Schema

The `ExtractedFact` relational entity models any quantitative enterprise assertion:

| Field | Data Type | Description |
|---|---|---|
| `id` | `UUID` | Primary key identifier for the fact. |
| `org_id` | `UUID` | Multi-tenant organization scope. |
| `workspace_id` | `UUID` | Workspace partition scope. |
| `document_id` | `UUID` | Source document reference. |
| `document_version_id` | `UUID` | Version tracking reference. |
| `page_number` | `INTEGER` | Source page number. |
| `section_path` | `VARCHAR(512)` | Human-readable section hierarchy breadcrumb. |
| `table_id` | `UUID` (Nullable) | Associated table entity ID if derived from a parsed table. |
| `entity_name` | `VARCHAR(256)` | Primary business entity (e.g., company, division, department, product line, project, facility). |
| `entity_type` | `VARCHAR(64)` | Classification of the entity (e.g., `business_unit`, `facility`, `account`, `product`). |
| `metric_name` | `VARCHAR(128)` | Standardized metric (e.g., `revenue`, `operating_expense`, `target`, `achievement`, `headcount`, `volume`, `variance`). |
| `metric_raw_label` | `VARCHAR(256)` | Verbatim header/label as it appeared in the document. |
| `value` | `NUMERIC(18, 4)` | Normalized floating-point or fixed-precision scalar. |
| `unit` | `VARCHAR(64)` | Standardized unit of measurement (e.g., `USD`, `EUR`, `percentage`, `units`, `metric_tons`, `hours`). |
| `period_type` | `VARCHAR(32)` | Temporal classification (`calendar_year`, `fiscal_year`, `quarter`, `month`, `point_in_time`). |
| `period_value` | `VARCHAR(64)` | Normalized period representation (e.g., `2024`, `FY2024`, `Q3-2024`). |
| `confidence` | `FLOAT` | Composite confidence score (0.0 to 1.0) incorporating OCR and parser confidence. |
| `extraction_method` | `VARCHAR(32)` | Pipeline strategy (`table_parser`, `pattern_rule`, `llm_assisted`). |
| `raw_text` | `TEXT` | Raw text snippet or table cell content for audit provenance. |
| `created_at` | `TIMESTAMPTZ` | Timestamp of ingestion. |

---

## 3. Tiered Extraction Pipeline

To maximize throughput, auditability, and precision, extraction proceeds through three tiered stages:

```
Document Section / Table Region
  │
  ├── Tier 1: Deterministic Table Parser (Highest Confidence: 0.90 - 1.0)
  │     ├── Detect column headers, multi-level spans, and row stubs
  │     ├── Map tabular matrices directly to ExtractedFact tuples
  │     └── If successfully resolved → Emit facts & finish
  │
  ├── Tier 2: Pattern-Based Rule Extractor (Medium Confidence: 0.75 - 0.90)
  │     ├── Apply regex patterns for standardized narrative assertions
  │     │   (e.g., "<Entity> reported <Metric> of <Value> <Unit> for <Period>")
  │     └── If pattern matches → Emit facts & finish
  │
  └── Tier 3: LLM-Assisted Structured Fallback (Selective: Confidence 0.60 - 0.85)
        ├── Invoked only for complex/unstructured tabular layouts or ambiguous syntax
        ├── Prompt constrained strictly with a Pydantic-validated JSON schema
        └── Facts stamped with extraction_method="llm_assisted"
```

> **Design Principle:** Deterministic tabular parsing and pattern matching are preferred over unconstrained LLM calls. Deterministic parsers eliminate hallucination risks, operate with near-zero marginal cost, and provide transparent audit trails.

---

## 4. Entity Normalization & Alias Mapping

Enterprise documents regularly use disparate naming conventions for the same entity or metric (e.g., *"North America Logistics Division"*, *"NA Logistics"*, and *"NAL"*).
- **Alias Lookup Table (`entity_aliases`):** Maps known textual variants to a canonical entity identifier and standardized display name.
- **Unit Normalization:** Converts common multiplier notations (e.g., "in thousands", "$M", "Billion") into canonical scalar values with normalized unit tags, preserving raw source expressions in `raw_text`.
- **Temporal Normalization:** Standardizes dates and reporting periods across diverse fiscal calendar definitions.

---

## 5. Fact Validation & Quality Assurance

1. **Range & Sanity Checks:** Applies configurable bounding checks per metric type to catch OCR transcription errors (e.g., misreading a decimal point or OCR character artifact).
2. **Provenance Audit Trail:** Every fact preserves its source coordinates (`document_id`, `page_number`, `raw_text`), allowing client applications to highlight the exact visual origin of any numeric figure.
3. **Discrepancy Logging:** When multiple documents or document versions report conflicting values for the identical entity, metric, and period, the system preserves both rows with distinct provenance rather than silently overwriting, enabling comparative discrepancy reporting.

---

## 6. PostgreSQL Relational Indexing & Storage

The `ExtractedFact` table is indexed to provide instant sub-millisecond execution for parameterized queries:
- Composite index on `(workspace_id, entity_name, metric_name, period_value)` for fast point lookups.
- Range index on `(workspace_id, period_value)` for temporal trend queries.
- Foreign key indexing on `(document_id, document_version_id)` for lifecycle management and cascade deletions.

---

## 7. Extensibility

New enterprise metrics, custom entity hierarchies, or domain-specific measurement units are configured via database lookup tables or JSON schema descriptors without requiring modifications to the core ingestion and retrieval codebase.
