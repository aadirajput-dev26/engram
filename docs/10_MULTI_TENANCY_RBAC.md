# 10 — Multi-Tenancy and Access Control (RBAC)

## 1. Tenancy Hierarchy

The RAG Pipeline microservice implements a strict hierarchical tenancy model to guarantee complete cryptographic and logical isolation of enterprise data:

```
Organization (`org_id`)
  └── Workspace (`workspace_id`)
        ├── API Keys (`sk-engram-...`)
        └── Collections / Folders (`folder_id`)
              └── Documents (`document_id`)
                    ├── Document Versions (`document_version_id`)
                    ├── Structured Facts (`ExtractedFact`)
                    └── Narrative Chunks (`Chunk` in Postgres & Qdrant)
```

- **Organization:** The highest boundary. Represents the enterprise client or legal entity. Cross-organization queries are strictly prohibited.
- **Workspace:** The functional partition (e.g., department, project, business unit, or operational domain). All document ingestion, chunking, embeddings, and query resolutions are strictly scoped to a workspace.
- **Collections:** Logical groupings or folders within a workspace for targeted document filtering.
- **API Keys:** Scoped cryptographic credentials. Each programmatic key (`sk-engram-...`) is issued for a specific `workspace_id` under an `org_id`.

---

## 2. API Key Authentication & Automated Scoping

To maximize security and eliminate developer friction, the microservice implements **automated scope resolution**:

1. **Incoming Request:** Client applications authenticate using the standard HTTP header:
   ```http
   X-Api-Key: sk-engram-9f2b8471...
   ```
2. **Cryptographic Validation:** The service hashes the incoming key using SHA-256 and matches it against the `api_keys` table in constant time.
3. **Tenant Context Extraction:** Upon validation, the active session is automatically populated with the authenticated `org_id` and `workspace_id`.
4. **Zero Redundancy:** Calling clients do not pass redundant `org_id` or `workspace_id` parameters in request bodies or query strings. Tenant boundaries are enforced server-side.

---

## 3. Role & Capability Model

When interacting with the management APIs (such as user provisioning and key generation), access is governed by role-based capabilities:

| Role | Scope | Description |
|---|---|---|
| `SUPER_ADMIN` | Platform-wide | Manages organizations, infrastructure settings, and system-wide audits. |
| `ORG_ADMIN` | Organization | Manages workspaces, workspace memberships, and organizational settings. |
| `MEMBER` | Workspace | Ingests documents, triggers processing, runs queries, and manages collections. |
| `VIEWER` | Workspace | Read-only access: executes queries and inspects document summaries without mutation rights. |

### Capability Matrix

| Capability | SUPER_ADMIN | ORG_ADMIN | MEMBER | VIEWER |
|---|---|---|---|---|
| `documents:read` | ✔ | ✔ | ✔ | ✔ |
| `documents:ingest` | ✔ | ✔ | ✔ | ✘ |
| `documents:delete` | ✔ | ✔ | ✘ | ✘ |
| `api_keys:manage` | ✔ | ✔ | ✘ | ✘ |
| `query:execute` | ✔ | ✔ | ✔ | ✔ |
| `analytics:read` | ✔ | ✔ | ✔ | ✔ |
| `workspaces:manage` | ✔ | ✔ | ✘ | ✘ |

---

## 4. Multi-Tenant Data Isolation Guarantees

Isolation is enforced through defense-in-depth across every storage engine:

### 4.1 Relational Storage (PostgreSQL)
- All document, chunk, fact, and job records include foreign keys to `org_id` and `workspace_id`.
- Data access layers enforce mandatory `WHERE workspace_id = :workspace_id AND org_id = :org_id` predicates across all queries, updates, and deletes.
- Reprocess and status operations reject requests targeting documents outside the caller's authorized workspace.

### 4.2 Vector Database (Qdrant)
- Vectors stored in Qdrant carry metadata payloads including `org_id` and `workspace_id`.
- Every search or hybrid retrieval query applies an immutable payload filter mask during HNSW index traversal:
  ```json
  {
    "must": [
      { "key": "org_id", "match": { "value": "<caller_org_id>" } },
      { "key": "workspace_id", "match": { "value": "<caller_workspace_id>" } }
    ]
  }
  ```
- Result candidates belonging to other tenants are masked out at index time, ensuring zero vector leakage and constant-time tenant isolation.

### 4.3 Object Storage (S3 / R2 / MinIO)
- Document binaries and intermediate artifacts are organized in partitioned object prefixes:
  ```
  s3://<bucket>/orgs/{org_id}/workspaces/{workspace_id}/docs/{document_id}/{filename}
  ```

---

## 5. Security & Key Lifecycle Management

- **Zero Plaintext Storage:** Plaintext API keys are generated once via high-entropy cryptographically secure random bytes (`secrets.token_urlsafe`) and presented to the creator. Only the SHA-256 hash (`key_hash`) and a truncated display prefix (`key_prefix`, e.g., `sk-engram-xK9p...`) are stored in the database.
- **Revocation & Expiry:** API keys can be instantly deactivated by setting `is_active = false` without requiring service restarts.
- **Audit Logging:** Every key lookup updates `last_used_at` timestamps, providing audit transparency for active client integrations.
