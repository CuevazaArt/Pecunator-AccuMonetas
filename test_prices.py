import config
from binance.client import Client

client = Client(config.api_key, config.api_secret)
tickers = client.get_all_tickers()
prices = {t["symbol"]: float(t["price"]) for t in tickers}

print("BTCUSDT:", prices.get("BTCUSDT"))
print("LDGNS USDT price:", prices.get("GNSUSDT"))
