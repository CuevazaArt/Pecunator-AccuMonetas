"""Quick test: compute HA + MA crossover from live Binance klines."""
import requests
from runtime.modules.trend_signal import compute_heikin_ashi, compute_signal

r = requests.get(
    "https://api.binance.com/api/v3/klines",
    params={"symbol": "BTCUSDT", "interval": "1h", "limit": 10},
)
klines = r.json()
print(f"Got {len(klines)} klines")

ha = compute_heikin_ashi(klines)
for i, c in enumerate(ha[-5:]):
    print(f"  HA[{i}] open={c['ha_open']:.2f}  close={c['ha_close']:.2f}")

result = compute_signal(ha)
print(f"\nRESULT:")
print(f"  MA1 (SMA 1, HA open) = {result['ma1']:.2f}")
print(f"  MA2 (SMA 2, HA open) = {result['ma2']:.2f}")
print(f"  Diff = {result['ma1'] - result['ma2']:.4f}")
print(f"  Signal = {result['signal']}")
print(f"  Dorothy should_run = {result['signal'] == 'BULLISH'}")
