# GeoGyan AI: Multi-Tenant RAG Microservice

Welcome to the **GeoGyan AI RAG Pipeline** repository.

This service is a high-performance, stateless **FastAPI** microservice acting as the sole AI worker and Retrieval-Augmented Generation (RAG) engine for the GeoGyan platform. It is designed from the ground up as a strict **multi-tenant** AI microservice, handling document ingestion, embedding generation, semantic search, and generative question-answering in complete isolation per organization and workspace.

## 🌟 Architecture Overview

This microservice follows a "Backend-for-Frontend" worker pattern:
1. **Delegated Authentication**: It does not handle user sessions, passwords, or direct web requests from the frontend. It only communicates with the main Express Backend.
2. **Strict Multi-Tenancy**: Every request, document, and vector embedding is strictly partitioned by `org_id` and `workspace_id` (and optionally `collection_id`). Tenants cannot cross-pollinate data.
3. **Pure AI Capabilities**: The service specializes strictly in what it does best: parsing documents (PDF, DOCX, XLSX, HTML), generating vector embeddings via Qdrant, and orchestrating RAG queries using LLMs (Gemini/OpenAI). 
4. **Stateless Scalability**: Since the heavy lifting (Auth, Billing, Job Queues) is handled by the Express Backend, this RAG API can be horizontally scaled infinitely as a stateless worker on platforms like Render or AWS.

## 🚀 Features

- **Multi-Tenant Vector Search**: Leveraging Qdrant for blazing-fast semantic and hybrid search, strictly isolated by tenant namespaces.
- **Advanced Ingestion**: Universal document parsers supporting unstructured and structured data formats, with automatic chunking.
- **Collections / Folders API**: Group documents into specific collections for scoped search and querying.
- **Retrieval-Augmented Generation**: Integrates directly with LLMs (e.g. Gemini) to provide cited, verifiable answers based strictly on the uploaded source material.
- **Asynchronous & Non-Blocking**: Built on FastAPI and SQLAlchemy (AsyncPG) to handle concurrent I/O operations seamlessly.

## 🛠 Tech Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL (SQLAlchemy + AsyncPG) for metadata
- **Vector Store**: Qdrant Cloud for vector embeddings
- **LLM / Embeddings**: LiteLLM (Gemini, OpenAI, HuggingFace)
- **Migrations**: Alembic

## 📦 Local Development

1. **Clone and Install**
   ```bash
   git clone <repo-url>
   cd RAG_PIPELINE
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Environment Setup**
   Create a `.env` file based on `.env.example`:
   ```env
   SERVICE_ENV=local
   AI_SERVICE_API_KEY=your_super_secret_master_key
   AI_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
   QDRANT_URL=http://localhost:6333
   LLM_API_KEY=your_gemini_or_openai_api_key
   ```

3. **Database Migrations**
   ```bash
   alembic upgrade head
   ```

4. **Run the Server**
   ```bash
   uvicorn app.main:app --reload
   ```

## 🔐 Security & Auth
This service expects an `X-Api-Key` header on **every** request. This key must match the `AI_SERVICE_API_KEY` defined in the `.env` file. It is the responsibility of the main Express backend to protect this key and pass it securely.
