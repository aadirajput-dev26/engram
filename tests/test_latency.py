import httpx
import json
import time

client = httpx.Client(
    base_url="http://127.0.0.1:8000",
    headers={"X-Api-Key": "a6XbhUYTRn092WEzq45mbASyh1BSCN"},
    timeout=60.0
)

for query in [
    "What were the safety incidents across the years?",
    "provide the energy consumption data in years",
    "What projects and technical skills are listed on the resume?"
]:
    payload = {
        "query_text": query,
        "scope": {
            "org_id": "11111111-1111-1111-1111-111111111111",
            "workspace_id": "22222222-2222-2222-2222-222222222222"
        },
        "top_k": 5
    }

    t0 = time.time()
    r = client.post("/api/v1/query", json=payload)
    elapsed = time.time() - t0
    data = r.json()
    print(f"\n==================================================")
    print(f"Query: '{query}'")
    print(f"Elapsed: {elapsed:.2f}s | Server Latency: {data.get('latency_ms')}ms | Route: {data.get('route_used')} | No_Evidence: {data.get('no_evidence')}")
    print(f"Citations: {len(data.get('citations', []))}")
    print(f"Answer:\n{data.get('answer')[:350]}...")
