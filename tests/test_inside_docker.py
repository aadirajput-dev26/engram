import asyncio
import time
from app.db.session import async_session_factory
from app.core.config import get_settings
from app.core.retrieval.semantic import semantic_search
from app.core.retrieval.keyword import keyword_search
from app.core.retrieval.fusion import reciprocal_rank_fusion
from app.core.rerank.reranker_service import rerank
from app.core.generation.context_builder import build_context
from app.core.generation.llm_client import generate
from app.core.validation.claim_verifier import verify_response

async def test():
    settings = get_settings()
    print("Collection name:", settings.QDRANT_COLLECTION_NAME)
    query = "provide the energy consumption data in years"
    org_id = "11111111-1111-1111-1111-111111111111"
    ws_id = "22222222-2222-2222-2222-222222222222"

    t0 = time.time()
    sem = semantic_search(query, org_id, ws_id, top_n=10)
    print(f"Semantic search ({len(sem)} results, took {time.time()-t0:.2f}s):")
    for i, s in enumerate(sem[:3]):
        print(f"  [{i}] score={s.get('score')}: {repr(s.get('text', '')[:120])}")

    t0 = time.time()
    async with async_session_factory() as session:
        kw = await keyword_search(session, query, org_id, ws_id, top_n=10)
    print(f"Keyword search ({len(kw)} results, took {time.time()-t0:.2f}s):")
    for i, k in enumerate(kw[:3]):
        print(f"  [{i}] kw_score={k.get('keyword_score')}: {repr(k.get('text', '')[:120])}")

    t0 = time.time()
    fused = reciprocal_rank_fusion(sem, kw)
    rr = rerank(query, fused, top_k=5)
    print(f"Rerank ({len(rr)} results, took {time.time()-t0:.2f}s):")
    for i, r in enumerate(rr[:3]):
        print(f"  [{i}] score={r.get('rerank_score')}: {repr(r.get('text', '')[:120])}")

    msgs = build_context(rr, query_text=query)
    print("--- User prompt to LLM ---")
    print(msgs[1]["content"][:500])
    print("...")

    print("Calling LLM...")
    t0 = time.time()
    ans = await generate(msgs)
    print(f"LLM took {time.time()-t0:.2f}s")
    print("LLM response:")
    print(ans)

    v = verify_response(ans, rr)
    print("Verification:")
    print("  verified_answer:", v.verified_answer)
    print("  no_evidence:", v.no_evidence)
    print("  confidence:", v.overall_confidence)

asyncio.run(test())
