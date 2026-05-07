import config
from binance.client import Client
import inspect

client = Client(config.api_key, config.api_secret)
sig = inspect.signature(client.redeem_simple_earn_flexible_product)
print("Signature:", sig)
