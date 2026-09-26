# 07 — AI Query Engine (Query Router)

## 1. Purpose

Given a natural-language question plus authorization scope, decide whether to answer via:
1. **Structured query** (PostgreSQL, exact figures).
2. **RAG query** (retrieval + LLM, narrative/explanatory).
3. **Hybrid query** (both, fused into one answer).

## 2. Classification Approach

```
User query
  → Entity/intent extraction (LLM call, constrained JSON output, or rule-based pre-pass)
  → Classification: STRUCTURED | RAG | HYBRID
  → Route accordingly
```

- **Decision:** classification uses a small, constrained LLM call that outputs a strict Pydantic-validated JSON object (`QueryClassification`: `route`, `metrics[]`, `mines[]`, `subsidiaries[]`, `periods[]`, `comparison: bool`, `confidence`), rather than a purely rule-based classifier.
  - **Alternative considered:** pure keyword/regex heuristics (e.g., "if the question contains a number word and a metric word → structured"). **Reason for not choosing purely-rules:** natural-language questions vary too much in phrasing for robust hard-coded coverage; a constrained LLM call is cheap (small prompt, GPT-5 nano class model) and generalizes better.
  - **Guardrail:** the LLM's output is only ever used as *routing metadata and query parameters* — it never becomes SQL text directly (see §4). A rule-based fallback classifier exists for when the LLM call fails/times out (defaults to `HYBRID` — the safest fallback, since hybrid attempts both paths and returns whatever has evidence).

## 3. Examples (from the problem statement, preserved verbatim as design test cases)

| Question | Route |
|---|---|
| "What was coal production in 2023?" | STRUCTURED |
| "Why did production decline in 2023?" | RAG |
| "Compare production decline with the operational reasons mentioned in reports." | HYBRID |

These three examples are part of the golden evaluation set in `17_TESTING_STRATEGY.md`.

## 4. Structured Query Path — Safety Design

**The LLM never generates free-form SQL.** This is a hard security/correctness requirement (see also `16_SECURITY.md` §SQL injection).

Flow:
1. LLM/rule classification produces a validated `QueryClassification` object with typed parameters (metrics, mines, subsidiaries, periods, comparison flag) — not SQL.
2. This object is validated against a strict Pydantic schema (`StructuredQueryPlan`): every field is constrained to known enums/patterns (e.g., `metric` must be one of the known metric enum values or explicitly `unknown`; `period` must parse to a valid year/fiscal-year pattern).
3. The validated plan is mapped to **one of a fixed, pre-written set of parameterized query templates** (Python functions using parameterized queries via the DB driver/ORM — never string concatenation), e.g.:
   - `get_metric_by_mine_and_period(metric, mine, period)`
   - `get_metric_aggregate_by_subsidiary_and_period(metric, subsidiary, period_range)`
   - `compare_metric_across_periods(metric, mine_or_subsidiary, periods[])`
4. If the validated plan does not map cleanly to any known template (e.g., an unsupported combination of filters), the system returns a controlled `NO_EVIDENCE_FOUND`/`UNSUPPORTED_QUERY` response rather than attempting a best-effort dynamic query.
5. Every template query includes the authorization scope filter (`org_id`/`workspace_id`/`allowed_document_ids`) as a mandatory parameter — a template cannot be invoked without it.

> **Decision:** fixed parameterized templates over dynamic query builders or LLM-generated SQL. **Alternative considered:** a constrained "query builder DSL" that assembles WHERE clauses dynamically from validated fields. **Reason for choosing fixed templates for v1:** with a bounded, known set of question shapes in this domain (metric-by-mine-by-period, aggregates, comparisons), a small template set is fully auditable and testable; a dynamic builder is a reasonable v2 evolution once more query shapes are observed in real usage, and is flagged as such in `18_IMPLEMENTATION_ROADMAP.md`.

## 5. RAG Query Path

See `05_RETRIEVAL_AND_RERANKING.md` and `11_CITATION_AND_VALIDATION.md`. Summary: hybrid semantic+keyword retrieval → rerank → context selection → constrained LLM answer generation → claim validation → citation attachment.

## 6. Hybrid Query Path

1. Run the structured path (§4) to obtain exact figures relevant to the detected metrics/periods/entities.
2. Run the RAG path (§5), optionally using the structured results to bias retrieval filters (e.g., restrict to chunks whose page/section overlaps the source of the relevant `ExtractedFact` rows, in addition to normal semantic/keyword candidates).
3. Compose a single LLM answer-generation call whose evidence context contains **both** the structured rows (rendered as a compact evidence table) and the top reranked narrative chunks, each with distinct citation markers (`[F1]` for facts, `[C1]` for chunks).
4. Validation (§`11`) checks numeric claims against `[F#]` facts specifically (exact match required) and narrative claims against `[C#]` chunks (entailment/overlap check).

## 7. Query Request/Response Contract

See `08_API_CONTRACTS.md` (`POST /query`) and `09_DATA_MODELS.md` (`QueryRequest`, `QueryResponse`) for the exact schema. Key fields surfaced to the caller regardless of route: `answer`, `route_used`, `citations[]`, `no_evidence: bool`, `confidence`.

## 8. Failure & Ambiguity Handling

- If classification confidence is low, default to `HYBRID` (broadest evidence gathering) rather than guessing a narrow route and missing evidence.
- If neither path produces qualifying evidence, the response is `no_evidence: true` with `answer` explicitly stating no evidence was found — never a fabricated answer (see `11_CITATION_AND_VALIDATION.md` §1 for the enforcement mechanism).
