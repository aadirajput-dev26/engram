import asyncio
import time
import httpx
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("LLM_API_KEY")
url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

async def test_model(model_name):
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": "Hello, reply with 1 word"}],
                    "max_tokens": 10
                }
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            print(f"{model_name}: status {resp.status_code} in {time.time()-t0:.2f}s, text={repr(content)}")
    except Exception as e:
        print(f"{model_name} failed in {time.time()-t0:.2f}s: {e}")

async def main():
    for m in ["gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"]:
        await test_model(m)

asyncio.run(main())
