import config, json
from binance.client import Client

client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})

# Get trade history for a specific asset to see purchase data
trades = client.get_my_trades(symbol="HBARUSDT", limit=5)
print("=== HBAR Trades ===")
print(json.dumps(trades, indent=2))

# Also check if there's a way to get klines for momentum detection
klines = client.get_klines(symbol="HBARUSDT", interval="1h", limit=3)
print("\n=== HBAR Klines (1h) ===")
for k in klines:
    print(f"  Open: {k[1]}, High: {k[2]}, Low: {k[3]}, Close: {k[4]}, Volume: {k[5]}")
