# 11 — Citation, Provenance and Fact Validation

## 1. Core Operating Principle: Strict Grounding Over Hallucination

> **Zero-Hallucination Policy:** The microservice strictly favors returning `"NO_EVIDENCE_FOUND"` over generating ungrounded, speculative, or hallucinated responses.

In enterprise and compliance-heavy operational environments, an inaccurate or hallucinated answer is substantially more damaging than an explicit declaration that the requested evidence is missing from the corpus. Grounding is enforced structurally at the pipeline level, rather than relying solely on soft prompt instructions.

---

## 2. End-to-End Verification Pipeline

```
Retrieved Evidence Set
  ├── Structured Facts: [F1], [F2], ... (Exact DB records)
  └── Narrative Chunks: [C1], [C2], ... (Reranked passages)
  │
  ▼
[Constrained Synthesis Engine]
  ├── Prompts instruct LLM to synthesize answer citing ONLY provided [F#]/[C#] tags
  └── Returns candidate answer with embedded citation markers
  │
  ▼
[Post-Generation Claim Verification Pass]
  ├── 1. Claim Extraction: Decomposes answer into discrete factual propositions
  │
  ├── 2. Deterministic Numeric Verification:
  │     ├── Regex extracts numbers, currency values, percentages, and dates
  │     └── Verifies exact equivalence against values in cited [F#] records
  │
  ├── 3. Narrative Entailment Verification:
  │     └── Evaluates lexical and semantic entailment against cited [C#] chunks
  │
  ├────────────────────────────────────────┬────────────────────────────────────────┐
  │ All claims verified                    │ One or more claims ungrounded          │
  ▼                                        ▼                                        ▼
[Final Response Construction]            [Ungrounded Claim Stripped]      [Sentinel Fallback]
  ├── Verified answer text                 ├── Factual assertions that     └── If no claims pass,
  ├── Stamped Citation objects                 lack proof are dropped          return explicit
  └── Provenance metadata                  └── Remaining text preserved        `NO_EVIDENCE_FOUND`
```

---

## 3. Strict Prompt Construction & Guardrails

The LLM generation prompts are constructed with explicit boundaries:
1. **Isolated Context Boundary:** Evidence blocks are enclosed within clear, immutable XML tags (e.g., `<evidence id="C1">...</evidence>`).
2. **Untrusted Data Isolation:** The system prompt explicitly informs the model that text within evidence blocks must be treated purely as inert reference material, mitigating prompt injection risks from ingested documents.
3. **Mandatory Marker Attribution:** Every statement asserting a figure, metric, or factual occurrence must conclude with its corresponding marker (e.g., `...generated $45.2M in recurring revenue [F1].`).
4. **Explicit Fallback Directive:** If the provided evidence cannot conclusively answer the query, the model is directed to emit the sentinel `NO_EVIDENCE_FOUND`.

---

## 4. Programmatic Numeric Consistency Verification

Because numerical errors in business analytics carry significant consequences:
- **Direct Fact Reconciliation:** Whenever an answer references a structured fact (`[F#]`), the verification module re-extracts the numeric quantity from the generated sentence and compares it against the underlying `ExtractedFact.value`.
- **Formatting Tolerances:** Tolerates standard formatting variations (e.g., `$1,200,000` vs `$1.2M`) while rejecting arithmetic distortions, swapped digits, or misplaced decimals.
- **Template Rendering Preference:** Where feasible, structured metrics are directly rendered from database records rather than relying on LLM transcription, eliminating transcription errors at the source.

---

## 5. Rich Citation Payload for Client Applications

Every generated answer returns a structured `citations` array. Consuming client applications can render these directly as interactive citations, hover popovers, or deep-links into the original document:

```json
{
  "citation_id": "C1",
  "source_type": "chunk",
  "document_id": "8a3e7b12-9c44-42f1-bb20-5c1a7d6e4f3a",
  "document_title": "Q3 2024 Operational Audit",
  "page_number": 27,
  "section_path": "Audit Findings > Logistics > Fleet Utilization",
  "excerpt": "Fleet utilization across the central corridor averaged 78.4% during Q3..."
}
```

---

## 6. "No Evidence Found" Response Specification

When evidence is insufficient to answer the query:
- `QueryResponse.no_evidence`: Set to `true`.
- `QueryResponse.answer`: A clear, non-hallucinatory message (e.g., *"No supporting evidence was found in the accessible documents for this query."*).
- `QueryResponse.citations`: Empty array (`[]`).
- `QueryResponse.confidence`: Set to `0.0`.
