import asyncio
from app.db.session import async_session_factory
from app.core.retrieval.semantic import semantic_search
from app.core.retrieval.keyword import keyword_search
from app.core.retrieval.fusion import reciprocal_rank_fusion
from app.core.rerank.reranker_service import rerank
from app.core.generation.context_builder import build_context
from app.core.generation.llm_client import generate

async def test():
    q = "What projects and technical skills are listed on the resume?"
    org_id = "11111111-1111-1111-1111-111111111111"
    ws_id = "22222222-2222-2222-2222-222222222222"

    sem = semantic_search(q, org_id, ws_id, top_n=10)
    async with async_session_factory() as s:
        kw = await keyword_search(s, q, org_id, ws_id, top_n=10)
    fused = reciprocal_rank_fusion(sem, kw)
    rr = rerank(q, fused, top_k=5)

    msgs = build_context(rr, query_text=q)
    print("--- User prompt to LLM ---")
    for i, chunk in enumerate(rr, 1):
        print(f"Evidence C{i} doc={chunk.get('document_name')} snippet={repr(chunk.get('text', '')[:100])}")

    ans = await generate(msgs)
    print("\n--- LLM Answer ---")
    print(ans)

asyncio.run(test())
