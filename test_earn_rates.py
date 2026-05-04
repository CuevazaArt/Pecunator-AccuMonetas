import config, json
from binance.client import Client

client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})

STABLES = {"USDT","USDC","BUSD","FDUSD","USDS","DAI","TUSD","USDP","GUSD","FRAX","PYUSD","USDE","CRVUSD"}

print("=== FLEXIBLE EARN - SAMPLE ===")
try:
    res = client.get_simple_earn_flexible_product_list(current=1, size=5)
    print(json.dumps(res, indent=2)[:3000])
except Exception as e:
    print(f"Error: {e}")

print("\n=== LOCKED EARN - SAMPLE ===")
try:
    res = client.get_simple_earn_locked_product_list(current=1, size=3)
    print(json.dumps(res, indent=2)[:3000])
except Exception as e:
    print(f"Error: {e}")
