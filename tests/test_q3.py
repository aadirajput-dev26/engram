import asyncio
from app.db.session import async_session_factory
from app.core.retrieval.semantic import semantic_search
from app.core.retrieval.keyword import keyword_search
from app.core.retrieval.fusion import reciprocal_rank_fusion
from app.core.rerank.reranker_service import rerank

async def test():
    q = "What projects and technical skills are listed on the resume?"
    org_id = "11111111-1111-1111-1111-111111111111"
    ws_id = "22222222-2222-2222-2222-222222222222"

    sem = semantic_search(q, org_id, ws_id, top_n=10)
    print("Semantic top 3:")
    for i, r in enumerate(sem[:3]):
        print(f"  [{i}] doc_id={r.get('document_id')} text={repr(r.get('text', '')[:60])}")

    async with async_session_factory() as s:
        kw = await keyword_search(s, q, org_id, ws_id, top_n=10)
    print("Keyword top 3:")
    for i, r in enumerate(kw[:3]):
        print(f"  [{i}] doc_id={r.get('document_id')} text={repr(r.get('text', '')[:60])}")

    fused = reciprocal_rank_fusion(sem, kw)
    print("Fused top 5:")
    for i, r in enumerate(fused[:5]):
        print(f"  [{i}] doc_id={r.get('document_id')} text={repr(r.get('text', '')[:60])}")

asyncio.run(test())
