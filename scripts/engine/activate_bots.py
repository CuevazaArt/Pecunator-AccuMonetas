"""Activate all 3 bots via the HTTP API after the engine is running.

Usage:
    python scripts/engine/activate_bots.py

Requires the engine to be running on http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"


def _wait_for_api(timeout: int = 60) -> None:
    """Wait until the API is responsive."""
    print("⏳ Waiting for API to be ready...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(f"{BASE}/api/v1/health", timeout=5)
            if r.status_code == 200:
                data = r.json()
                print(f"   ✅ API is up — status={data.get('status','?')}, "
                      f"running={data.get('total_running', 0)} bots")
                return
        except httpx.ConnectError:
            pass  # Server not ready yet
        except Exception as e:
            print(f"   ... waiting ({type(e).__name__})")
        time.sleep(2)
    print("   ❌ API did not respond within timeout.")
    sys.exit(1)


def _create_and_start(hub_path: str, bot_tag: str, config: dict) -> dict:
    """Create a bot instance and start it."""
    # List existing
    try:
        lr = httpx.get(f"{BASE}{hub_path}", timeout=10)
        if lr.status_code == 200:
            data = lr.json()
            bots = data.get("bots", data) if isinstance(data, dict) else data
            if isinstance(bots, list) and bots:
                bot_id = bots[0].get("bot_id")
                print(f"   ♻️  Found existing instance: {bot_id}")
                # Start it
                sr = httpx.post(f"{BASE}{hub_path}/{bot_id}/start", json={}, timeout=15)
                if sr.status_code == 200:
                    print(f"   ✅ {bot_tag} STARTED")
                    return sr.json()
                else:
                    print(f"   ⚠️  Start returned {sr.status_code}: {sr.text[:200]}")
                    return {}
    except Exception as e:
        print(f"   ... list check: {e}")

    # Create new
    payload = {"tag": bot_tag, **config}
    try:
        r = httpx.post(f"{BASE}{hub_path}", json=payload, timeout=10)
    except Exception as e:
        print(f"   ❌ Create failed: {e}")
        return {}

    if r.status_code not in (200, 201):
        print(f"   ❌ Create failed: {r.status_code} — {r.text[:200]}")
        return {}

    data = r.json()
    bot_id = data.get("bot_id", "")
    print(f"   📦 Created {bot_tag}: {bot_id}")

    # Start
    try:
        sr = httpx.post(f"{BASE}{hub_path}/{bot_id}/start", json={}, timeout=15)
        if sr.status_code == 200:
            print(f"   ✅ {bot_tag} STARTED (LIVE)")
            return sr.json()
        else:
            print(f"   ⚠️  Start failed: {sr.status_code} — {sr.text[:200]}")
    except Exception as e:
        print(f"   ⚠️  Start error: {e}")

    return data


def main():
    print("=" * 60)
    print("🤖 BOT ACTIVATION SCRIPT")
    print("=" * 60)

    _wait_for_api()

    print("\n--- Dorothy (XRP DCA) ---")
    _create_and_start(
        "/api/v1/hub/bots",
        "Dorothy-LiveTest",
        {
            "symbol": "XRPUSDT",
            "loop_interval_sec": 450,
            "quote_order_qty": "6",
            "profit_factor": "0.05",
            "margin_drop_factor": "0.03",
            "qty_decimals": 1,
            "price_decimals": 4,
            "stop_loss_pct": "0.15",
            "max_drawdown_pct": "0.20",
            "simulated": False,
            "trading_enabled": True,
        },
    )

    time.sleep(2)

    print("\n--- Masha (BTC DCA) ---")
    _create_and_start(
        "/api/v1/masha/bots",
        "Masha-LiveTest",
        {
            "symbol": "BTCUSDT",
            "loop_interval_sec": 600,
            "simulated": False,
            "trading_enabled": True,
        },
    )

    time.sleep(2)

    print("\n--- Thusnelda (Volatile basket) ---")
    _create_and_start(
        "/api/v1/thusnelda/bots",
        "Thusnelda-LiveTest",
        {
            "symbols_csv": "PEPEUSDT,SUIUSDT",
            "loop_interval_sec": 600,
            "simulated": False,
            "trading_enabled": True,
        },
    )

    print("\n" + "=" * 60)
    print("✅ ALL BOTS ACTIVATED")
    print("   Health:       GET /api/v1/health")
    print("   Dorothy bots: GET /api/v1/hub/bots")
    print("   Masha bots:   GET /api/v1/masha/bots")
    print("   Thusnelda:    GET /api/v1/thusnelda/bots")
    print("   Swagger:      http://127.0.0.1:8000/docs")
    print("=" * 60)


if __name__ == "__main__":
    main()
