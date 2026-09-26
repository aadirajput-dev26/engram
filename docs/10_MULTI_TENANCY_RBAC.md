# 10 — Multi-Tenancy and RBAC

## 1. Tenancy Hierarchy

```
Organization  (e.g., a CIL subsidiary, or CMPDI, or a Ministry department — generic, not hard-coded)
  → Workspace  (department/project within the organization)
    → Folder    (existing concept in the current portal — VERIFY AGAINST EXISTING REPOSITORY for exact current semantics)
      → Document
```

- **Decision:** `Organization` is a first-class, generic entity. No subsidiary name (e.g., "NCL", "SECL") appears anywhere in code, config enums, or schema constraints — only as *data* rows.
- **Alternative considered:** hard-coding a fixed list of CIL subsidiaries as an enum for faster initial development. **Reason for rejection:** explicitly disallowed by the problem statement's generality requirement, and it would block onboarding CMPDI/Ministry/any future organization without a code change.

## 2. Roles

| Role | Scope | Description |
|---|---|---|
| `SUPER_ADMIN` | Platform-wide | Manages organizations, platform configuration, cross-org support access (with audit logging). |
| `ORG_ADMIN` | Single organization | Manages workspaces, members, and role assignments within their organization. |
| `MEMBER` | Workspace(s) they're added to | Normal usage: upload, query, generate reports, subject to granted capabilities. |
| `VIEWER` | Workspace(s)/document(s) they're granted | Read-only: view documents, analytics, reports. Cannot upload, delete, or trigger AI actions that mutate state (may still be granted `ai.query` read-style access — see capability table). |

> **VERIFY AGAINST EXISTING REPOSITORY:** if the existing Express app already implements a different role set, this document's roles must be reconciled with (not silently replacing) the existing implementation before coding begins. This role set matches the problem statement's explicit list and is the target if no conflicting implementation exists.

## 3. Capabilities (capability-based permission model)

Roles map to default capability sets; capabilities (not roles) are what every authorization check actually tests, so future custom roles/fine-grained overrides are possible without redesigning enforcement points.

| Capability | SUPER_ADMIN | ORG_ADMIN | MEMBER | VIEWER |
|---|---|---|---|---|
| `documents.read` | ✔ | ✔ | ✔ | ✔ |
| `documents.upload` | ✔ | ✔ | ✔ | ✘ |
| `documents.delete` | ✔ | ✔ | ✘ (or configurable) | ✘ |
| `analytics.read` | ✔ | ✔ | ✔ | ✔ |
| `reports.create` | ✔ | ✔ | ✔ | ✘ |
| `reports.approve` | ✔ | ✔ | ✘ | ✘ |
| `ai.query` | ✔ | ✔ | ✔ | ✔ (read-style only) |
| `users.manage` | ✔ | ✔ (within own org) | ✘ | ✘ |

- **Decision:** capabilities are assigned per role by default but stored as an explicit per-user-per-workspace grant table in Express (not purely derived from role name in code), so an `ORG_ADMIN` could, e.g., have `reports.approve` revoked for a specific workspace if the business needs it later, without a schema change.

## 4. Document-Level Authorization

- Default: a user's access to a document is derived from their role/membership in the document's workspace.
- Optional finer-grained override: specific documents can be restricted further (e.g., a sensitive parliamentary-inquiry document visible only to specific users within a workspace) via an explicit `document_access_grant` table. **This is flagged as a should-have, not verified as already implemented** — VERIFY AGAINST EXISTING REPOSITORY before assuming it exists; if absent, workspace-level access is the enforced default and document-level overrides are a roadmap item (`18_IMPLEMENTATION_ROADMAP.md`).
- Every AI-service-facing operation (query, search, extract, topics, report generation) must resolve to an explicit list of `allowed_document_ids` (or an explicit `workspace_scope: true` meaning "everything currently visible to this user in this workspace, evaluated at token-mint time") — this resolution happens in Express, not FastAPI (see `02_SYSTEM_ARCHITECTURE.md` §4).

## 5. Enforcement Points

| Layer | What it enforces |
|---|---|
| Express API layer | All CRUD on organizations/workspaces/folders/documents/reports; role/capability checks on every endpoint. |
| Express → FastAPI scope minting | Resolves the calling user's effective `allowed_document_ids`/`workspace_scope` and `permissions` **at request time**, embeds in the signed scope token. |
| FastAPI request layer | Validates scope token signature/expiry; rejects any operation whose target falls outside the token's scope. |
| FastAPI retrieval/query layer | Applies scope as a **native filter** on every Qdrant/Postgres query (see `05_RETRIEVAL_AND_RERANKING.md` §9) — defense in depth, not solely relying on "only authorized documents were listed in the request." |

## 6. Cross-Organization Isolation

- No query, retrieval, or structured-data lookup may span organizations implicitly. `org_id` is always part of the mandatory filter, even for `SUPER_ADMIN` support access (which instead performs an explicit, audited "impersonate scope" action in Express rather than FastAPI ever accepting an unscoped/multi-org request).
- Qdrant and Postgres FTS indexes are shared infrastructure but logically partitioned via mandatory payload/row filters — see `05_RETRIEVAL_AND_RERANKING.md` §3–4 for the specific mechanism and its rejected alternative (per-org collections).

## 7. Open Items for Verification

- Exact current Express auth mechanism (session cookie vs JWT vs OAuth) — **VERIFY AGAINST EXISTING REPOSITORY**.
- Whether "Folder" in the existing app already maps 1:1 to "Workspace" or is a separate nested level — **VERIFY AGAINST EXISTING REPOSITORY**; this document assumes `Workspace → Folder → Document` as stated in the problem brief's existing conceptual structure (`User → Folder/Workspace → Documents → ...`), but the precise nesting must be confirmed against real schema before Phase 13 (Express integration) begins.
