import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("LLM_API_KEY")

async def test():
    async with httpx.AsyncClient(timeout=15.0) as client:
        for model in ["gemini-2.5-flash", "gemini-3.6-flash", "models/gemini-3.6-flash", "models/gemini-2.5-flash"]:
            # OpenAI-compatible
            r = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": "Respond with 'PONG'"}]}
            )
            print(f"OpenAI-compat [{model}]:", r.status_code, r.text[:200])

asyncio.run(test())
