import json
import httpx
import uuid

BASE_URL = "http://127.0.0.1:8000"
API_KEY = "a6XbhUYTRn092WEzq45mbASyh1BSCN"
HEADERS = {"X-Api-Key": API_KEY}

ORG_ID = "11111111-1111-1111-1111-111111111111"
WORKSPACE_ID = "22222222-2222-2222-2222-222222222222"
USER_ID = "33333333-3333-3333-3333-333333333333"

def run_tests():
    print("==================================================")
    print("STARTING FULL API SUITE TEST")
    print("==================================================\n")

    client = httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=60.0)

    # 1. Health Liveness
    r = client.get("/health")
    print(f"1. GET /health -> Status: {r.status_code}, Body: {r.json()}")
    assert r.status_code == 200

    # 2. Health Readiness
    r = client.get("/health/ready")
    print(f"2. GET /health/ready -> Status: {r.status_code}, Body: {r.json()}")
    assert r.status_code == 200

    # 3. Document Ingest (Add document, parse, chunk, embed, index)
    with open("data/sample_resume.pdf", "rb") as f:
        files = {"file": ("sample_resume.pdf", f, "application/pdf")}
        data = {
            "org_id": ORG_ID,
            "workspace_id": WORKSPACE_ID,
            "uploaded_by_user_id": USER_ID,
            "filename": "sample_resume.pdf"
        }
        r = client.post("/api/v1/documents/ingest", files=files, data=data)
    
    print(f"\n3. POST /api/v1/documents/ingest -> Status: {r.status_code}")
    ingest_resp = r.json()
    print("   Response:", json.dumps(ingest_resp, indent=2))
    assert r.status_code == 200
    doc_id = ingest_resp["document_id"]
    doc_ver_id = ingest_resp["document_version_id"]
    job_id = ingest_resp["job_id"]

    # 4. Document Status Check
    r = client.get(f"/api/v1/documents/{doc_id}/status")
    print(f"\n4. GET /api/v1/documents/{doc_id}/status -> Status: {r.status_code}")
    print("   Response:", json.dumps(r.json(), indent=2))
    assert r.status_code == 200

    # 5. Search API (Retrieval-only: semantic + keyword + RRF + rerank)
    search_payload = {
        "query_text": "Backend Engineer experience and skills in Python and FastAPI",
        "scope": {
            "org_id": ORG_ID,
            "workspace_id": WORKSPACE_ID,
            "document_ids": [doc_id]
        },
        "top_k": 5
    }
    r = client.post("/api/v1/search", json=search_payload)
    print(f"\n5. POST /api/v1/search -> Status: {r.status_code}")
    print("   Response:", json.dumps(r.json(), indent=2))
    assert r.status_code == 200

    # 6. RAG Query API (Full RAG pipeline + answer + citations)
    query_payload = {
        "query_text": "What projects and technical skills are listed on the resume?",
        "scope": {
            "org_id": ORG_ID,
            "workspace_id": WORKSPACE_ID,
            "document_ids": [doc_id]
        },
        "top_k": 5
    }
    r = client.post("/api/v1/query", json=query_payload)
    print(f"\n6. POST /api/v1/query -> Status: {r.status_code}")
    print("   Response:", json.dumps(r.json(), indent=2))
    assert r.status_code == 200

    # 7. Extract API (Structured facts extraction)
    extract_payload = {
        "document_id": doc_id,
        "document_version_id": doc_ver_id
    }
    r = client.post("/api/v1/extract", json=extract_payload)
    print(f"\n7. POST /api/v1/extract -> Status: {r.status_code}")
    print("   Response:", json.dumps(r.json(), indent=2))
    assert r.status_code == 200

    # 8. Topics Analysis Trigger
    topics_payload = {
        "org_id": ORG_ID,
        "workspace_id": WORKSPACE_ID,
        "document_ids": [doc_id],
        "num_topics": 3
    }
    r = client.post("/api/v1/topics", json=topics_payload)
    print(f"\n8. POST /api/v1/topics -> Status: {r.status_code}")
    topic_resp = r.json()
    print("   Response:", json.dumps(topic_resp, indent=2))
    assert r.status_code == 200
    topic_job_id = topic_resp["job_id"]

    # 9. Topics Results Retrieval
    r = client.get(f"/api/v1/topics/{topic_job_id}?org_id={ORG_ID}&workspace_id={WORKSPACE_ID}")
    print(f"\n9. GET /api/v1/topics/{topic_job_id} -> Status: {r.status_code}")
    print("   Response:", json.dumps(r.json(), indent=2))
    assert r.status_code == 200

    # 10. Reports Generation Trigger
    report_payload = {
        "org_id": ORG_ID,
        "workspace_id": WORKSPACE_ID,
        "report_type": "EXECUTIVE_SUMMARY",
        "parameters": {"title": "Candidate Profile Report"},
        "output_format": "docx"
    }
    r = client.post("/api/v1/reports/generate", json=report_payload)
    print(f"\n10. POST /api/v1/reports/generate -> Status: {r.status_code}")
    report_resp = r.json()
    print("    Response:", json.dumps(report_resp, indent=2))
    assert r.status_code == 200
    report_job_id = report_resp["job_id"]

    # 11. Reports Draft Retrieval
    r = client.get(f"/api/v1/reports/{report_job_id}?org_id={ORG_ID}&workspace_id={WORKSPACE_ID}")
    print(f"\n11. GET /api/v1/reports/{report_job_id} -> Status: {r.status_code}")
    print("    Response:", json.dumps(r.json(), indent=2))
    assert r.status_code == 200

    # 12. Reports Download
    r = client.get(f"/api/v1/reports/{report_job_id}/download?org_id={ORG_ID}&workspace_id={WORKSPACE_ID}")
    print(f"\n12. GET /api/v1/reports/{report_job_id}/download -> Status: {r.status_code}, Content-Type: {r.headers.get('content-type')}, Length: {len(r.content)} bytes")
    assert r.status_code == 200

    print("\n==================================================")
    print("ALL API ENDPOINTS TESTED SUCCESSFULLY AND WORKING!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
