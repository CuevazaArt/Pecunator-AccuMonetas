"""Weight Stress v5 — REAL OSCILLATION via silence windows.

Key insight: X-MBX-USED-WEIGHT-1M is a rolling 1-min window.
Old requests fall off after 60s. To create oscillation:
1. BURST heavily for 10-15s (weight shoots UP)
2. TOTAL SILENCE for 25-35s (weight DECAYS as old requests expire)
3. One probe call to read the new lower header → inject to engine
4. Repeat → visible sawtooth/oscillation on Flutter chart

Usage:
    .venv\Scripts\python.exe scripts\engine\stress_weight.py --pattern wave
    .venv\Scripts\python.exe scripts\engine\stress_weight.py --pattern pulse
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import httpx

BASE = "http://127.0.0.1:8000"
WEIGHT_LIMIT = 6000

SYMBOLS = ["XRPUSDT", "BTCUSDT", "PEPEUSDT", "SUIUSDT", "ETHUSDT", "SOLUSDT",
           "ADAUSDT", "DOTUSDT", "LINKUSDT", "AVAXUSDT"]

_real_weight = 0
_weight_lock = __import__('threading').Lock()


def _read_weight(client) -> int:
    global _real_weight
    try:
        resp = getattr(client, 'response', None)
        if resp and hasattr(resp, 'headers'):
            w = resp.headers.get('x-mbx-used-weight-1m') or resp.headers.get('X-MBX-USED-WEIGHT-1M')
            if w:
                val = int(w)
                with _weight_lock:
                    _real_weight = val
                return val
    except Exception:
        pass
    with _weight_lock:
        return _real_weight


def _inject(weight: int) -> dict:
    try:
        r = httpx.post(f"{BASE}/api/v1/weight-governor/inject",
                       json={"weight": weight}, timeout=2)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def _probe(client) -> int:
    """Make ONE tiny call just to read the current weight header."""
    client.get_server_time()  # weight 1
    w = _read_weight(client)
    if w > 0:
        _inject(w)
    return w


def _fuse_status() -> dict:
    try:
        r = httpx.get(f"{BASE}/api-fuse/status", timeout=2)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


def _heavy_call(client, i: int) -> int:
    sym = SYMBOLS[i % len(SYMBOLS)]
    try:
        v = i % 5
        if v == 0:
            client.get_all_tickers(); return 40
        elif v == 1:
            client.get_klines(symbol=sym, interval="1m", limit=500); return 10
        elif v == 2:
            client.get_order_book(symbol=sym, limit=100); return 10
        elif v == 3:
            client.get_klines(symbol=sym, interval="5m", limit=1000); return 20
        else:
            client.get_order_book(symbol=sym, limit=500); return 50
    except Exception:
        return 0


def _burst(client, n: int, threads: int) -> int:
    total = 0
    with ThreadPoolExecutor(max_workers=threads) as pool:
        futs = [pool.submit(_heavy_call, client, i) for i in range(n)]
        for f in as_completed(futs):
            total += f.result()
    w = _read_weight(client)
    if w > 0:
        _inject(w)
    return total


def _log(label, w, detail=""):
    pct = w / WEIGHT_LIMIT * 100
    icon = "⛔" if pct >= 95 else "🔴" if pct >= 80 else "🟡" if pct >= 60 else "🟢"
    bar_len = int(pct / 2)
    bar = "█" * bar_len + "░" * (50 - bar_len)
    print(f"  {time.strftime('%H:%M:%S')} {label:6s} {icon} {pct:5.1f}% [{bar}] {w:>5d} {detail}")


# ── Patterns ────────────────────────────────────────────────────────

def run_wave(client, threads, duration):
    """WAVE: 12s burst → 30s silence → probe → repeat.
    Creates clear sawtooth: weight shoots up, then decays over silence.
    """
    print("\n🌊 WAVE — 10s heavy burst, 5s silence, probe, repeat")
    print("   Expect: ↗️ shoot up during burst, ↘️ decay during silence\n")
    start = time.time()
    cycle = 0

    while time.time() - start < duration:
        cycle += 1
        print(f"  ── Cycle {cycle} ──")

        # BURST PHASE: 12 seconds of heavy calls
        burst_start = time.time()
        while time.time() - burst_start < 12:
            if time.time() - start >= duration: return
            n = random.randint(10, 25)
            _burst(client, n, threads)
            w = _read_weight(client)
            _log("BURST", w, f"[{n} heavy]")
            # Check fuse
            fuse = _fuse_status()
            if fuse.get("tripped"):
                print(f"  🚨 FUSE TRIPPED! Cooldown: {fuse.get('remaining_cooldown_sec',0):.0f}s")
                _watch_recovery()
                break
            time.sleep(0.3)

        # SILENCE PHASE: 5 seconds
        print(f"  {time.strftime('%H:%M:%S')} ────── SILENCE 5s ──────")
        silence_end = time.time() + 5
        while time.time() < silence_end:
            if time.time() - start >= duration: return
            time.sleep(2.5)
            # ONE tiny call to read the decayed weight
            w = _probe(client)
            _log("DECAY", w, "[probe]")


def run_pulse(client, threads, duration):
    """PULSE: short sharp spikes with short gaps.
    5s MASSIVE burst → 5s silence → repeat.
    Goal: push as high as possible, then watch brief decay.
    """
    print("\n💓 PULSE — 5s massive spike, 5s silence, repeat")
    print("   Goal: spike high then brief decay\n")
    start = time.time()
    cycle = 0

    while time.time() - start < duration:
        cycle += 1
        print(f"  ── Pulse {cycle} ──")

        # SPIKE: 5 seconds of maximum intensity
        spike_start = time.time()
        while time.time() - spike_start < 5:
            if time.time() - start >= duration: return
            n = random.randint(30, 60)  # Massive: 30-60 heavy calls
            _burst(client, n, threads)
            w = _read_weight(client)
            _log("SPIKE", w, f"[{n} HEAVY!]")
            fuse = _fuse_status()
            if fuse.get("tripped"):
                print(f"  🚨 FUSE TRIPPED at {w}! ({w/WEIGHT_LIMIT*100:.1f}%)")
                print(f"     Cooldown: {fuse.get('remaining_cooldown_sec',0):.0f}s "
                      f"Streak: {fuse.get('consecutive_streak',0)}")
                _watch_recovery()
                break
            time.sleep(0.1)

        # SHORT SILENCE: 5 seconds
        print(f"  {time.strftime('%H:%M:%S')} ────── SILENCE 5s ──────")
        silence_end = time.time() + 5
        while time.time() < silence_end:
            if time.time() - start >= duration: return
            time.sleep(5)
            w = _probe(client)
            _log("DECAY", w, "[probe]")


def run_heartbeat(client, threads, duration):
    """HEARTBEAT: alternating intensity — heavy/light/heavy/light.
    Creates a rhythmic oscillation pattern.
    """
    print("\n❤️ HEARTBEAT — 8s heavy, 5s silence, 5s light, 5s silence")
    print("   Creates a rhythmic double-beat oscillation\n")
    start = time.time()
    cycle = 0

    while time.time() - start < duration:
        cycle += 1
        print(f"  ── Beat {cycle} ──")

        # STRONG BEAT: 8s heavy
        beat_start = time.time()
        while time.time() - beat_start < 8:
            if time.time() - start >= duration: return
            n = random.randint(15, 30)
            _burst(client, n, threads)
            w = _read_weight(client)
            _log("STRONG", w, f"[{n} heavy]")
            fuse = _fuse_status()
            if fuse.get("tripped"):
                print(f"  🚨 FUSE!")
                _watch_recovery()
                break
            time.sleep(0.3)

        # PAUSE
        print(f"  {time.strftime('%H:%M:%S')} ── pause 5s ──")
        time.sleep(5)
        w = _probe(client)
        _log("REST", w, "[probe]")

        # WEAK BEAT: lighter burst
        beat_start = time.time()
        while time.time() - beat_start < 5:
            if time.time() - start >= duration: return
            n = random.randint(5, 10)
            _burst(client, n, threads)
            w = _read_weight(client)
            _log("WEAK", w, f"[{n} light-heavy]")
            time.sleep(0.5)

        # SHORT PAUSE
        print(f"  {time.strftime('%H:%M:%S')} ── rest 5s ──")
        time.sleep(5)
        w = _probe(client)
        _log("REST", w, "[probe]")


def _watch_recovery():
    print(f"  ⏳ Watching fuse recovery...")
    for _ in range(40):
        time.sleep(3)
        fuse = _fuse_status()
        remaining = fuse.get("remaining_cooldown_sec", 0)
        tripped = fuse.get("tripped", False)
        print(f"  {time.strftime('%H:%M:%S')} FUSED  🔴 remaining={remaining:.0f}s "
              f"streak={fuse.get('consecutive_streak',0)}")
        if not tripped:
            print(f"  ✅ FUSE RECOVERED — resuming")
            return


# ── Main ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern", choices=["wave", "pulse", "heartbeat"],
                        default="wave")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--duration", type=int, default=600)
    args = parser.parse_args()

    print("=" * 65)
    print(f"⚡ WEIGHT STRESS v5 — REAL OSCILLATION")
    print(f"   Pattern: {args.pattern.upper()}")
    print(f"   Threads: {args.threads} | Duration: {args.duration}s")
    print(f"   Key: silence windows let the rolling 1-min weight DECAY")
    print(f"   Fuse threshold: 80% ({int(WEIGHT_LIMIT*0.8)})")
    print("=" * 65)

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(project_root, ".env"))
    except ImportError:
        pass

    api_key = os.environ.get("PECUNATOR_BINANCE_API_KEY", "") or os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("PECUNATOR_BINANCE_API_SECRET", "") or os.environ.get("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        print("❌ No API keys"); sys.exit(1)

    from binance.client import Client
    client = Client(api_key, api_secret)
    w = _probe(client)
    print(f"✅ Connected — weight: {w}/{WEIGHT_LIMIT} ({w/WEIGHT_LIMIT*100:.1f}%)")

    try:
        {"wave": run_wave, "pulse": run_pulse, "heartbeat": run_heartbeat}[args.pattern](
            client, args.threads, args.duration)
    except KeyboardInterrupt:
        print("\n⏹ Stopped.")

    w = _probe(client)
    fuse = _fuse_status()
    print(f"\n{'='*65}")
    print(f"📊 FINAL: {w}/{WEIGHT_LIMIT} ({w/WEIGHT_LIMIT*100:.1f}%)")
    print(f"   Fuse: tripped={fuse.get('tripped','?')} "
          f"trips={fuse.get('trip_count',0)} streak={fuse.get('consecutive_streak',0)}")
    print(f"{'='*65}")


if __name__ == "__main__":
    main()
