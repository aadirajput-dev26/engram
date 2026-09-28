import requests
import json

url = "http://127.0.0.1:8000/api/v1/documents/ingest"
headers = {"X-Api-Key": "a6XbhUYTRn092WEzq45mbASyh1BSCN"}
files = {
    "file": open("C:/Users/Aadityaraj/Downloads/synthetic_mining_report_35_pages.pdf", "rb")
}
data = {
    "org_id": "11111111-1111-1111-1111-111111111111",
    "workspace_id": "22222222-2222-2222-2222-222222222222",
    "uploaded_by_user_id": "33333333-3333-3333-3333-333333333333",
}

print("Uploading document...")
response = requests.post(url, headers=headers, files=files, data=data)
print("Status Code:", response.status_code)
print("Response:", response.text)
