# 04 — Document Processing Specification

## 1. Supported Input Media & Format Detection

The ingestion pipeline handles heterogeneous enterprise document formats with automatic format detection:

| Media Type | Detection Mechanism | Ingestion & Extraction Engine |
|---|---|---|
| **Digital PDF (Text Layer)** | MIME `application/pdf` + text density verification across sample pages | PyMuPDF (`fitz`) / `pdfplumber` layout & text extraction |
| **Scanned / Image PDF** | MIME `application/pdf` + low/empty extractable character count | Optical Character Recognition (PaddleOCR / Tesseract) per page raster |
| **Microsoft Word (DOCX)** | MIME `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | `python-docx` structural parsing (preserving headings, tables, bullets) |
| **Spreadsheets (XLSX)** | MIME `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `openpyxl` sheet, header, and cell-matrix extraction |
| **Delimited Data (CSV)** | MIME `text/csv` / `text/plain` + delimiter sniffing (comma, tab, semicolon) | Direct tabular parsing into normalized rows |
| **Images (PNG, JPG, TIFF, WebP)** | MIME `image/*` + magic-byte header inspection | OCR processing with bounding box geometry extraction |

> **Mixed-Mode PDF Handling:** Multi-page PDF documents frequently combine digitally generated pages with scanned exhibits, affidavits, or invoices. The pipeline executes classification and OCR fallback on a **per-page basis** rather than assuming uniform document type.

---

## 2. Ingestion Validation & Security Boundaries

When a file is submitted via the ingestion API (`POST /documents/ingest`):
1. **Size Limits:** Enforces a configurable upload ceiling (`MAX_UPLOAD_SIZE_MB`, default: 100 MB for direct multipart uploads; larger files use pre-signed object storage URLs).
2. **Magic-Byte Sniffing:** Verifies file signatures against a strict allowlist to prevent executable or malicious file spoofing.
3. **Cryptographic Content Hashing:** Computes a SHA-256 digest of raw file bytes for deduplication, idempotent ingestion, and audit versioning.
4. **Resilience & Graceful Failure:** Files that fail parsing or exhibit severe corruption trigger a structured job failure (`FAILED`) with exact diagnostic error codes, preventing silent data drops.

---

## 3. Optical Character Recognition (OCR) Engine

For scanned pages, image attachments, or digital pages with corrupted text encodings:
- **Engine Architecture:** Employs an offline, high-accuracy OCR engine (PaddleOCR or Tesseract) running in isolated worker processes, eliminating third-party API dependencies and recurring per-page API costs.
- **Page-by-Page Streaming:** Pages are rendered to high-resolution raster images (configurable 200–300 DPI) sequentially in memory, processed, and immediately garbage-collected to prevent memory bloat.
- **Bounding Boxes & Confidence Scores:** The OCR engine yields recognized text tokens, spatial bounding coordinates, and confidence scores per bounding box.
- **Confidence Tracking:** When average OCR confidence falls below a configured threshold (e.g., `< 0.70`), the page is flagged (`Page.ocr_confidence`), allowing downstream modules to warn consumers about potentially noisy text spans.

---

## 4. Hierarchical Structure Understanding (PageIndex Model)

To support accurate retrieval and synthesis, documents must not be treated as flat text streams. The pipeline builds a hierarchical semantic tree: `Document → Sections → Subsections → Paragraphs / Tables`.

### 4.1 Structural Parsing Workflow
1. **Layout & Typographic Heuristics:** Evaluates font sizes, font weights, line spacing, and bounding box alignments (or OCR block geometry) to infer document hierarchy (H1, H2, H3 headers).
2. **PageIndex Tree Construction:** Generates an indexed navigation tree mapping each section and subsection node to exact page spans and character offsets. This tree provides:
   - Boundary enforcement for semantic chunking (preventing chunks from spilling across unrelated chapters).
   - High-level navigation for automated multi-section report drafting.
   - Human-readable structural paths for citations (e.g., *"Section 4.1 > Fiscal Highlights, Page 18"*).
3. **Table Region Extraction:** Detects tabular structures explicitly. Rather than mangling tables into raw unstructured text, table boundaries are parsed into structured column headers and data rows, feeding the Structured Extraction Track.

---

## 5. Document-Level Metadata Extraction

Following structure parsing, a metadata extraction pass identifies key document-level attributes:
- **Title & Subtitle:** Inferred from H1 headers, title metadata, or clean filename fallback.
- **Document Classification:** Classified into categories (e.g., *Financial Statement, Technical Specification, Operational Report, Compliance Audit, Contract*) via heuristic or classifier matching.
- **Publication & Effective Dates:** Inferred from front-matter date patterns.
- **Page Count & Language Profile:** Extracted page statistics and detected primary language(s).

---

## 6. Structure-Aware Chunking Strategy

Naive fixed-length sliding-window chunking (e.g., cutting text every 500 characters) corrupts sentence structures, splits tables mid-row, and separates headings from their context. This pipeline employs **Structure-Aware Semantic Chunking**:

1. **Section Boundary Confinement:** Paragraphs and blocks are grouped strictly within their parent subsection. Chunks are never merged across section boundaries.
2. **Token Budget Target:** Paragraphs within a subsection are aggregated up to a target token window (configurable, default: 350–600 tokens).
3. **Sentence-Boundary Preservation:** If an individual paragraph exceeds the token budget, it is split exclusively along natural sentence boundaries with a configurable token overlap (10–15%).
4. **Isolated Table Chunking:** Tables are parsed into standalone table chunks or row-group chunks with preserved column headers, preventing tabular data from bleeding into narrative paragraphs.
5. **Enriched Chunk Metadata:** Every stored chunk maintains relational links:
   - `document_id`: Target document reference.
   - `page_number`: Source page or page range.
   - `section_id`: Associated section in the PageIndex tree.
   - `section_path`: Full hierarchical path (e.g., `"Executive Summary > Q4 Operational Review"`).
   - `chunk_type`: Categorization (`paragraph`, `table`, `list_item`).
   - `content_hash`: SHA-256 hash of normalized chunk text.

---

## 7. Deduplication & Idempotency

- **Document-Level Deduplication:** If an ingested file shares an identical SHA-256 digest with an existing document in the same workspace, the ingestion endpoint immediately returns the existing document record, preventing redundant processing.
- **Chunk-Level Deduplication:** On document revisions where portions of text remain identical, unchanged chunks (identified by `content_hash`) can reuse existing embeddings, significantly reducing computational overhead and embedding costs.

---

## 8. Document Versioning Model

- Each logical document can maintain multiple versions (`DocumentVersion: v1, v2, ...`), each with distinct processing logs, extracted facts, and vector embeddings.
- By default, search and query operations target the latest `READY` version.
- Consuming applications can pin queries to specific historical versions for audit compliance, historical comparisons, and reproducible analytics.

---

## 9. Scalable Processing of Large Documents

Enterprise files often exceed hundreds of pages and hundreds of megabytes. The pipeline architecture guarantees bounded resource utilization:

- **Object Storage Primacy:** Large files are streamed directly into S3-compatible object storage; worker processes stream byte ranges or page batches rather than buffering entire files in memory.
- **Page-Batched Execution:** PDF parsing and OCR run in discrete page batches (default: 10–20 pages per batch). Intermediate text and layout representations are flushed to storage at the end of each batch.
- **Resumable Checkpoints:** Each processing phase records persistent stage status in PostgreSQL. If a worker terminates unexpectedly, processing resumes from the last completed page batch rather than restarting from page one.
- **Poison-Pill Isolation:** If a specific corrupted page repeatedly causes parsing exceptions, that single page is marked `FAILED` with an error annotation, while processing continues uninterrupted for the remainder of the document.
