import httpx
import json

client = httpx.Client(
    base_url="http://127.0.0.1:8000",
    headers={"X-Api-Key": "a6XbhUYTRn092WEzq45mbASyh1BSCN"},
    timeout=60.0
)

# Test with document_id of resume: d2a7c77e-df65-4dc5-9330-ca0a52b6318b
payload = {
    "query_text": "What projects and technical skills are listed on the resume?",
    "scope": {
        "org_id": "11111111-1111-1111-1111-111111111111",
        "workspace_id": "22222222-2222-2222-2222-222222222222",
        "document_ids": ["d2a7c77e-df65-4dc5-9330-ca0a52b6318b"]
    },
    "top_k": 5
}

r = client.post("/api/v1/query", json=payload)
data = r.json()
print("Status:", r.status_code)
print("Latency_ms:", data.get("latency_ms"))
print("No evidence:", data.get("no_evidence"))
print("Answer:\n", data.get("answer"))
print("\nCitations:", data.get("citations"))
