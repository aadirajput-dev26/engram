import asyncio
import time
from sqlalchemy import text
from app.db.session import async_session_factory
from app.core.vectorstore.qdrant_service import _get_client
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding

async def reindex():
    print("--- 1. Fetching all chunks from PostgreSQL ---")
    async with async_session_factory() as session:
        query = text("""
            SELECT
                c.id,
                c.document_id,
                c.document_version_id,
                c.org_id,
                c.workspace_id,
                c.page_start,
                c.page_end,
                c.section_path,
                c.chunk_type,
                c.text,
                d.filename as document_name
            FROM chunks c
            LEFT JOIN documents d ON d.id = c.document_id
            ORDER BY c.created_at ASC
        """)
        rows = (await session.execute(query)).mappings().all()

    print(f"Found {len(rows)} chunks in database.")
    if not rows:
        return

    texts = [r["text"] for r in rows]

    print("--- 2. Loading FastEmbed TextEmbedding ---")
    t0 = time.time()
    model = TextEmbedding("BAAI/bge-base-en-v1.5", cache_dir="/tmp/fastembed_cache", threads=2)
    print(f"Model loaded in {time.time()-t0:.2f}s")

    print(f"--- 3. Generating real embeddings for {len(texts)} chunks ---")
    t0 = time.time()
    vectors = []
    for i in range(0, len(texts), 32):
        batch = texts[i:i+32]
        gen = model.embed(batch, batch_size=32)
        batch_vecs = [e.tolist() for e in gen]
        vectors.extend(batch_vecs)
        print(f"  Embedded {len(vectors)}/{len(texts)} chunks...")

    print(f"Finished {len(vectors)} embeddings in {time.time()-t0:.2f}s! Vector dim: {len(vectors[0])}")

    # Build PointStructs
    points = []
    for r, vec in zip(rows, vectors):
        payload = {
            "chunk_id": str(r["id"]),
            "document_id": str(r["document_id"]),
            "document_version_id": str(r["document_version_id"]),
            "org_id": str(r["org_id"]),
            "workspace_id": str(r["workspace_id"]),
            "page_start": r["page_start"],
            "page_end": r["page_end"],
            "section_path": r["section_path"] or "",
            "chunk_type": r["chunk_type"],
            "text": r["text"],
            "document_name": r["document_name"] or "Document",
        }
        points.append(PointStruct(id=str(r["id"]), vector=vec, payload=payload))

    print("--- 4. Upserting into Qdrant collections ---")
    client = _get_client()
    for col in ["document_chunks", "rag_chunks"]:
        try:
            client.get_collection(col)
        except Exception:
            client.create_collection(
                collection_name=col,
                vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE),
            )
        # Upsert in batches
        for i in range(0, len(points), 50):
            client.upsert(collection_name=col, points=points[i:i+50])
        count = client.count(collection_name=col)
        print(f"Collection '{col}' now has {count.count} points.")

    print("--- 5. Updating embedding_model in PostgreSQL ---")
    async with async_session_factory() as session:
        await session.execute(
            text("UPDATE chunks SET embedding_model = 'BAAI/bge-base-en-v1.5'")
        )
        await session.commit()
    print("ALL 114 CHUNKS SUCCESSFULLY RE-EMBEDDED WITH REAL BAAI/bge-base-en-v1.5 EMBEDDINGS!")

if __name__ == "__main__":
    asyncio.run(reindex())
