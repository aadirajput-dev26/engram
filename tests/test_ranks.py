from app.core.vectorstore.qdrant_service import search_vectors
from app.core.embeddings.embedding_service import embed_query

q = "provide the energy consumption data in years"
vec = embed_query(q)
res = search_vectors(vec, "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", top_k=86)

print(f"Total results: {len(res)}")
found = 0
for i, r in enumerate(res):
    text = r.get("text", "")
    score = r.get("score")
    page = r.get("page_start")
    if "energy consumption" in text.lower():
        found += 1
        print(f"Rank {i+1} [score={score:.4f}, page={page}]: {repr(text[:70])}")

print(f"\nTotal containing 'energy consumption': {found}")
print("\nTop 5 overall retrieved by semantic search:")
for i, r in enumerate(res[:5]):
    print(f"Top {i+1} [score={r.get('score'):.4f}, page={r.get('page_start')}]: {repr(r.get('text', '')[:70])}")
