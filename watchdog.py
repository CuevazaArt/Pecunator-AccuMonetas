"""M4: Process Watchdog — monitors the Pecunator backend and restarts on failure.

Usage:
    python watchdog.py

Polls GET /api/v1/health every 30s. If 3 consecutive checks fail,
kills and relaunches the engine process.
"""

from __future__ import annotations

import os
import sys
import subprocess
import time
import signal

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

HEALTH_URL = "http://127.0.0.1:8000/api/v1/health"
CHECK_INTERVAL_SEC = 30
MAX_FAILURES = 3
PYTHON_EXE = sys.executable
LAUNCH_SCRIPT = os.path.join(ROOT, "launch.py")

def check_health() -> bool:
    """Returns True if the backend is healthy."""
    try:
        import urllib.request
        req = urllib.request.Request(HEALTH_URL, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def kill_port_8000() -> None:
    """Kill any process on port 8000."""
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
                    print(f"   ⚠️  Killing stale PID {pid} on :8000")
                    subprocess.run(["taskkill", "/F", "/PID", pid],
                                   capture_output=True, timeout=5)
                    time.sleep(1)
    except Exception as e:
        print(f"   (port cleanup skipped: {e})")


def launch_engine() -> subprocess.Popen:
    """Start the engine as a subprocess."""
    print(f"\n🚀 Launching engine: {PYTHON_EXE} {LAUNCH_SCRIPT}")
    proc = subprocess.Popen(
        [PYTHON_EXE, LAUNCH_SCRIPT],
        cwd=ROOT,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    # Give it time to boot
    time.sleep(5)
    return proc


def main() -> None:
    print("=" * 60)
    print("🐕 PECUNATOR WATCHDOG")
    print(f"   Health endpoint: {HEALTH_URL}")
    print(f"   Check interval: {CHECK_INTERVAL_SEC}s")
    print(f"   Max failures before restart: {MAX_FAILURES}")
    print("=" * 60)

    proc: subprocess.Popen | None = None
    consecutive_failures = 0

    # Initial launch
    kill_port_8000()
    proc = launch_engine()

    try:
        while True:
            time.sleep(CHECK_INTERVAL_SEC)

            # Check if process is still alive
            if proc and proc.poll() is not None:
                print(f"\n💀 Engine process died (exit code {proc.returncode})")
                consecutive_failures = MAX_FAILURES  # Force restart

            if check_health():
                if consecutive_failures > 0:
                    print(f"   ✅ Health restored (was at {consecutive_failures} failures)")
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                print(f"   ⚠️  Health check failed ({consecutive_failures}/{MAX_FAILURES})")

                if consecutive_failures >= MAX_FAILURES:
                    print(f"\n🔄 RESTARTING ENGINE (failed {consecutive_failures}x)")
                    # Kill existing
                    if proc:
                        try:
                            proc.terminate()
                            proc.wait(timeout=10)
                        except Exception:
                            try:
                                proc.kill()
                            except Exception:
                                pass
                    kill_port_8000()
                    time.sleep(2)
                    proc = launch_engine()
                    consecutive_failures = 0
    except KeyboardInterrupt:
        print("\n🛑 Watchdog stopped by operator")
        if proc:
            proc.terminate()
            proc.wait(timeout=10)


if __name__ == "__main__":
    main()
