"""Robust launcher that handles port conflicts and old state.

Usage:
    .venv\Scripts\python.exe launch.py
"""

from __future__ import annotations

import os
import sys
import subprocess
import time
import signal

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


def clean_old_hub_dbs():
    """Delete old hub SQLite DBs so bots are created fresh with new config."""
    data_dir = os.path.join(ROOT, "runtime", "data")
    if not os.path.isdir(data_dir):
        return
    count = 0
    for f in os.listdir(data_dir):
        if f.endswith("_hub.sqlite"):
            path = os.path.join(data_dir, f)
            try:
                os.remove(path)
                count += 1
                print(f"   🗑️  Deleted {f}")
            except Exception as e:
                print(f"   ⚠️  Could not delete {f}: {e}")
    if count:
        print(f"   ✅ Cleaned {count} old hub database(s)")
    else:
        print("   ✅ No old hub databases found (clean state)")


def main():
    print("=" * 60)
    print("🚀 PECUNATOR CLEAN LAUNCH")
    print(f"   Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. Kill stale processes on port 8000
    print("\n📋 Step 1: Clearing port 8000...")
    kill_port_8000()

    # 2. Clean old hub databases
    print("\n📋 Step 2: Cleaning old bot state...")
    clean_old_hub_dbs()

    # 3. Launch the engine
    print("\n📋 Step 3: Starting engine...")
    print("   Engine will start on http://127.0.0.1:8000")
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
