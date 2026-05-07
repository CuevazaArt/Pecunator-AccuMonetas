"""Launch Pecunator for a live test with real money.

This script:
1. Validates environment (API keys present)
2. Pre-checks Binance connectivity + wallet balance
3. Displays safety configuration summary
4. Starts the HTTP API (which auto-starts the bots via immortality loop)
5. Streams logs to stdout for real-time monitoring

Usage:
    python scripts/engine/launch_live_test.py
"""

from __future__ import annotations

import os
import sys
import time
from decimal import Decimal
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _check_env() -> dict[str, str]:
    """Validate that all required environment variables are present."""
    required = {
        "PECUNATOR_BINANCE_API_KEY": os.environ.get("PECUNATOR_BINANCE_API_KEY", ""),
        "PECUNATOR_BINANCE_API_SECRET": os.environ.get("PECUNATOR_BINANCE_API_SECRET", ""),
        "DOROTHY_API_KEY": os.environ.get("DOROTHY_API_KEY", ""),
        "DOROTHY_API_SECRET": os.environ.get("DOROTHY_API_SECRET", ""),
        "MASHA_API_KEY": os.environ.get("MASHA_API_KEY", ""),
        "MASHA_API_SECRET": os.environ.get("MASHA_API_SECRET", ""),
        "THUSNELDA_API_KEY": os.environ.get("THUSNELDA_API_KEY", ""),
        "THUSNELDA_API_SECRET": os.environ.get("THUSNELDA_API_SECRET", ""),
    }
    missing = [k for k, v in required.items() if not v.strip()]
    if missing:
        print(f"\n❌ MISSING ENV VARS: {', '.join(missing)}")
        print("   Check your .env file.\n")
        sys.exit(1)
    return required


def _check_binance_connectivity(api_key: str, api_secret: str) -> Decimal:
    """Verify Binance API connectivity and return USDT spot balance."""
    from binance.client import Client
    
    print("\n🔗 Connecting to Binance API...")
    client = Client(api_key, api_secret, requests_params={"timeout": 15})
    
    # Sync time
    server_time = client.get_server_time()
    server_ms = int(server_time.get("serverTime", 0))
    local_ms = int(time.time() * 1000)
    offset = server_ms - local_ms
    client.timestamp_offset = offset
    print(f"   ✅ Server time synced (offset: {offset}ms)")
    
    # Get account
    account = client.get_account()
    balances = account.get("balances", [])
    usdt_free = Decimal("0")
    usdt_locked = Decimal("0")
    non_zero = []
    for b in balances:
        asset = b.get("asset", "")
        free = Decimal(b.get("free", "0"))
        locked = Decimal(b.get("locked", "0"))
        total = free + locked
        if total > 0:
            non_zero.append((asset, free, locked))
        if asset == "USDT":
            usdt_free = free
            usdt_locked = locked
    
    print(f"   ✅ Account verified. USDT: {usdt_free} free, {usdt_locked} locked")
    if non_zero:
        print(f"   📊 Non-zero assets ({len(non_zero)}):")
        for asset, free, locked in sorted(non_zero, key=lambda x: x[0]):
            extra = f" (locked: {locked})" if locked > 0 else ""
            print(f"      {asset}: {free}{extra}")
    
    return usdt_free


def _print_config_summary():
    """Display the safety configuration for the live test."""
    from runtime.bot.dorothy import DorothyConfig
    from runtime.bot.masha import MashaConfig
    from runtime.bot.thusnelda import ThusneldaConfig
    
    dc = DorothyConfig()
    dc.normalize()
    mc = MashaConfig()
    mc.normalize()
    tc = ThusneldaConfig()
    tc.normalize()
    
    max_dorothy = int(dc.max_rungs_per_symbol) * dc.quote_order_qty
    max_masha_approx = Decimal("30")  # Masha uses base_qty, hard to estimate without price
    max_thusnelda = int(tc.max_rungs_per_symbol) * tc.quote_order_qty_modulo * len(tc.symbols())
    
    print("\n" + "=" * 60)
    print("🛡️  SAFETY CONFIGURATION SUMMARY")
    print("=" * 60)
    print(f"\n  Dorothy (XRP DCA):")
    print(f"    Mode:           {'🔴 LIVE' if not dc.simulated else '🟢 SIMULATED'}")
    print(f"    Symbol:         {dc.symbol}")
    print(f"    Quote/rung:     {dc.quote_order_qty} USDT")
    print(f"    Max rungs:      {dc.max_rungs_per_symbol}")
    print(f"    Max exposure:   ~{max_dorothy} USDT")
    print(f"    Profit factor:  {dc.profit_factor} ({float(dc.profit_factor)*100:.1f}%)")
    print(f"    Stop loss:      {dc.stop_loss_pct} ({float(dc.stop_loss_pct)*100:.1f}%)")
    print(f"    Cycle interval: {dc.loop_interval_sec}s")
    
    print(f"\n  Masha (BTC DCA):")
    print(f"    Mode:           {'🔴 LIVE' if not mc.simulated else '🟢 SIMULATED'}")
    print(f"    Symbol:         {mc.symbol}")
    print(f"    Buy qty base:   {mc.buy_qty_base}")
    print(f"    Max rungs:      {mc.max_rungs_per_symbol}")
    print(f"    Profit factor:  {mc.profit_factor} ({float(mc.profit_factor)*100:.1f}%)")
    print(f"    Stop loss:      {mc.stop_loss_pct} ({float(mc.stop_loss_pct)*100:.1f}%)")
    print(f"    Cycle interval: {mc.loop_interval_sec}s")
    
    print(f"\n  Thusnelda (Volatile basket):")
    print(f"    Mode:           {'🔴 LIVE' if not tc.simulated else '🟢 SIMULATED'}")
    print(f"    Symbols:        {','.join(tc.symbols())}")
    print(f"    Quote/rung:     {tc.quote_order_qty_modulo} USDT")
    print(f"    Max rungs/sym:  {tc.max_rungs_per_symbol}")
    print(f"    Max exposure:   ~{max_thusnelda} USDT")
    print(f"    Stop loss:      {tc.stop_loss_pct} ({float(tc.stop_loss_pct)*100:.1f}%)")
    print(f"    Cycle interval: {tc.loop_interval_sec}s")
    
    print(f"\n  Budget Guard:     50 USDT/day hard ceiling")
    print(f"  Regime Filter:    FAIL-CLOSED (BTC>EMA200, ADX, Vol, Macro)")
    print(f"  Cache TTL:        60s (flash-crash responsive)")
    print(f"  Doom button:      DISABLED (pause only, no auto-liquidation)")
    print("=" * 60)


def main():
    print("=" * 60)
    print("🚀 PECUNATOR LIVE TEST LAUNCHER")
    print(f"   Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 1. Check env
    env = _check_env()
    print("✅ All environment variables present")
    
    # 2. Check Binance
    usdt = _check_binance_connectivity(
        env["PECUNATOR_BINANCE_API_KEY"],
        env["PECUNATOR_BINANCE_API_SECRET"],
    )
    
    if usdt < Decimal("10"):
        print(f"\n⚠️  WARNING: USDT balance is very low ({usdt}). Bots may not have enough to operate.")
    
    # 3. Config summary
    _print_config_summary()
    
    # 4. Confirmation
    print("\n⚡ READY TO LAUNCH WITH REAL MONEY ⚡")
    print("   The HTTP API will start on http://127.0.0.1:8000")
    print("   Bots will auto-start via immortality loop.")
    print("   Press Ctrl+C at any time to stop everything.\n")
    
    resp = input("   Type 'GO' to proceed: ").strip().upper()
    if resp != "GO":
        print("   Aborted.")
        sys.exit(0)
    
    print("\n" + "=" * 60)
    print("🟢 LAUNCHING PECUNATOR ENGINE...")
    print("=" * 60 + "\n")
    
    # 5. Start the engine
    from runtime.main import main as engine_main
    engine_main()


if __name__ == "__main__":
    main()
