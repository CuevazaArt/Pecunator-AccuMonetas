"""Resilient launcher — resumes bots instead of wiping state.

Unlike launch.py (clean launch), this preserves hub SQLite databases
so bots resume their configurations and continue watching their
open Binance orders after a crash or restart.

Usage:
    .venv\Scripts\python.exe launch_resume.py
"""

from __future__ import annotations

import os
import sys
import subprocess
import time

# Fix Windows console encoding for emoji/unicode
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)


def kill_port_8000():
    """Kill any process holding port 8000 on Windows."""
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if ":8000" in line and "LISTENING" in line:
                parts = line.strip().split()
                pid = parts[-1]
                if pid.isdigit() and int(pid) > 0:
                    print(f"   ⚠️  Killing old process on port 8000 (PID {pid})")
                    subprocess.run(["taskkill", "/F", "/PID", pid],
                                   capture_output=True, timeout=5)
                    time.sleep(1)
    except Exception as e:
        print(f"   (port cleanup skipped: {e})")


def check_hub_dbs():
    """Report existing hub SQLite databases (we preserve them)."""
    data_dir = os.path.join(ROOT, "runtime", "data")
    if not os.path.isdir(data_dir):
        print("   ⚠️  No data directory found — fresh start")
        return
    found = []
    for f in os.listdir(data_dir):
        if f.endswith("_hub.sqlite"):
            path = os.path.join(data_dir, f)
            size_kb = os.path.getsize(path) / 1024
            found.append((f, size_kb))
    if found:
        for f, sz in found:
            print(f"   ✅ Preserving {f} ({sz:.0f} KB)")
        print(f"   📦 {len(found)} hub database(s) will be resumed")
    else:
        print("   📋 No hub databases found — bots will need to be created")


def main():
    print("=" * 60)
    print("🔄 PECUNATOR RESUME LAUNCH")
    print(f"   Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("   Mode: RESUME (preserving bot state)")
    print("=" * 60)

    # 1. Kill stale processes on port 8000
    print("\n📋 Step 1: Clearing port 8000...")
    kill_port_8000()

    # 2. Check (but DON'T delete) hub databases
    print("\n📋 Step 2: Checking existing bot state...")
    check_hub_dbs()

    # 3. Launch the engine
    print("\n📋 Step 3: Starting engine...")
    print("   Engine will start on http://127.0.0.1:8000")
    print("   Bots with desired_running=True will auto-resume via immortality loop")
    print("   Press Ctrl+C to stop everything.\n")
    print("=" * 60)

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    from runtime.main import main as engine_main
    engine_main()


if __name__ == "__main__":
    main()
