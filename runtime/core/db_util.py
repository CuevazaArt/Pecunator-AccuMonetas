"""Centralised SQLite helper.

Use ``open_db(path)`` instead of ``sqlite3.connect(path)`` everywhere in the
codebase so WAL mode, synchronous=NORMAL, and busy_timeout are set
consistently in a single place.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union


def open_db(path: Union[str, Path], timeout: float = 5.0) -> sqlite3.Connection:
    """Return a ``sqlite3.Connection`` with production-grade defaults.

    Sets:
    * ``PRAGMA journal_mode = WAL``  — concurrent readers don't block writers.
    * ``PRAGMA synchronous = NORMAL`` — durable enough for trading logs,
      ~3× faster than FULL.
    * ``PRAGMA busy_timeout = 5000``  — wait up to 5 s instead of raising
      ``OperationalError: database is locked`` immediately.

    Args:
        path: Path to the ``.sqlite`` file.
        timeout: Python-level connection timeout (seconds).  The WAL
            ``busy_timeout`` is set separately so both layers protect against
            lock contention.

    Returns:
        An open ``sqlite3.Connection``.  The caller must ``close()`` it (or
        use a ``with`` / ``try/finally`` block).
    """
    conn = sqlite3.connect(str(path), timeout=timeout)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn
