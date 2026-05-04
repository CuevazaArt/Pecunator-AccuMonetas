import config
import json
from binance.client import Client

client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})

# Check flexible products for a specific asset
flex = client.get_simple_earn_flexible_product_list(asset="BNB", size=10)
print("=== FLEXIBLE BNB ===")
print(json.dumps(flex, indent=2))

# Check locked products for a specific asset
locked = client.get_simple_earn_locked_product_list(asset="BNB", size=10)
print("\n=== LOCKED BNB ===")
print(json.dumps(locked, indent=2))
