"""PANIC.lock sentinel — Out-of-Band Kill Switch for bot loops.

If the file ``runtime/data/PANIC.lock`` exists, ALL bot loops must halt
immediately and refuse to execute new cycles.  This provides a kill switch
that works even when FastAPI is unresponsive or the event loop is blocked.

Usage in bot ``_loop()``:
    from runtime.bot._panic import check_panic_lock
    if check_panic_lock():
        self._emit("CRITICAL", "PANIC.lock detected — halting bot")
        break

The operator can trigger a panic stop by simply creating the file:
    echo PANIC > runtime/data/PANIC.lock

And resume operations by deleting it.
"""

from __future__ import annotations

import os
from pathlib import Path

# Resolved once at import time; bots check at the start of each cycle.
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_PANIC_PATH = _DATA_DIR / "PANIC.lock"


def check_panic_lock() -> bool:
    """Return True if the PANIC.lock sentinel file exists."""
    try:
        return _PANIC_PATH.exists()
    except OSError:
        # If we can't even check the filesystem, assume panic.
        return True


def panic_lock_path() -> Path:
    """Return the absolute path to the PANIC.lock file (for logging/UI)."""
    return _PANIC_PATH
