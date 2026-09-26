# 09 — Data Models

All models below are specified as Pydantic models (FastAPI request/response and internal domain objects). PostgreSQL vs. Qdrant responsibility is called out per model. Field types are indicative; exact Python typing (e.g., `Decimal` vs `float` for monetary/measurement values — recommend `Decimal` for stored facts to avoid float drift) is an implementation detail to be finalized during Phase 1/Phase 11 (`18_IMPLEMENTATION_ROADMAP.md`).

## 1. `Document` (PostgreSQL — AI schema, mirrors a subset of Express's document record by `document_id` reference)

```python
class Document(BaseModel):
    id: UUID
    org_id: UUID
    workspace_id: UUID
    folder_id: UUID | None
    filename: str
    content_hash: str
    current_version_id: UUID
    created_at: datetime
    updated_at: datetime
```

> Note: `id`/`org_id`/`workspace_id`/`folder_id` values are **provided by Express** at ingest time and treated as foreign references, not independently assigned. FastAPI does not create organizations/workspaces/folders.

## 2. `DocumentVersion`

```python
class DocumentVersion(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    file_ref: str            # object storage key
    declared_mime_type: str
    detected_type: Literal["digital_pdf", "scanned_pdf", "docx", "xlsx", "csv", "image"]
    page_count: int | None
    uploaded_by_user_id: UUID
    created_at: datetime
```

## 3. `DocumentMetadata`

```python
class DocumentMetadata(BaseModel):
    document_version_id: UUID
    title: str | None
    document_type: str            # extensible, not a hard enum
    detected_dates: list[str]
    detected_subsidiary_names: list[str]
    detected_mine_names: list[str]
    language: str | None
```

## 4. `ProcessingJob` / `ProcessingStatus`

```python
class ProcessingStageStatus(BaseModel):
    stage: Literal[
        "UPLOADED", "QUEUED", "PROCESSING", "OCR", "STRUCTURE_EXTRACTION",
        "DATA_EXTRACTION", "CHUNKING", "EMBEDDING", "INDEXING", "READY",
        "FAILED", "PARTIAL",
    ]
    progress_current: int | None
    progress_total: int | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None

class ProcessingJob(BaseModel):
    id: UUID
    document_id: UUID
    document_version_id: UUID
    org_id: UUID
    workspace_id: UUID
    overall_status: str
    stages: list[ProcessingStageStatus]
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
```

See `14_ASYNC_PROCESSING.md` for lifecycle transition rules.

## 5. `Page`

```python
class Page(BaseModel):
    id: UUID
    document_version_id: UUID
    page_number: int
    source_type: Literal["native", "ocr"]
    ocr_confidence: float | None
    raw_text: str
```

## 6. `Section`

```python
class Section(BaseModel):
    id: UUID
    document_version_id: UUID
    parent_section_id: UUID | None
    level: int
    title: str | None
    page_start: int
    page_end: int
    section_path: str          # e.g. "3 > 3.2"
```

## 7. `Table`

```python
class Table(BaseModel):
    id: UUID
    document_version_id: UUID
    page_number: int
    section_id: UUID | None
    row_count: int
    col_count: int
    header_row: list[str] | None
    raw_cells: list[list[str]]
```

## 8. `Chunk` (metadata in PostgreSQL; vector in Qdrant, keyed by the same `id`)

```python
class Chunk(BaseModel):
    id: UUID
    document_id: UUID
    document_version_id: UUID
    org_id: UUID
    workspace_id: UUID
    page_start: int
    page_end: int
    section_id: UUID | None
    section_path: str | None
    chunk_type: Literal["paragraph", "table", "heading_context"]
    text: str
    content_hash: str
    char_offset_start: int
    char_offset_end: int
    embedding_model: str
    created_at: datetime
```

## 9. `ExtractedFact`

See full field description in `06_STRUCTURED_DATA_EXTRACTION.md` §2.

```python
class ExtractedFact(BaseModel):
    id: UUID
    document_id: UUID
    document_version_id: UUID
    page_number: int
    section_path: str | None
    table_id: UUID | None
    metric: str
    metric_raw_label: str | None
    value: Decimal
    unit: str
    unit_normalized: str | None
    mine_name: str | None
    subsidiary_name: str | None
    coal_grade: str | None
    period_type: Literal["year", "fiscal_year", "quarter", "month", "date_range"]
    period_value: str
    confidence: float
    extraction_method: Literal["table_parser", "regex", "llm_assisted"]
    raw_text: str
    validation_flag: str | None
    created_at: datetime
```

## 10. `RetrievalResult`

```python
class RetrievalResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_name: str
    page_start: int
    page_end: int
    section_path: str | None
    snippet: str
    semantic_score: float | None
    keyword_score: float | None
    fused_score: float | None
    rerank_score: float | None
```

## 11. `Citation`

```python
class Citation(BaseModel):
    citation_id: str          # e.g. "C1" or "F1"
    source_type: Literal["chunk", "fact"]
    document_id: UUID
    document_name: str
    page_number: int | None
    section_path: str | None
    chunk_id: UUID | None
    fact_id: UUID | None
```

## 12. `QueryRequest` / `QueryResponse`

See `08_API_CONTRACTS.md` §4 for full field list; core response shape:

```python
class QueryResponse(BaseModel):
    answer: str
    route_used: Literal["structured", "rag", "hybrid"]
    no_evidence: bool
    citations: list[Citation]
    structured_evidence: list[ExtractedFact]
    confidence: float
    latency_ms: int
```

## 13. `ReportRequest` / Report Generation Models

```python
class ReportGenerateRequest(BaseModel):
    org_id: UUID
    workspace_id: UUID
    report_type: str                 # extensible enum
    parameters: dict                 # shape depends on report_type; validated per-type sub-schema
    output_format: Literal["docx", "pdf"]
    requested_by_user_id: UUID

class ReportSection(BaseModel):
    heading: str
    content: str
    citations: list[Citation]

class ReportDraft(BaseModel):
    id: UUID
    job_id: UUID
    sections: list[ReportSection]
    file_ref: str | None             # populated once rendered to DOCX/PDF
    status: Literal["DRAFTING", "VALIDATING", "READY", "FAILED"]
```

## 14. `TopicResult`

```python
class TopicKeyword(BaseModel):
    term: str
    score: float

class Topic(BaseModel):
    topic_id: str
    label: str
    top_terms: list[str]
    representative_document_ids: list[UUID]

class TopicResult(BaseModel):
    job_id: UUID
    keywords: list[TopicKeyword]
    topics: list[Topic]
    word_cloud_data: list[TopicKeyword]
    entities: list[dict]     # {text, label, count}
```

## 15. PostgreSQL vs. Qdrant Responsibility (summary)

| Model | Store |
|---|---|
| Document, DocumentVersion, DocumentMetadata, ProcessingJob, Page, Section, Table, ExtractedFact, Citation records, ReportDraft, TopicResult | PostgreSQL (AI schema) |
| Chunk **text + metadata** | PostgreSQL (AI schema) — also feeds the FTS `tsvector` column |
| Chunk **embedding vector** | Qdrant, payload includes the filterable fields listed in `05_RETRIEVAL_AND_RERANKING.md` §3 |

All UUIDs referencing `org_id`/`workspace_id`/`user_id` are foreign references to Express-owned entities; FastAPI does not define or migrate those tables.
