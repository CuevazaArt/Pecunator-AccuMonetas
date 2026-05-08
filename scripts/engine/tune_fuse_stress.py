"""Tune all running bots for organic fuse stress test.

1. Eliminates stop_loss from all Dorothy, Masha, and Thusnelda bots.
2. Reduces loop intervals to push weight toward fuse threshold (80% = 4800/6000).
3. Reports final state.

Usage:
    python scripts/engine/tune_fuse_stress.py
"""
from __future__ import annotations
import sys
import time
import httpx

BASE = "http://127.0.0.1:8000"

def main():
    print("=" * 60)
    print("FUSE STRESS TUNING")
    print("  Goal: push API weight to 70-80% organically")
    print("  Stop loss: DISABLED (0) on all bots")
    print("=" * 60)

    # ── Dorothy bots ────────────────────────────────────────────
    print("\n-- Dorothy bots --")
    try:
        r = httpx.get(f"{BASE}/api/v1/hub/bots", timeout=10)
        bots = r.json().get("bots", [])
        print(f"  Found {len(bots)} Dorothy bot(s)")

        # Stagger intervals: 30s to 60s spread across bots
        for i, b in enumerate(bots):
            bid = b["bot_id"]
            tag = b.get("tag", bid)
            # Cycle through 30, 35, 40, 45, 50, 55, 60s
            loop = 30 + (i % 7) * 5
            try:
                httpx.patch(f"{BASE}/api/v1/hub/bots/{bid}", json={
                    "stop_loss_pct": "0",
                    "loop_interval_sec": loop,
                }, timeout=10)
                print(f"  [{tag}] stop_loss=0, loop={loop}s")
            except Exception as e:
                print(f"  [{tag}] PATCH failed: {e}")
    except Exception as e:
        print(f"  Error listing Dorothy: {e}")

    # ── Masha bots ──────────────────────────────────────────────
    print("\n-- Masha bots --")
    try:
        r = httpx.get(f"{BASE}/api/v1/masha/bots", timeout=10)
        bots = r.json().get("bots", [])
        print(f"  Found {len(bots)} Masha bot(s)")

        for i, b in enumerate(bots):
            bid = b["bot_id"]
            tag = b.get("tag", bid)
            loop = 45 + (i % 5) * 5  # 45-65s
            try:
                httpx.patch(f"{BASE}/api/v1/masha/bots/{bid}", json={
                    "stop_loss_pct": "0",
                    "loop_interval_sec": loop,
                }, timeout=10)
                print(f"  [{tag}] stop_loss=0, loop={loop}s")
            except Exception as e:
                print(f"  [{tag}] PATCH failed: {e}")
    except Exception as e:
        print(f"  Error listing Masha: {e}")

    # ── Thusnelda bots ──────────────────────────────────────────
    print("\n-- Thusnelda bots --")
    try:
        r = httpx.get(f"{BASE}/api/v1/thusnelda/bots", timeout=10)
        bots = r.json().get("bots", [])
        print(f"  Found {len(bots)} Thusnelda bot(s)")

        for b in bots:
            bid = b["bot_id"]
            tag = b.get("tag", bid)
            try:
                httpx.patch(f"{BASE}/api/v1/thusnelda/bots/{bid}", json={
                    "stop_loss_pct": "0",
                    "loop_interval_sec": 60,
                }, timeout=10)
                print(f"  [{tag}] stop_loss=0, loop=60s")
            except Exception as e:
                print(f"  [{tag}] PATCH failed: {e}")
    except Exception as e:
        print(f"  Error listing Thusnelda: {e}")

    # ── Weight estimate ─────────────────────────────────────────
    print("\n-- Weight pressure estimate --")
    try:
        r = httpx.get(f"{BASE}/api/v1/hub/bots", timeout=10)
        d_bots = r.json().get("bots", [])
        r2 = httpx.get(f"{BASE}/api/v1/masha/bots", timeout=10)
        m_bots = r2.json().get("bots", [])
        r3 = httpx.get(f"{BASE}/api/v1/thusnelda/bots", timeout=10)
        t_bots = r3.json().get("bots", [])

        total_cycles_per_min = 0.0
        for b in d_bots + m_bots + t_bots:
            loop = b.get("loop_interval_sec", 300)
            if loop > 0:
                total_cycles_per_min += 60.0 / loop

        # Each cycle ~15 weight (get_my_trades=10, ticker=1, etc.)
        weight_per_min = total_cycles_per_min * 15
        # Add gateway overhead (~40 weight/min at 60s poll)
        weight_per_min += 40
        pct = (weight_per_min / 6000) * 100

        print(f"  Total bots: {len(d_bots) + len(m_bots) + len(t_bots)}")
        print(f"  Cycles/min: {total_cycles_per_min:.1f}")
        print(f"  Est. weight/min: {weight_per_min:.0f} / 6000 ({pct:.1f}%)")
        print(f"  Fuse threshold: 80% (4800)")
        if pct >= 80:
            print(f"  --> SHOULD TRIP the fuse organically!")
        elif pct >= 60:
            print(f"  --> Will approach fuse zone, may trip with bursts")
        else:
            print(f"  --> May need more bots or shorter intervals")
    except Exception as e:
        print(f"  Weight estimate failed: {e}")

    print("\n" + "=" * 60)
    print("Tuning complete. Monitor weight oscillator for fuse trip.")
    print("=" * 60)


if __name__ == "__main__":
    main()
