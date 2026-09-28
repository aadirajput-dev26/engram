# 09 — Data Models (RAG Pipeline Microservice)

This document specifies the primary domain models and database schemas powering the RAG Pipeline microservice. Relational entities are persisted in PostgreSQL via SQLAlchemy ORM / Pydantic schemas, while vector representations are maintained in Qdrant.

---

## 1. Multi-Tenant Identity & Access Models

The microservice manages its own hierarchical multi-tenant structure to isolate document indices, extracted facts, and vector payloads.

```python
class Organization(BaseModel):
    id: UUID
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime

class Workspace(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime

class ApiKey(BaseModel):
    id: UUID
    org_id: UUID
    workspace_id: UUID
    created_by: UUID
    name: str
    key_prefix: str          # e.g. "sk-engram-xK9p..."
    key_hash: str            # SHA-256 digest of plaintext key
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime
```

---

## 2. Document & Collection Management

```python
class Collection(BaseModel):
    id: UUID
    org_id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    created_at: datetime

class Document(BaseModel):
    id: UUID
    org_id: UUID
    workspace_id: UUID
    folder_id: UUID | None   # Foreign key to collections.id
    filename: str
    content_hash: str        # SHA-256 digest of original file
    current_version_id: UUID | None
    created_at: datetime
    updated_at: datetime

class DocumentVersion(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    file_ref: str            # Object storage path or key
    declared_mime_type: str
    detected_type: Literal[
        "digital_pdf", "scanned_pdf", "docx", "xlsx", "csv", "image", "url"
    ]
    page_count: int | None
    uploaded_by_user_id: UUID
    created_at: datetime

class DocumentMetadata(BaseModel):
    document_version_id: UUID
    title: str | None
    document_type: str | None
    detected_dates: list[str]
    detected_entities: list[str]
    language: str | None
```

---

## 3. Asynchronous Job & Processing Lifecycle

```python
class ProcessingStageStatus(BaseModel):
    stage: Literal[
        "VALIDATION",
        "LAYOUT_EXTRACTION",
        "OCR",
        "STRUCTURE_UNDERSTANDING",
        "STRUCTURED_FACTS",
        "CHUNKING",
        "EMBEDDING",
        "INDEXING",
        "READY",
        "FAILED",
        "PARTIAL",
    ]
    status: Literal["PENDING", "IN_PROGRESS", "COMPLETED", "FAILED", "SKIPPED"]
    progress_current: int | None
    progress_total: int | None
    details: str | None
    started_at: datetime | None
    completed_at: datetime | None

class ProcessingJob(BaseModel):
    id: UUID
    document_id: UUID
    document_version_id: UUID
    org_id: UUID
    workspace_id: UUID
    overall_status: Literal["QUEUED", "PROCESSING", "READY", "FAILED", "PARTIAL"]
    stages: list[ProcessingStageStatus]
    created_at: datetime
    updated_at: datetime
```

---

## 4. Document Layout & Structure Representation

```python
class Page(BaseModel):
    id: UUID
    document_version_id: UUID
    page_number: int
    source_type: Literal["native", "ocr"]
    ocr_confidence: float | None
    raw_text: str

class Section(BaseModel):
    id: UUID
    document_version_id: UUID
    parent_section_id: UUID | None
    level: int               # H1 = 1, H2 = 2, H3 = 3
    title: str | None
    page_start: int
    page_end: int
    section_path: str        # e.g., "1.0 > Financial Review > Capital Expenditure"

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

---

## 5. Text Chunks & Hybrid Search Schema

Chunks are stored in PostgreSQL with their metadata and `tsvector` keyword search representation, while dense vector embeddings are stored in Qdrant using the same `chunk_id`.

```python
class Chunk(BaseModel):
    id: UUID                 # Matches Qdrant point ID
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
    content_hash: str        # SHA-256 of normalized text
    char_offset_start: int
    char_offset_end: int
    embedding_model: str
    created_at: datetime
```

---

## 6. Structured Facts Schema

```python
class ExtractedFact(BaseModel):
    id: UUID
    org_id: UUID
    workspace_id: UUID
    document_id: UUID
    document_version_id: UUID
    page_number: int
    section_path: str | None
    table_id: UUID | None
    entity_name: str         # Target company, division, department, product
    entity_type: str         # e.g., "business_unit", "product_line"
    metric_name: str         # Standardized metric name
    metric_raw_label: str | None
    value: Decimal           # High-precision scalar value
    unit: str                # Normalized unit (e.g. USD, EUR, MT, %)
    period_type: Literal["calendar_year", "fiscal_year", "quarter", "month", "point_in_time"]
    period_value: str        # e.g., "2024", "Q3-2024", "FY2024-25"
    confidence: float        # Composite confidence (0.0 to 1.0)
    extraction_method: Literal["table_parser", "pattern_rule", "llm_assisted"]
    raw_text: str            # Original snippet for audit provenance
    created_at: datetime
```

---

## 7. Query, Retrieval & Citation Models

```python
class Citation(BaseModel):
    citation_id: str         # e.g., "C1" for chunk, "F1" for structured fact
    source_type: Literal["chunk", "fact"]
    document_id: UUID
    document_title: str
    page_number: int | None
    section_path: str | None
    chunk_id: UUID | None
    fact_details: dict | None
    excerpt: str | None

class QueryRequest(BaseModel):
    query_text: str
    document_ids: list[UUID] = []
    route_override: Literal["structured", "unstructured", "hybrid"] | None = None
    top_k: int = 8

class QueryResponse(BaseModel):
    answer: str
    route_used: Literal["STRUCTURED", "UNSTRUCTURED", "HYBRID"]
    no_evidence: bool
    citations: list[Citation]
    confidence: float
    latency_ms: int

class SearchResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    page_numbers: list[int]
    section_path: str | None
    snippet: str
    score: float
    retrieval_source: Literal["DENSE_VECTOR", "LEXICAL_KEYWORD", "HYBRID_FUSION"]
```

---

## 8. Storage Tier Responsibilities

| Data Entity | Primary Store | Indexing & Query Strategy |
|---|---|---|
| **Organizations, Workspaces, Users, API Keys** | PostgreSQL | B-Tree on IDs, Slugs, and `key_hash` for fast auth |
| **Documents, Versions, Processing Jobs** | PostgreSQL | B-Tree on UUIDs, Status, and foreign keys |
| **Layout Tree (Pages, Sections, Tables)** | PostgreSQL | Foreign keys to `document_version_id` |
| **Structured Facts (`ExtractedFact`)** | PostgreSQL | Composite B-Tree on `(workspace_id, entity_name, metric_name, period_value)` |
| **Chunk Text & Metadata** | PostgreSQL | B-Tree + GIN index on `tsvector(text)` for lexical search |
| **Chunk Dense Embeddings** | Qdrant Vector DB | HNSW Cosine Index with payload filtering on `org_id` / `workspace_id` |
| **Original Documents & Rendered Images** | Object Storage (S3 / R2 / MinIO) | Key-value retrieval by `file_ref` |
