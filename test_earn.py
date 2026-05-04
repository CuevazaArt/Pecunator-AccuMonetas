import config
from binance.client import Client

client = Client(config.api_key, config.api_secret)
earn_methods = [m for m in dir(client) if 'earn' in m.lower() or 'redeem' in m.lower() or 'lend' in m.lower()]
print("Earn methods:", earn_methods)
