"""ToxicSymbolRegistry — Persistent blacklist of symbols that failed margin operations.

When a symbol repeatedly fails with borrowing/liquidity errors, it gets
flagged as "toxic" and excluded from future Prospector scans and bot
deployments.  This prevents the system from recycling symbols that
Binance cannot service.

Lifecycle:
  1. SymmetryGuard detects per-symbol pause exhaustion → calls `blacklist()`
  2. Prospector reads `is_blacklisted()` during scan → skips symbol
  3. Operator can manually `whitelist()` a symbol if conditions change

Storage: SQLite in runtime/data/toxic_symbols.sqlite
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from runtime.core.db_util import open_db

_LOG = logging.getLogger("pecunator.core.toxic_symbols")

_DDL = """\
CREATE TABLE IF NOT EXISTS toxic_symbols (
    symbol          TEXT    PRIMARY KEY,
    reason          TEXT    NOT NULL DEFAULT '',
    error_code      TEXT    NOT NULL DEFAULT '',
    blacklisted_at  TEXT    NOT NULL,
    hit_count       INTEGER NOT NULL DEFAULT 1,
    resolved        INTEGER NOT NULL DEFAULT 0,
    resolved_at     TEXT    NOT NULL DEFAULT '',
    notes           TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_toxic_active
    ON toxic_symbols(resolved);
"""


class ToxicSymbolRegistry:
    """Persistent blacklist of symbols that fail margin/borrow operations."""

    def __init__(self, db_path: Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: set[str] = set()  # In-memory hot cache
        self._init_schema()

    def _init_schema(self) -> None:
        conn = open_db(self._path)
        try:
            conn.executescript(_DDL)
            rows = conn.execute(
                "SELECT symbol FROM toxic_symbols WHERE resolved = 0"
            ).fetchall()
            self._cache = {r[0].upper() for r in rows}
            if self._cache:
                _LOG.info(
                    "ToxicSymbolRegistry: loaded %d blacklisted symbols: %s",
                    len(self._cache), ", ".join(sorted(self._cache)),
                )
        finally:
            conn.close()

    def blacklist(
        self,
        symbol: str,
        reason: str = "",
        error_code: str = "",
    ) -> bool:
        """Add a symbol to the toxic blacklist.

        Returns True if the symbol was newly blacklisted (not already there).
        If already blacklisted, increments hit_count.
        """
        sym = symbol.upper()
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = open_db(self._path)
            try:
                if sym in self._cache:
                    # Already blacklisted — increment hit count
                    conn.execute(
                        "UPDATE toxic_symbols SET hit_count = hit_count + 1 "
                        "WHERE symbol = ? AND resolved = 0",
                        (sym,),
                    )
                    conn.commit()
                    _LOG.warning(
                        "ToxicSymbol: %s hit again (already blacklisted). Reason: %s",
                        sym, reason[:100],
                    )
                    return False
                else:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO toxic_symbols
                            (symbol, reason, error_code, blacklisted_at,
                             hit_count, resolved, resolved_at, notes)
                        VALUES (?, ?, ?, ?, 1, 0, '', '')
                        """,
                        (sym, reason[:300], error_code[:20], now),
                    )
                    conn.commit()
                    self._cache.add(sym)
                    _LOG.critical(
                        "ToxicSymbol: BLACKLISTED %s — %s (code=%s)",
                        sym, reason[:100], error_code,
                    )
                    return True
            finally:
                conn.close()

    def whitelist(self, symbol: str, notes: str = "") -> bool:
        """Remove a symbol from the blacklist (operator override).

        Returns True if the symbol was found and whitelisted.
        """
        sym = symbol.upper()
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = open_db(self._path)
            try:
                cur = conn.execute(
                    "UPDATE toxic_symbols SET resolved = 1, resolved_at = ?, "
                    "notes = ? WHERE symbol = ? AND resolved = 0",
                    (now, notes[:300], sym),
                )
                conn.commit()
                self._cache.discard(sym)
                if cur.rowcount > 0:
                    _LOG.info("ToxicSymbol: WHITELISTED %s — %s", sym, notes[:60])
                    return True
                return False
            finally:
                conn.close()

    def is_blacklisted(self, symbol: str) -> bool:
        """Fast in-memory check if a symbol is currently blacklisted."""
        return symbol.upper() in self._cache

    def get_blacklist(self) -> list[dict[str, Any]]:
        """Return all currently blacklisted symbols with metadata."""
        conn = open_db(self._path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM toxic_symbols WHERE resolved = 0 "
                "ORDER BY blacklisted_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return full history including resolved (whitelisted) symbols."""
        conn = open_db(self._path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM toxic_symbols ORDER BY blacklisted_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def filter_symbols(self, symbols: list[str]) -> list[str]:
        """Return only non-blacklisted symbols from the input list."""
        return [s for s in symbols if s.upper() not in self._cache]


# ── Singleton ───────────────────────────────────────────────────────

_instance: Optional[ToxicSymbolRegistry] = None


def get_toxic_registry(data_dir: Optional[Path] = None) -> ToxicSymbolRegistry:
    global _instance
    if _instance is None:
        d = data_dir or Path("runtime/data")
        _instance = ToxicSymbolRegistry(Path(d) / "toxic_symbols.sqlite")
    return _instance
