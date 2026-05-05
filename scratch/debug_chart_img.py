import httpx
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("CHART_IMG_API_KEY")

async def debug_capture():
    url = "https://api.chart-img.com/v1/tradingview/advanced-chart"
    
    # Try different combinations
    combos = [
        {"symbol": "BINANCE:BTCUSDT", "interval": "240"},
        {"symbol": "BTCUSDT", "interval": "240"},
        {"symbol": "BINANCE:BTCUSDT", "interval": "4h"},
        {"symbol": "BTCUSDT", "interval": "4h"},
    ]
    
    async with httpx.AsyncClient() as client:
        for params in combos:
            params.update({"theme": "dark", "width": 800, "height": 600})
            headers = {"x-api-key": api_key}
            print(f"Testing params: {params}")
            resp = await client.get(url, params=params, headers=headers)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print("SUCCESS!")
                return
            else:
                print(f"Body: {resp.text[:200]}")
            print("-" * 20)

if __name__ == "__main__":
    import asyncio
    asyncio.run(debug_capture())
