# RAG Pipeline Quality Assurance & Testing Report

This document outlines the comprehensive testing strategy and test suites implemented to validate the RAG (Retrieval-Augmented Generation) Pipeline. Our testing approach ensures that the system handles document ingestion, semantic search, and AI-generated responses securely, accurately, and reliably.

## 1. Unit Testing Strategy

The unit test suite (`/tests/unit`) targets individual components of the RAG microservice in isolation to ensure core logic operates flawlessly.

*   **API & Core Logic:**
    *   `test_api_endpoints.py`: Validates FastAPI route definitions, request validation, and correct HTTP status code responses.
    *   `test_auth.py`: Ensures API keys are correctly validated and requests are properly scoped by tenant boundaries (`org_id`, `workspace_id`).
    *   `test_job_queue.py`: Tests the background job tracking mechanisms for document processing tasks.

*   **Document Parsing & Chunking:**
    *   `test_chunking.py`: Validates the text splitting logic (ensuring chunks overlap correctly and maintain semantic boundaries).
    *   `test_table_parser.py`: Verifies the extraction logic for tabular data embedded within documents.

*   **AI & Retrieval Core Services:**
    *   `test_query_router.py`: Tests the routing logic that decides whether a query needs semantic search, exact match, or aggregation.
    *   `test_retrieval_fusion.py`: Validates Reciprocal Rank Fusion (RRF) and hybrid search result merging.
    *   `test_citation_service.py`: Ensures that AI responses correctly map back to exact source text chunks.
    *   `test_claim_verifier.py`: Tests the hallucination-prevention module that verifies LLM claims against retrieved context.
    *   `test_regex_extractor.py` & `test_topic_service.py`: Validates extraction of specific entities and semantic topics.

## 2. Integration Testing

Integration tests verify that our external databases and internal components communicate correctly.

*   **Database & Infrastructure Connectivity:**
    *   `test_qdrant.py`: Verifies vector database connection, collection creation, and upsert operations.
    *   `test_storage_path.py`: Ensures file storage paths are resolved correctly for document ingestion.
*   **LLM Provider Integrations:**
    *   `test_litellm.py` & `test_gemini.py`: Verifies that calls to LLM providers succeed and handle rate limits correctly.
*   **End-to-End API Integration:**
    *   `test_all_13_endpoints.py`: Runs a complete lifecycle test through all 13 core REST API endpoints (upload, poll status, query, delete).
    *   `test_all_curls.py` & `test_inside_docker.py`: Validates that standard client requests succeed both locally and inside containerized environments.
    *   `test_latency.py`: Ensures the API responds within the established SLA thresholds.
    *   `test_scoped.py`: Verifies multi-tenancy rules—preventing a user in Workspace A from querying documents in Workspace B.

## 3. Large-Scale AI Evaluation (35-Page Synthetic Report)

To ensure high-quality AI intelligence, we maintain a comprehensive LLM evaluation suite documented in `TEST_RESULTS_35_PAGE_REPORT.md` and `test_rag_responses.md`.

*   **Test Environment:** Evaluated against a 35-page synthetic mining report to simulate complex, multi-page data extraction.
*   **Scale:** Over 100+ unique test queries spanning factual recall, multi-hop reasoning, table extraction, and summarization.
*   **Methodology:** Queries are sent directly to the RAG endpoint, evaluating:
    *   **Context Relevance:** Did the pipeline retrieve the correct pages/chunks?
    *   **Answer Accuracy:** Did the LLM extract the correct factual data without hallucinations?
    *   **Citation Correctness:** Does the provided citation match the exact source page and paragraph?
