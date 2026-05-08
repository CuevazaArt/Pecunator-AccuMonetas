"""Test dual-gate trend signal from live Binance data."""
import requests
from runtime.modules.trend_signal import (
    compute_heikin_ashi,
    compute_trend,
    compute_entry_gate,
)

# ── Fetch real 1h klines ────────────────────────────────────────────
r = requests.get(
    "https://api.binance.com/api/v3/klines",
    params={"symbol": "BTCUSDT", "interval": "1h", "limit": 10},
)
klines = r.json()
print(f"Got {len(klines)} klines")

# ── Gate 1: Trend (Heikin Ashi) ─────────────────────────────────────
ha = compute_heikin_ashi(klines)
for i, c in enumerate(ha[-3:]):
    idx = len(ha) - 3 + i
    print(f"  HA[{idx}] open={c['ha_open']:.2f}  close={c['ha_close']:.2f}")

trend = compute_trend(ha)
print(f"\nGATE 1 — TREND:")
print(f"  MA1 (SMA 1, HA open)  = {trend['ma1']:.2f}")
print(f"  MA2 (SMA 2, HA open)  = {trend['ma2']:.2f}")
print(f"  Diff                  = {trend['ma1'] - trend['ma2']:.4f}")
print(f"  Signal                = {trend['signal']}")

# ── Gate 2: Entry (regular candle) ──────────────────────────────────
# Current 1h candle open = last kline open (regular, not HA)
candle_open = float(klines[-1][1])
# Current price from ticker
r2 = requests.get(
    "https://api.binance.com/api/v3/ticker/price",
    params={"symbol": "BTCUSDT"},
)
current_price = float(r2.json()["price"])

entry = compute_entry_gate(current_price, candle_open)
print(f"\nGATE 2 — ENTRY:")
print(f"  Current price         = {entry['current_price']:.2f}")
print(f"  1h candle open (reg)  = {entry['candle_open']:.2f}")
print(f"  Diff                  = {entry['diff']:.2f} ({entry['diff_pct']:.4f}%)")
print(f"  Gate                  = {entry['gate']}")

# ── Combined ────────────────────────────────────────────────────────
should_run = trend["signal"] == "BULLISH" and entry["gate"] == "CLEAR"
print(f"\n{'='*50}")
print(f"  TREND  = {trend['signal']}")
print(f"  ENTRY  = {entry['gate']}")
print(f"  DOROTHY should_run = {should_run}")
print(f"{'='*50}")
