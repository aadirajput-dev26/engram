# 12 — Automated Report Generation

## 1. Engine Purpose

The Automated Report Generation engine compiles multi-section analytical documents (such as executive briefings, quarterly operational reviews, risk assessments, and compliance audits) synthesized directly from ingested enterprise documents, guaranteeing verifiable citations for every factual statement.

---

## 2. Extensible Report Templates

The microservice supports both pre-configured templates and custom dynamic outlines:

| Report Template | Description | Primary Data Sources |
|---|---|---|
| `executive_summary` | High-level synthesis of strategic KPIs, organizational highlights, and emerging operational risks. | Hybrid: structured KPI totals + narrative executive statements. |
| `operational_review` | Deep-dive evaluation of departmental performance, output metrics, and variance analysis across periods. | Structured facts for target vs. actual figures + narrative post-mortems. |
| `compliance_audit_summary` | Evaluation of corporate disclosures against regulatory standards and internal policy benchmarks. | Unstructured RAG retrieval over audit logs, policies, and contracts. |
| `custom_outline` | Client application provides an arbitrary list of section headings and target prompt directives. | Dynamically resolved via the section-by-section query pipeline. |

---

## 3. Section-by-Section Synthesis Pipeline

To prevent hallucination and maintain strict context budgets, reports are compiled modularly:

```
Report Generation Request (Template / Custom Outline + Tenant Scope)
  │
  ▼
[Outline & Section Decomposition]
  ├── Breaks report into ordered section tasks: [Section 1, Section 2, ... Section N]
  │
  ▼
[Section-by-Section Evidence Retrieval Loop]
  ├── For each section:
  │     ├── Formulate targeted sub-queries
  │     ├── Retrieve relevant structured facts (PostgreSQL) and narrative chunks (Qdrant/FTS)
  │     ├── Execute grounded LLM drafting with strict citation markers
  │     ├── Run programmatic validation (check numeric fidelity and chunk entailment)
  │     └── If evidence is missing → Emit explicit section disclaimer placeholder
  │
  ▼
[Consolidated Assembly & Rendering]
  ├── Order sections and format document layout
  ├── Compile master citation bibliography (Document, Page, Section references)
  ├── Render output artifact (DOCX / PDF)
  └── Store rendered artifact in Object Storage & update Job Status to `READY`
```

---

## 4. Grounded Synthesis & Hallucination Prevention

1. **No Unbounded Generation:** The LLM is never tasked with generating an entire multi-page document from parametric memory. Each section prompt contains strictly the retrieved context relevant to that topic.
2. **Mandatory Citations:** Every assertion in a generated section must reference a valid citation marker.
3. **Missing Evidence Transparency:** If no qualifying evidence exists for a requested section, the engine renders an explicit callout:
   > *"No supporting evidence was found in the workspace repository for this section."*
   The system never fabricates placeholder narratives.

---

## 5. Structured & Narrative Data Fusion

Report sections routinely require both exact numbers and explanatory narratives:
- Example: An *"Operating Performance"* section synthesizes exact revenue/expense rows retrieved from the `ExtractedFact` table, alongside explanatory paragraphs retrieved via hybrid search explaining why cost variances occurred.
- The report generation engine directly leverages the `HYBRID` query execution path defined in `07_AI_QUERY_ENGINE.md`.

---

## 6. Document Compilation & Output Formats

- **Microsoft Word (DOCX):** Rendered using standard document templates (`python-docx`) with styled typographic hierarchies, tables, headers, footers, and footnote citations.
- **PDF Export:** Generated via document conversion utilities or direct PDF template renderers.
- **Master Provenance Trail:** Each generated report payload includes complete machine-readable provenance metadata, allowing consuming client applications to view the exact citation trail alongside the rendered file.

---

## 7. Asynchronous Task Lifecycle

Because compiling multi-section reports involves multiple retrieval, synthesis, and validation iterations:
- Client applications initiate report requests via `POST /api/v1/reports/generate`, which returns an immediate HTTP `202 Accepted` with a `job_id`.
- The task executes in the background worker queue.
- Progress and final downloadable artifacts are polled via `GET /api/v1/reports/{job_id}`.
