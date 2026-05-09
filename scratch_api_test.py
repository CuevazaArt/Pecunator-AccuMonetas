import asyncio
from runtime.api.app import create_app
from fastapi.testclient import TestClient

app = create_app()

def test():
    with TestClient(app) as client:
        # 1. Create bot
        try:
            client.post("/api/v1/elphaba/bots", json={
                "bot_id": "elphaba-nil",
                "tag": "test",
                "symbol": "BTCUSDT"
            })
        except:
            pass
        
        # 2. Start bot
        resp = client.post("/api/v1/elphaba/bots/elphaba-nil/start", json={
            "api_key": "fake",
            "api_secret": "fake"
        })
        print("Start:", resp.status_code, resp.text)

test()
