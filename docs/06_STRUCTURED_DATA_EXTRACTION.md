# 06 — Structured Data Extraction

## 1. Purpose

Extract discrete, typed, queryable facts from documents (primarily from tables, but also from narrative sentences that state a figure) into PostgreSQL, so that exact-figure questions can be answered by SQL rather than by retrieval-and-hope.

## 2. Target Fact Schema (domain-specific layer)

`ExtractedFact` (see `09_DATA_MODELS.md` for the full Pydantic/DB model):

| Field | Description |
|---|---|
| `id` | Fact ID |
| `document_id`, `document_version_id` | Provenance |
| `page_number` | Provenance |
| `section_path` | Provenance (human-readable) |
| `table_id` (nullable) | If sourced from a detected table |
| `metric` | Enum/string: `production`, `target`, `achievement`, `dispatch`, `reserves`, `grade_quantity`, etc. — **extensible enum**, not exhaustively hard-coded; unrecognized metrics are stored with `metric_raw_label` for later taxonomy expansion rather than dropped. |
| `value` | Numeric value |
| `unit` | e.g., `MT` (million tonnes), `tonnes`, `%`, `INR` — normalized where possible, raw unit preserved alongside |
| `mine_name` (nullable) | Extracted mine/project name |
| `subsidiary_name` (nullable) | Extracted subsidiary/organization name mentioned *in the document content* (distinct from the platform's tenant `org_id` — a document can discuss a subsidiary without that subsidiary being a platform tenant) |
| `coal_grade` (nullable) | e.g., grade classification if applicable |
| `period_type` | `year`, `fiscal_year`, `quarter`, `month`, `date_range` |
| `period_value` | Normalized period (e.g., `2023`, `FY2023-24`) |
| `confidence` | Extraction confidence score (0–1), factoring in OCR confidence of the source region |
| `extraction_method` | `table_parser`, `regex`, `llm_assisted` |
| `raw_text` | The original text/cell content the fact was derived from (for audit) |
| `created_at`, `document_version_id` | Audit fields |

## 3. Extraction Methods (in priority order)

1. **Table parser (highest confidence):** For detected `Table` regions (see `04_DOCUMENT_PROCESSING_SPEC.md` §5), apply header-detection heuristics to identify metric/period/mine columns and value cells, then emit one `ExtractedFact` per relevant cell. This is the primary extraction path since production/target/achievement data in this domain is predominantly tabular.
2. **Regex/pattern extraction (medium confidence):** For narrative sentences matching known numeric-statement patterns (e.g., `"<mine> produced <number> <unit> in <year>"`), apply curated regex/pattern rules tuned to domain phrasing. Lower confidence than table extraction; flagged accordingly.
3. **LLM-assisted extraction (lowest-confidence tier, used selectively):** For ambiguous table structures (merged cells, multi-row headers) or narrative statements regex cannot confidently parse, an LLM call is used to propose structured facts from a given text/table span, constrained to return a strict Pydantic-validated JSON schema. LLM-proposed facts are marked `extraction_method="llm_assisted"` and carry a lower default confidence, and are eligible for human review workflows (future enhancement; not required for the prototype but the confidence/audit fields exist from day one so this is additive, not a schema break later).

> **Decision:** table parsing and regex are attempted first; LLM-assisted extraction is a fallback, not the default path. **Reason:** deterministic parsers are cheaper, faster, auditable, and avoid LLM hallucination risk for numbers that will end up in parliamentary-grade reports; LLM assistance is reserved for genuinely ambiguous structures.

## 4. Normalization

- Units are normalized to a canonical form per metric where a clear conversion exists (e.g., tonnes → MT), while the original unit/value is preserved in `raw_text` for audit.
- Mine/subsidiary name normalization: a lightweight lookup/alias table (`entity_alias`) maps known name variants (e.g., "NCL" ↔ "Northern Coalfields Limited") to a canonical display name, without hard-coding this list into application logic — it is data, editable without a code change. Unmatched names are stored as-is (not dropped), flagged as `normalized=false`.
- Period normalization distinguishes calendar year vs. Indian fiscal year (April–March), since mining/production reporting in India commonly uses fiscal year — this must be explicit in `period_type` and never silently assumed.

## 5. Validation & Consistency Checks

- Range sanity checks per metric (configurable bounds) to flag likely OCR/extraction errors (e.g., a "production" value with an implausible number of digits) — flagged, not silently discarded; stored with `confidence` reduced and a `validation_flag` for reviewer/UI surfacing.
- Cross-check: if the same (mine, metric, period) fact appears with conflicting values across extraction methods or document versions, both are retained (not overwritten) with provenance, and retrieval/query surfaces the conflict rather than silently picking one (important for traceability/audit in a government-reporting context).

## 6. Storage

- All `ExtractedFact` rows live in the AI service's PostgreSQL schema (see `02_SYSTEM_ARCHITECTURE.md` §5), indexed on `(mine_name, subsidiary_name, metric, period_value)` and on `document_id` for provenance lookups.
- This is the table the structured query path (`07_AI_QUERY_ENGINE.md`) executes parameterized queries against.

## 7. Extensibility

New metrics, entity types, or domain fields are added by extending the `metric` enum/lookup and the alias tables — not by modifying the ingestion/chunking/retrieval core. This preserves the reusable-core / domain-specific-layer boundary described in `02_SYSTEM_ARCHITECTURE.md` §7.
