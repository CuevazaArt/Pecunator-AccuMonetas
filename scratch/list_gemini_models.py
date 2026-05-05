import httpx
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")

async def list_models():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            print("Available models:")
            for m in models:
                if "flash" in m["name"].lower():
                    print(f"  - {m['name']}")
        else:
            print(f"Error: {resp.text}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(list_models())
