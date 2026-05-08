"""Launch fleet of 31 bots for organic stress testing.

20 Dorothy (trend-following), 10 Masha (DCA), 1 Thusnelda (basket).
Intervals staggered so API weight distributes organically.

Usage:
    python scripts/engine/launch_fleet_31.py
"""
from __future__ import annotations

import sys
import time
import httpx

BASE = "http://127.0.0.1:8000"


def _wait_for_api(timeout: int = 60) -> None:
    print("Waiting for API...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(f"{BASE}/api/v1/health", timeout=5)
            if r.status_code == 200:
                data = r.json()
                print(f"  API up - status={data.get('status','?')}, running={data.get('total_running', 0)} bots")
                return
        except httpx.ConnectError:
            pass
        except Exception as e:
            print(f"  ... waiting ({type(e).__name__})")
        time.sleep(2)
    print("  API did not respond in time.")
    sys.exit(1)


def _create_and_start(path: str, tag: str, config: dict) -> None:
    # Check if exists
    try:
        lr = httpx.get(f"{BASE}{path}", timeout=10)
        if lr.status_code == 200:
            data = lr.json()
            bots = data.get("bots", data) if isinstance(data, dict) else data
            if isinstance(bots, list):
                for b in bots:
                    if isinstance(b, dict) and b.get("tag") == tag:
                        bot_id = b.get("bot_id")
                        # Already exists, just start it
                        sr = httpx.post(f"{BASE}{path}/{bot_id}/start", json={}, timeout=15)
                        status = "STARTED" if sr.status_code == 200 else f"ERR {sr.status_code}"
                        print(f"  [RESUME] {tag} ({bot_id}) -> {status}")
                        return
    except Exception:
        pass

    # Create new
    payload = {"tag": tag, **config}
    try:
        r = httpx.post(f"{BASE}{path}", json=payload, timeout=15)
        if r.status_code not in (200, 201):
            print(f"  [FAIL] {tag}: {r.status_code} - {r.text[:120]}")
            return
        bot_id = r.json().get("bot_id", "")
        sr = httpx.post(f"{BASE}{path}/{bot_id}/start", json={}, timeout=15)
        status = "LIVE" if sr.status_code == 200 else f"START_ERR {sr.status_code}"
        print(f"  [OK] {tag} ({bot_id}) -> {status}")
    except Exception as e:
        print(f"  [ERR] {tag}: {e}")


def main():
    print("=" * 60)
    print("PECUNATOR FLEET LAUNCH - 31 BOTS")
    print("=" * 60)

    _wait_for_api()

    # ── 20 Dorothy instances (trend-following) ──────────────────
    print("\n-- 20x Dorothy (Trend Scalper) --")
    dorothy_configs = [
        ("XRPUSDT",  150), ("ADAUSDT",  180), ("DOTUSDT",  200), ("LINKUSDT", 160),
        ("DOGEUSDT", 140), ("LTCUSDT",  220), ("ATOMUSDT", 200), ("NEARUSDT", 180),
        ("AVAXUSDT", 160), ("UNIUSDT",  240), ("FILUSDT",  200), ("AAVEUSDT", 260),
        ("CRVUSDT",  180), ("SANDUSDT", 200), ("MANAUSDT", 220), ("ENJUSDT",  240),
        ("CHZUSDT",  200), ("GALAUSDT", 180), ("AXSUSDT",  220), ("MATICUSDT",160),
    ]
    for sym, loop in dorothy_configs:
        _create_and_start("/api/v1/hub/bots", f"Dorothy-{sym.replace('USDT','')}", {
            "symbol": sym,
            "loop_interval_sec": loop,
            "quote_order_qty": "8",
            "profit_factor": "0.05",
            "margin_drop_factor": "0.004",
            "stop_loss_pct": "0.10",
            "max_drawdown_pct": "0.20",
            "simulated": False,
            "trading_enabled": True,
        })
        time.sleep(0.3)

    # ── 10 Masha instances (DCA) ───────────────────────────────
    print("\n-- 10x Masha (DCA Accumulation) --")
    masha_configs = [
        ("BTCUSDT",  360), ("ETHUSDT",  360), ("BNBUSDT",  420), ("SOLUSDT",  360),
        ("AVAXUSDT", 420), ("FILUSDT",  480), ("LINKUSDT", 420), ("DOTUSDT",  480),
        ("ATOMUSDT", 480), ("UNIUSDT",  540),
    ]
    for sym, loop in masha_configs:
        _create_and_start("/api/v1/masha/bots", f"Masha-{sym.replace('USDT','')}", {
            "symbol": sym,
            "loop_interval_sec": loop,
            "simulated": False,
            "trading_enabled": True,
        })
        time.sleep(0.3)

    # ── 1 Thusnelda (basket) ──────────────────────────────────
    print("\n-- 1x Thusnelda (Volatile Basket) --")
    _create_and_start("/api/v1/thusnelda/bots", "Thusnelda-Basket", {
        "symbols_csv": "PEPEUSDT,SUIUSDT,NEARUSDT,INJUSDT,FETUSDT",
        "loop_interval_sec": 600,
        "quote_order_qty_modulo": "8",
        "simulated": False,
        "trading_enabled": True,
    })

    # ── Summary ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    try:
        h = httpx.get(f"{BASE}/api/v1/health", timeout=5).json()
        print(f"Fleet Status: {h.get('total_running', '?')} bots running")
        print(f"Weight Zone:  {h.get('weight_zone', '?')}")
    except Exception:
        pass
    print("Target: 60-70% weight utilization for organic fuse testing")
    print("=" * 60)


if __name__ == "__main__":
    main()
