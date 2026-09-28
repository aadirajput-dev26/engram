# 03 — RAG Pipeline Specification

## 1. Architectural Philosophy: The Dual-Track RAG Pipeline

Standard naive RAG architectures—relying solely on extracting raw text chunks, embedding them into a vector database, and passing top-$k$ semantic matches to an LLM—fail in mission-critical enterprise environments. Enterprise documents (such as financial filings, operational logs, technical specifications, compliance audits, and contracts) contain dense quantitative metrics, key performance indicators (KPIs), multi-column tables, and exact dates intermixed with explanatory narrative prose.

A naive semantic vector-search pipeline exhibits fundamental limitations when handling such data:
- **Exact Numeric & Entity Retrieval Failure:** Semantic similarity measures conceptual proximity, not factual precision. Vector search frequently retrieves a semantically similar chunk describing a neighboring quarter, department, or related entity instead of the exact figure requested.
- **Inability to Compute Aggregations:** Questions requiring arithmetic computation or comparative analysis (e.g., *"What was the total operating expense across all business units in Q3 2024?"*) require aggregate calculation over structured data rather than semantic text retrieval.
- **Lack of Numeric Fidelity:** Standard LLM generation from narrative context lacks strict transactional guarantees for numeric accuracy, posing unacceptable hallucination risks.

To solve this, this RAG Pipeline microservice implements a **Dual-Track Ingestion and Query Architecture**:
1. **Structured Extraction Track:** Identifies tabular and discrete quantitative entities, validates their types, and persists normalized structured facts into PostgreSQL for exact SQL querying.
2. **Unstructured Narrative Track:** Performs structure-aware chunking preserving hierarchy and context, indexes chunks into Qdrant for dense semantic vector retrieval, and indexes terms into PostgreSQL for lexical Full-Text Search (FTS).
3. **Hybrid Query Engine:** Dynamically routes queries to structured SQL, hybrid semantic/lexical retrieval, or a unified fusion path that synthesizes both structured metrics and narrative context with verifiable citations.

---

## 2. End-to-End Pipeline Architecture

```
=== INGESTION & PROCESSING LIFECYCLE ===

Raw Document (PDF / DOCX / XLSX / CSV / Image)
  │
  ▼
[Stage 1: Ingestion & Validation]
  ├── Detect MIME type, file size, and magic bytes
  └── Store original artifact in Object Storage
  │
  ▼
[Stage 2: Document Classification & Layout Analysis]
  ├── Classify format (Digital PDF / Scanned PDF / Office Doc / Spreadsheet / Image)
  ├── OCR Processing (Tesseract / Vision Model for scanned media)
  └── Native Extraction (PyMuPDF / pdfplumber for digital documents)
  │
  ▼
[Stage 3: Hierarchical Structure Understanding]
  ├── Document Tree Construction (Document → Pages → Sections → Subsections)
  ├── Table & Bounding Box Detection
  └── Document-level Metadata Extraction (Title, Author, Dates, Entity hints)
  │
  ├────────────────────────────────────────┬────────────────────────────────────────┐
  │                                        │                                        │
  ▼                                        ▼                                        ▼
[Track A: Structured Extraction]       [Track B: Unstructured Chunking]       [Document Catalog]
  │                                        │                                        │
  ├── Table & Entity Parsing              ├── Hierarchy-Preserving Chunking        └── Status Update:
  ├── Fact Validation & Normalization      ├── Chunk Metadata Binding                     `READY`
  └── PostgreSQL Storage:                  ├── Vector Embeddings → Qdrant
      `ExtractedFact` tables               └── Full-Text Indexing → Postgres FTS


=== QUERY & INFERENCE LIFECYCLE ===

Client Application Request (Query + Context Scope + X-Api-Key)
  │
  ▼
[Stage 4: Query Understanding & Routing]
  ├── Scope Validation (Workspace / Organization isolation via API Key)
  ├── Intent Classification:
  │     ├── `STRUCTURED`: Tabular / aggregation / metric lookup
  │     ├── `UNSTRUCTURED`: Qualitative / narrative / conceptual query
  │     └── `HYBRID`: Requires both exact metrics and narrative context
  │
  ├────────────────────────────────────────┬────────────────────────────────────────┐
  │                                        │                                        │
  ▼ (if Structured / Hybrid)               ▼ (if Unstructured / Hybrid)             │
[Path A: Structured Query Engine]       [Path B: Hybrid Retrieval Engine]            │
  │                                        │                                        │
  ├── Parameter & Filter Extraction        ├── Dense Vector Search (Qdrant)         │
  ├── Parameterized SQL Generation         ├── Lexical Keyword Search (Postgres FTS)│
  └── Deterministic Execution (Postgres)   ├── Reciprocal Rank Fusion (RRF)         │
                                           └── Cross-Encoder Reranking              │
                                                   │                                │
                                                   ▼                                │
                                           Top-K Context Selection                  │
                                                   │                                │
  └────────────────────────────────────────┬───────┴────────────────────────────────┘
                                           │
                                           ▼
[Stage 5: Synthesis, Grounding & Verification]
  ├── LLM Answer Generation (Prompt constrained strictly to retrieved facts/chunks)
  ├── Claim-to-Evidence Verification (Every assertion mapped to citation ID)
  ├── Hallucination Fallback (Return `NO_EVIDENCE_FOUND` if ungrounded)
  └── Formatted Response with Provenance Citations (Document, Page, Chunk/Row)
```

---

## 3. Pipeline Stages & Component Responsibilities

| Stage | Input | Primary Output | Specification Reference |
|---|---|---|---|
| **Ingestion & Validation** | Raw bytes or object storage reference | Validated file descriptor, verified MIME type | `04_DOCUMENT_PROCESSING_SPEC.md` |
| **Classification & Extraction** | Validated file artifact | Raw text stream, page layouts, coordinates | `04_DOCUMENT_PROCESSING_SPEC.md` |
| **Structure Understanding** | Layout tree + text | Hierarchical document tree, section boundaries, tables | `04_DOCUMENT_PROCESSING_SPEC.md` |
| **Metadata Extraction** | Document structure tree | Document metadata (Title, dates, tags, detected entities) | `04_DOCUMENT_PROCESSING_SPEC.md` |
| **Structured Fact Extraction** | Tables, key-value pairs, layout text | Normalized `ExtractedFact` records in PostgreSQL | `06_STRUCTURED_DATA_EXTRACTION.md` |
| **Structure-Aware Chunking** | Narrative sections, document hierarchy | Semantic `Chunk` records with breadcrumbs | `04_DOCUMENT_PROCESSING_SPEC.md` |
| **Embedding & Indexing** | Chunks | Dense vector index (Qdrant) + Lexical index (Postgres FTS) | `05_RETRIEVAL_AND_RERANKING.md` |
| **Query Classification & Routing** | User query + Tenant scope | Query execution plan (`STRUCTURED`, `RAG`, `HYBRID`) | `07_AI_QUERY_ENGINE.md` |
| **Hybrid Retrieval & Reranking** | Query plan + search vectors | Top-$k$ high-relevance evidence chunks | `05_RETRIEVAL_AND_RERANKING.md` |
| **Synthesis & Verification** | Evidence set + User query | Factual draft answer linked to citation IDs | `07_AI_QUERY_ENGINE.md`, `11_CITATION_AND_VALIDATION.md` |
| **Citation Attachment** | Verified answer + evidence payload | Final response payload with exact page/line references | `11_CITATION_AND_VALIDATION.md` |

---

## 4. Dual-Track Partitioning: Structured vs. Unstructured

During ingestion, the pipeline applies deterministic heuristics and model-assisted classification to determine how information spans are routed:

### 4.1 Structured Information Criteria
A document region is routed to the **Structured Extraction Track** if it represents discrete, tabular, or typed data:
- Tables with clear column headers and row entities.
- Financial or operational metrics: `(entity, metric_name, value, unit, time_period, source_location)`.
- Key-Value pairs with explicit labels (e.g., `"Operating Revenue: $42.5M"`, `"Audit Date: 2024-03-31"`).
- Structured tabular data is extracted, normalized, validated for data types, and stored in relational tables.

### 4.2 Unstructured / Narrative Information Criteria
A document region is routed to the **Unstructured Chunking Track** if it represents contextual, descriptive, or discursive prose:
- Paragraphs explaining operational trends, risks, policies, or market conditions.
- Section overviews, introductions, and conclusions.
- Footnotes, qualitative assessments, and commentary.

### 4.3 Cross-Track Linking
The same document page frequently produces both structured facts and narrative chunks (e.g., a financial balance sheet followed by explanatory footnotes). To preserve relational context:
- Every `ExtractedFact` and `Chunk` records its exact provenance: `document_id`, `page_number`, and `section_id`.
- The Query Engine can perform cross-track joins: retrieving an exact structured metric and immediately augmenting it with narrative chunks from the same page or section to explain *why* that metric changed.

---

## 5. Grounded Generation & Hallucination Prevention

A core requirement of this enterprise RAG microservice is absolute evidentiary grounding. The system adheres to strict validation principles:

1. **No Parametric Memory Recall:** The LLM is strictly instructed to act as a grounded synthesizer, drawing conclusions solely from the context payload provided in the prompt.
2. **Sentinel Fallbacks:** If the retrieved evidence does not contain sufficient facts to answer the question, the system is programmed to return an explicit sentinel response (`NO_EVIDENCE_FOUND`) rather than generating speculative text.
3. **Strict Citation Binding:** Every factual claim, number, or assertion in the generated response must reference one or more active citation IDs included in the evidence payload.
4. **Post-Generation Fact Verification:** Before returning a response to the client application, an automated validation module verifies that all numerical quantities in the answer appear verbatim in the referenced source chunks or structured records. Any ungrounded assertion causes the claim to be flagged or downgraded.

---

## 6. Microservice Reusability & Extensibility Boundaries

The architecture is partitioned into a generic infrastructure core and a configurable domain layer:

- **Universal Engine Core (Domain-Agnostic):**
  - File ingestion, MIME validation, and object storage management.
  - OCR pipelines, text layout analysis, and hierarchical structure parsing.
  - Chunking algorithms, dense vector embedding orchestration, and Qdrant indexing.
  - Hybrid retrieval fusion (RRF), cross-encoder reranking, and search filtering.
  - Multi-tenant data isolation, API key resolution, and async worker execution.
  - Citation attachment and claim-to-evidence validation frameworks.

- **Configurable Domain Adapters:**
  - Structured extraction schemas (defining target metrics and entities for specific industries).
  - Domain-specific report templates (defining required sections and validation constraints).
  - Specialized topic-modeling stopword lists and entity dictionaries.

This separation ensures the RAG Pipeline microservice functions as a turnkey, general-purpose enterprise infrastructure component that can be integrated into any client application.
