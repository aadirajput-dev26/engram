# 04 — Document Processing Specification

## 1. Supported Input Types

| Type | Detection | Primary handling |
|---|---|---|
| Digital PDF (text layer present) | MIME `application/pdf` + text-layer probe (sample first N pages, check extractable character density) | PyMuPDF text/layout extraction |
| Scanned PDF (image-only or low text density) | Same probe, low/no text density | OCR (PaddleOCR) per page image render |
| DOCX | MIME/extension | python-docx (or equivalent) structural parse |
| XLSX | MIME/extension | openpyxl (or equivalent) sheet/table parse |
| CSV | MIME/extension | Direct tabular parse (delimiter sniffing) |
| Images (PNG/JPG/TIFF) | MIME/extension | OCR (PaddleOCR) directly |

A single PDF may be **mixed** (some pages digital, some scanned) — classification and OCR fallback happen **per page**, not per document.

## 2. File Validation

On ingest (`POST /documents/ingest`):
- Enforce max file size (configurable, `MAX_UPLOAD_SIZE_MB`; prototype default suggested: 50 MB direct upload, larger files via pre-signed object-storage upload + ingest-by-reference).
- Enforce allowed MIME/extension allowlist (reject executables, scripts, archives unless explicitly supported).
- Compute and store a content hash (SHA-256) for deduplication and versioning.
- Virus/malware scanning: **Decision:** out of scope for the SIH prototype; **flagged as a production requirement** (e.g., integrate ClamAV or a cloud provider's scanning service before general availability). Documented here as a known gap, not silently omitted.
- Reject files that fail to open/parse at all after N retries; mark job `FAILED` with a structured error reason (not a silent drop).

## 3. Document Classification

Classification determines the processing path:
1. Detect file type from content (not just extension) using magic-byte sniffing.
2. For PDFs: sample pages (e.g., first 5, middle 5, last 5, or all pages for short documents) and measure extractable-text density per page to decide `digital` vs `scanned` **per page**.
3. Store the classification result (and per-page decision for PDFs) as part of `DocumentMetadata`/`Page` records.

## 4. OCR

- **Engine:** PaddleOCR (or an equivalent open-source OCR engine providing comparable accuracy) — chosen because it handles both Latin and mixed script content well and runs without external API dependency, keeping per-page OCR cost at zero marginal API cost.
- OCR runs **page-by-page**, rendering each page to an image at a configurable DPI (default suggested: 200–300 DPI, tunable per document based on size/complexity), never rasterizing the whole document into memory at once.
- OCR output per page: recognized text blocks with bounding boxes and confidence scores.
- **Fallback rule:** if native text extraction on a nominally "digital" page yields text density below a threshold (garbled encoding, embedded-image-only page), fall back to OCR for that page even if the document was classified as digital overall.
- Low-confidence OCR regions are flagged in `Page.ocr_confidence` / stored per block so downstream extraction can weight or exclude low-confidence text and so the UI can surface "low OCR confidence" warnings on generated facts/citations.

## 5. Structure Understanding

Goal: build a hierarchical map of the document (`Document → Section → Subsection → Paragraph/Table`) rather than treating it as a flat text blob.

Approach:
1. Use font-size/style heuristics + PyMuPDF layout metadata (for digital PDFs) or OCR block geometry/heuristics (for scanned PDFs) to detect headings and section boundaries.
2. Build a **PageIndex-style** hierarchical index: a tree keyed by page and heading level, where each node records its page range and character offsets. This tree is what "PageIndex-based structure understanding" refers to in the source problem statement — it is used to (a) drive structure-aware chunking, (b) support navigation for report generation ("find the section covering Mine X 2023 production"), and (c) provide human-readable section labels for citations (e.g., "Section 3.2, Page 14").
3. Detect tables explicitly (via PyMuPDF table-detection utilities for digital PDFs; via layout/row-column heuristics on OCR bounding boxes for scanned pages) and store them as `Table` records distinct from paragraph text, since tables are the primary source of `ExtractedFact` rows.
4. **Decision:** structure understanding is heuristic + rule-based in v1, not a trained ML layout model. **Alternatives considered:** a full document-layout ML model (e.g., LayoutLM-family). **Reason:** heuristic approach is transparent, debuggable, and sufficient for the structured report formats in this domain; an ML layout model is flagged as a future enhancement if heuristics prove insufficient on real archival scans (see `18_IMPLEMENTATION_ROADMAP.md`).

## 6. Metadata Extraction

Document-level metadata extracted post-structure-understanding:
- Title (from first heading / filename fallback).
- Detected document type (e.g., "production report," "geological survey," "parliamentary Q&A response" — a configurable, extensible enum, not hard-coded to a fixed exhaustive list).
- Date(s) mentioned / document date.
- Detected subsidiary/mine name candidates (via the structured-extraction NER pass, see `06`).
- Page count, language(s) detected.

## 7. Structure-Aware Chunking

**Do not** use naive fixed-size (e.g., "every 500 characters") chunking as the sole strategy.

Chunking algorithm:
1. Walk the structure tree leaf-to-root: paragraphs within a subsection are the base unit.
2. Merge adjacent paragraphs within the same subsection up to a target token budget (configurable, default suggested 300–600 tokens) to avoid over-fragmenting short paragraphs, but **never merge across a section boundary**.
3. If a single paragraph/table exceeds the token budget, split it at sentence boundaries (for text) or logical row-groups (for tables), preserving overlap (configurable, default suggested 10–15% overlap) only within the same subsection.
4. Tables are chunked separately from surrounding narrative (a table becomes its own chunk or set of row-group chunks) because tables feed both the `ExtractedFact` extractor and, as fallback context, the RAG index.
5. Every chunk stores: `document_id`, `page_number(s)`, `section_id`, `section_path` (human-readable, e.g. "3 > 3.2"), `chunk_type` (`paragraph`/`table`/`heading_context`), `char_offset_start/end`, and a `content_hash`.

## 8. Chunk Metadata & Deduplication

- `content_hash` (SHA-256 of normalized chunk text) is used to detect exact-duplicate chunks across re-uploaded/duplicate documents.
- On re-ingestion of a byte-identical file (same document-level content hash), the system short-circuits to "already processed" rather than reprocessing (idempotency; see `08_API_CONTRACTS.md`).
- On re-ingestion of a **new version** of a document with overlapping content, duplicate chunks (by `content_hash`) are linked rather than re-embedded, to save embedding cost — **Decision**, with **alternative** being always re-embed for simplicity; re-linking is chosen because embedding cost/time scales with corpus size and archival re-uploads are expected to be common in this domain.

## 9. Document Versioning

- A `Document` has one or more `DocumentVersion` records (v1, v2, ...). Each version has its own processing job and its own chunks/facts.
- Queries default to the latest `READY` version unless a workspace/report explicitly pins a version (needed for point-in-time report reproducibility, e.g., "what did the report say as submitted on date X").
- Re-processing a specific stage (e.g., re-run structured extraction after a schema fix) creates a new processing attempt for the same version, not a new version.

## 10. Large Document Handling

- Files are uploaded to object storage first (directly or via pre-signed URL for large files); the processing job operates on the object-storage reference, never on an in-memory buffer of the whole file.
- PDFs are processed **page-batched**: pages are streamed/rendered in batches (configurable batch size, default suggested 10–20 pages) so peak memory is bounded regardless of total document size.
- Each stage (OCR, structure extraction, chunking, embedding) persists its intermediate output (per page/batch) before proceeding, so a crash/restart resumes from the last completed batch rather than restarting the whole document (see `14_ASYNC_PROCESSING.md`).
- A 267 MB document is handled identically in kind to an 8–10 MB document — it simply has more page-batches and takes proportionally longer; there is no architectural ceiling built into the design (see `23` scalability discussion in `15_DEPLOYMENT_ARCHITECTURE.md`). The SIH demo intentionally uses a smaller representative file for time/infra reasons only.

## 11. Failure Handling

- Each processing stage records success/failure independently (`ProcessingStatus` per stage, see `09_DATA_MODELS.md`).
- A stage failure marks the job `FAILED` (if unrecoverable, e.g., corrupt file) or `PARTIAL` (if some pages/batches succeeded and others didn't).
- Retrying a `FAILED`/`PARTIAL` job re-runs **only the failed stage/batches**, not the entire pipeline — enabled by persisted intermediate results per stage/page-batch.
- Poison-pill protection: a batch that fails repeatedly (configurable max retry count) is marked `FAILED` for that batch specifically, and processing continues for the rest of the document where possible, so one bad page does not block an entire large document.
