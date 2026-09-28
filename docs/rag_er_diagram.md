# RAG Pipeline PostgreSQL Entity-Relationship (ER) Diagram

This diagram documents the relational schema and foreign-key constraints implemented in the PostgreSQL database for the RAG Pipeline microservice.

```mermaid
erDiagram
    organizations {
        uuid id PK
        varchar name
        varchar slug
        text description
        timestamptz created_at
        timestamptz updated_at
    }

    workspaces {
        uuid id PK
        uuid org_id FK
        varchar name
        varchar slug
        text description
        timestamptz created_at
        timestamptz updated_at
    }

    users {
        uuid id PK
        uuid org_id FK
        varchar email
        varchar hashed_password
        varchar full_name
        varchar role
        bool is_active
        timestamptz created_at
        timestamptz updated_at
    }

    api_keys {
        uuid id PK
        uuid org_id FK
        uuid workspace_id FK
        uuid created_by FK
        varchar name
        varchar key_hash
        varchar key_prefix
        bool is_active
        timestamptz last_used_at
        timestamptz created_at
        timestamptz updated_at
    }

    collections {
        uuid id PK
        uuid org_id FK
        uuid workspace_id FK
        varchar name
        text description
        timestamptz created_at
        timestamptz updated_at
    }

    documents {
        uuid id PK
        uuid org_id FK
        uuid workspace_id FK
        uuid folder_id FK
        varchar filename
        varchar content_hash
        uuid current_version_id
        timestamptz created_at
        timestamptz updated_at
    }

    document_versions {
        uuid id PK
        uuid document_id FK
        integer version_number
        varchar file_ref
        varchar declared_mime_type
        varchar detected_type
        integer page_count
        uuid uploaded_by_user_id FK
        timestamptz created_at
    }

    pages {
        uuid id PK
        uuid document_version_id FK
        integer page_number
        varchar source_type
        float ocr_confidence
        text raw_text
        timestamptz created_at
    }

    sections {
        uuid id PK
        uuid document_version_id FK
        uuid parent_section_id FK
        integer level
        varchar title
        integer page_start
        integer page_end
        varchar section_path
        timestamptz created_at
    }

    tables {
        uuid id PK
        uuid document_version_id FK
        integer page_number
        uuid section_id FK
        integer row_count
        integer col_count
        jsonb header_row
        jsonb raw_cells
        timestamptz created_at
    }

    chunks {
        uuid id PK
        uuid document_id FK
        uuid document_version_id FK
        uuid org_id FK
        uuid workspace_id FK
        integer page_start
        integer page_end
        uuid section_id FK
        varchar section_path
        varchar chunk_type
        text text
        varchar content_hash
        integer char_offset_start
        integer char_offset_end
        varchar embedding_model
        tsvector search_vector
        timestamptz created_at
    }

    extracted_facts {
        uuid id PK
        uuid org_id FK
        uuid workspace_id FK
        uuid document_id FK
        uuid document_version_id FK
        integer page_number
        varchar section_path
        uuid table_id FK
        varchar entity_name
        varchar entity_type
        varchar metric_name
        varchar metric_raw_label
        numeric value
        varchar unit
        varchar period_type
        varchar period_value
        float confidence
        varchar extraction_method
        text raw_text
        timestamptz created_at
    }

    processing_jobs {
        uuid id PK
        uuid document_id FK
        uuid document_version_id FK
        uuid org_id FK
        uuid workspace_id FK
        varchar overall_status
        jsonb stage_status
        timestamptz created_at
        timestamptz updated_at
    }

    job_tasks {
        uuid id PK
        uuid job_id FK
        varchar task_type
        varchar status
        integer page_batch_start
        integer page_batch_end
        text error_message
        timestamptz started_at
        timestamptz completed_at
    }

    organizations ||--o{ workspaces : "owns"
    organizations ||--o{ users : "employs"
    organizations ||--o{ api_keys : "owns"
    workspaces ||--o{ api_keys : "scopes"
    workspaces ||--o{ collections : "contains"
    workspaces ||--o{ documents : "contains"
    users ||--o{ api_keys : "creates"
    collections ||--o{ documents : "categorizes"
    documents ||--o{ document_versions : "has"
    document_versions ||--o{ pages : "contains"
    document_versions ||--o{ sections : "contains"
    document_versions ||--o{ tables : "contains"
    document_versions ||--o{ chunks : "produces"
    document_versions ||--o{ extracted_facts : "yields"
    documents ||--o{ processing_jobs : "triggers"
    processing_jobs ||--o{ job_tasks : "decomposes_into"
```
