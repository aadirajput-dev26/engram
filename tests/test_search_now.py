import time
from app.core.vectorstore.qdrant_service import search_vectors
from fastembed import TextEmbedding

t0 = time.time()
model = TextEmbedding("BAAI/bge-base-en-v1.5", cache_dir="/tmp/fastembed_cache", threads=2)
q = "What projects and technical skills are listed on the resume?"
vec = list(model.embed([q]))[0]
print(f"Embedded query in {time.time()-t0:.2f}s")

t0 = time.time()
res = search_vectors(vec, "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", top_k=5)
print(f"Searched vectors in {time.time()-t0:.2f}s")
for i, r in enumerate(res):
    print(f"[{i}] score={r.get('score'):.4f}, page={r.get('page_start')}: {repr(r.get('text', '')[:120])}")
