import config
from binance.client import Client
import json

client = Client(config.api_key, config.api_secret)
try:
    positions = client.get_simple_earn_flexible_product_position(size=5)
    print("Positions:")
    print(json.dumps(positions, indent=2))
except Exception as e:
    print(f"Error: {e}")
