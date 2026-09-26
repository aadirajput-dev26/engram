import os
from dotenv import load_dotenv
import litellm

load_dotenv()
api_key = os.getenv("LLM_API_KEY")
os.environ["GEMINI_API_KEY"] = api_key
os.environ["GOOGLE_API_KEY"] = api_key

try:
    response = litellm.completion(
        model="gemini/gemini-3.6-flash",
        messages=[{"role": "user", "content": "Respond with 'LITELLM_GEMINI_OK'"}]
    )
    print("LiteLLM response:", response.choices[0].message.content)
except Exception as e:
    print("LiteLLM error:", e)
