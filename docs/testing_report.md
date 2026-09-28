# RAG Pipeline Quality Assurance & Testing Report

This document outlines the testing strategy, test suites, and empirical benchmarks implemented to validate the RAG Pipeline microservice. Testing ensures that the service executes document ingestion, layout parsing, hybrid retrieval, structured extraction, and AI-grounded responses reliably and securely across multi-tenant environments.

---

## 1. Unit Testing Strategy

The unit test suite (`/tests/unit`) exercises individual components of the RAG microservice in isolation:

*   **API Routing & Security Layer:**
    *   `test_api_endpoints.py`: Validates FastAPI route definitions, request validation, and correct HTTP status code responses.
    *   `test_auth.py`: Ensures API keys (`sk-engram-...`) are hashed and validated, and requests are properly scoped by tenant boundaries (`org_id`, `workspace_id`).
    *   `test_job_queue.py`: Tests PostgreSQL-native `SKIP LOCKED` task polling and state tracking.

*   **Document Parsing & Chunking Engine:**
    *   `test_chunking.py`: Validates structure-aware semantic chunking (boundary preservation, token budget ceilings, sentence-boundary splitting).
    *   `test_table_parser.py`: Verifies deterministic table extraction and cell-matrix mapping into structured records.

*   **AI & Hybrid Retrieval Core:**
    *   `test_query_router.py`: Tests intent classification routing queries to `STRUCTURED`, `UNSTRUCTURED`, or `HYBRID` paths.
    *   `test_retrieval_fusion.py`: Validates Reciprocal Rank Fusion (RRF) and hybrid search result merging across vector and lexical candidate pools.
    *   `test_citation_service.py`: Verifies provenance tracking and citation attachment.
    *   `test_claim_verifier.py`: Tests the post-generation verification module that checks numeric exactness and narrative entailment.
    *   `test_regex_extractor.py` & `test_topic_service.py`: Validates entity extraction and topic clustering.

---

## 2. Integration Testing

Integration tests verify end-to-end communication across PostgreSQL, Qdrant, object storage, and LLM endpoints:

*   **Datastore & Vector Engine Connectivity:**
    *   `test_qdrant.py`: Verifies vector collection creation, payload indexing, and filtered ANN search.
    *   `test_storage_path.py`: Tests object storage read/write paths for document binaries.
*   **LLM Provider Interfaces:**
    *   `test_litellm.py` & `test_gemini.py`: Verifies OpenAI-compatible API client connectivity, request timeouts, and error handling.
*   **End-to-End API Integration:**
    *   `test_all_13_endpoints.py`: Executes a complete lifecycle test through core REST endpoints (upload, status poll, chunk inspection, query, collection management).
    *   `test_all_curls.py` & `test_inside_docker.py`: Validates standard client requests both locally and inside containerized environments.
    *   `test_latency.py`: Verifies response latency meets SLA thresholds.
    *   `test_scoped.py`: Verifies strict multi-tenant isolation, ensuring requests scoped to Workspace A can never access or retrieve documents from Workspace B.

---

## 3. Large-Scale AI Evaluation (35-Page Synthetic Corpus Benchmark)

To empirically evaluate retrieval recall and hallucination prevention:

*   **Evaluation Corpus:** Evaluated against a 35-page synthetic data-heavy technical and financial report containing dense tables, exact metrics, dates, and narrative operational reviews.
*   **Benchmark Scale:** 100+ unique evaluation queries spanning factual recall, multi-hop reasoning, table extraction, and summarization.
*   **Evaluation Criteria:**
    *   **Context Relevance:** Did hybrid retrieval surface the expected source pages in top-$K$ candidates?
    *   **Answer Accuracy:** Did the synthesis engine extract the correct factual data without hallucinations?
    *   **Citation Precision:** Do attached citations point to the exact source page, section, and paragraph?
    *   **Refusal on Missing Evidence:** Did out-of-scope queries properly return `NO_EVIDENCE_FOUND`?
