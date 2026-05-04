import config
from binance.client import Client

client = Client(config.api_key, config.api_secret)
info = client.get_exchange_info()
symbols = [s['symbol'] for s in info['symbols']]

print("LDQIUSDT in symbols?", "LDQIUSDT" in symbols)
print("QIUSDT in symbols?", "QIUSDT" in symbols)
