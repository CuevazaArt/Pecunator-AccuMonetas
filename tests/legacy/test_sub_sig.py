import config, inspect
from binance.client import Client
client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})
print("subscribe_flexible:", inspect.signature(client.subscribe_simple_earn_flexible_product))
print("subscribe_locked:", inspect.signature(client.subscribe_simple_earn_locked_product))
