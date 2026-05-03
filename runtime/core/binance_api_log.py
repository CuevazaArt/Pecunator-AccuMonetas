"""Append-only log of ALL Binance API interactions (REST + WebSocket) with WAL mode.

This module provides the forensic audit trail for every single interaction
with the Binance API. WAL mode ensures writes are ~0.1ms without blocking reads.

Design principles:
- Every REST call gets logged with latency, weight, and response snippet
- Every WebSocket event gets logged (outboundAccountPosition, executionReport, etc.)
- Low-latency writes via WAL + NORMAL synchronous mode
- Auto-pruning of old records (configurable retention)
"""

from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class BinanceApiLog:
    """Low-latency append-only logger for all Binance API interactions."""

    def __init__(self, db_path: Path, max_records: int = 50_000) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._max_records = max_records
        self._lock = threading.Lock()
        self._write_count = 0
        self._prune_every = 1000  # Prune check every N writes
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        cx = sqlite3.connect(self._path, isolation_level=None)
        cx.execute("PRAGMA journal_mode=WAL")
        cx.execute("PRAGMA synchronous=NORMAL")
        return cx

    def _init_schema(self) -> None:
        with self._conn() as cx:
            cx.execute(
                """
                CREATE TABLE IF NOT EXISTS binance_api_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_utc TEXT NOT NULL,
                    source TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    action TEXT NOT NULL,
                    symbol TEXT,
                    http_status INTEGER,
                    weight_used INTEGER,
                    weight_delta INTEGER,
                    response_size_bytes INTEGER,
                    response_snippet TEXT,
                    error_code INTEGER,
                    error_message TEXT,
                    fuse_tripped INTEGER DEFAULT 0,
                    latency_ms INTEGER
                )
                """
            )
            cx.execute(
                "CREATE INDEX IF NOT EXISTS idx_api_log_ts ON binance_api_log(ts_utc)"
            )
            cx.execute(
                "CREATE INDEX IF NOT EXISTS idx_api_log_source ON binance_api_log(source)"
            )
            cx.execute(
                "CREATE INDEX IF NOT EXISTS idx_api_log_error ON binance_api_log(error_code)"
            )
            cx.commit()

    def _ts_now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def _maybe_prune(self, cx: sqlite3.Connection) -> None:
        self._write_count += 1
        if self._write_count % self._prune_every != 0:
            return
        count = cx.execute("SELECT COUNT(*) FROM binance_api_log").fetchone()[0]
        if count > self._max_records:
            excess = count - self._max_records
            cx.execute(
                "DELETE FROM binance_api_log WHERE id IN "
                "(SELECT id FROM binance_api_log ORDER BY id ASC LIMIT ?)",
                (excess,),
            )

    def log_rest_call(
        self,
        *,
        source: str,
        action: str,
        symbol: str | None = None,
        http_status: int | None = None,
        weight_used: int | None = None,
        weight_delta: int | None = None,
        response_snippet: str | None = None,
        response_size_bytes: int | None = None,
        error_code: int | None = None,
        error_message: str | None = None,
        fuse_tripped: bool = False,
        latency_ms: int | None = None,
    ) -> None:
        """Log an outgoing REST API call and its response."""
        ts = self._ts_now()
        snippet = (response_snippet or "")[:500] or None
        err_msg = (error_message or "")[:500] or None
        with self._lock:
            with self._conn() as cx:
                cx.execute(
                    """
                    INSERT INTO binance_api_log (
                        ts_utc, source, direction, action, symbol,
                        http_status, weight_used, weight_delta,
                        response_size_bytes, response_snippet,
                        error_code, error_message, fuse_tripped, latency_ms
                    ) VALUES (?, ?, 'REST', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts, source[:60], action[:120], symbol,
                        http_status, weight_used, weight_delta,
                        response_size_bytes, snippet,
                        error_code, err_msg, 1 if fuse_tripped else 0, latency_ms,
                    ),
                )
                self._maybe_prune(cx)

    def log_ws_event(
        self,
        *,
        source: str,
        action: str,
        symbol: str | None = None,
        data_snippet: str | None = None,
    ) -> None:
        """Log an incoming WebSocket event."""
        ts = self._ts_now()
        snippet = (data_snippet or "")[:500] or None
        with self._lock:
            with self._conn() as cx:
                cx.execute(
                    """
                    INSERT INTO binance_api_log (
                        ts_utc, source, direction, action, symbol,
                        response_snippet
                    ) VALUES (?, ?, 'WS_IN', ?, ?, ?)
                    """,
                    (ts, source[:60], action[:120], symbol, snippet),
                )
                self._maybe_prune(cx)

    def log_fuse_trip(
        self,
        *,
        source: str,
        reason: str,
        weight_used: int | None = None,
    ) -> None:
        """Log when the API Fuse trips."""
        ts = self._ts_now()
        with self._lock:
            with self._conn() as cx:
                cx.execute(
                    """
                    INSERT INTO binance_api_log (
                        ts_utc, source, direction, action,
                        weight_used, error_message, fuse_tripped
                    ) VALUES (?, ?, 'FUSE', 'fuse_tripped', ?, ?, 1)
                    """,
                    (ts, source[:60], weight_used, reason[:500]),
                )

    # ── Query methods ───────────────────────────────────────────────

    def list_recent(
        self,
        limit: int = 200,
        source: str | None = None,
        errors_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Return recent log entries (newest first)."""
        lim = max(1, min(limit, 5000))
        conditions = []
        params: list[Any] = []
        if source:
            conditions.append("source = ?")
            params.append(source)
        if errors_only:
            conditions.append("error_code IS NOT NULL")
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(lim)
        with self._lock:
            with self._conn() as cx:
                cx.row_factory = sqlite3.Row
                cur = cx.execute(
                    f"""
                    SELECT * FROM binance_api_log
                    {where}
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]

    def weight_summary_last_hour(self) -> dict[str, Any]:
        """Summarize REST weight usage in the last hour."""
        with self._lock:
            with self._conn() as cx:
                cx.row_factory = sqlite3.Row
                cur = cx.execute(
                    """
                    SELECT
                        COUNT(*) AS total_calls,
                        SUM(CASE WHEN direction = 'REST' THEN 1 ELSE 0 END) AS rest_calls,
                        SUM(CASE WHEN direction = 'WS_IN' THEN 1 ELSE 0 END) AS ws_events,
                        MAX(weight_used) AS max_weight_seen,
                        SUM(CASE WHEN error_code IS NOT NULL THEN 1 ELSE 0 END) AS errors,
                        SUM(CASE WHEN fuse_tripped = 1 THEN 1 ELSE 0 END) AS fuse_trips,
                        AVG(latency_ms) AS avg_latency_ms
                    FROM binance_api_log
                    WHERE ts_utc >= datetime('now', '-1 hour')
                    """
                )
                row = cur.fetchone()
                return dict(row) if row else {}

    def db_stats(self) -> dict[str, Any]:
        """Return DB file size and record counts."""
        size = self._path.stat().st_size if self._path.is_file() else 0
        with self._lock:
            with self._conn() as cx:
                total = cx.execute("SELECT COUNT(*) FROM binance_api_log").fetchone()[0]
                rest = cx.execute(
                    "SELECT COUNT(*) FROM binance_api_log WHERE direction = 'REST'"
                ).fetchone()[0]
                ws = cx.execute(
                    "SELECT COUNT(*) FROM binance_api_log WHERE direction = 'WS_IN'"
                ).fetchone()[0]
                errors = cx.execute(
                    "SELECT COUNT(*) FROM binance_api_log WHERE error_code IS NOT NULL"
                ).fetchone()[0]
                fuse = cx.execute(
                    "SELECT COUNT(*) FROM binance_api_log WHERE fuse_tripped = 1"
                ).fetchone()[0]
        return {
            "db_size_bytes": size,
            "db_size_mb": round(size / 1_048_576, 2),
            "total_records": total,
            "rest_calls": rest,
            "ws_events": ws,
            "errors": errors,
            "fuse_trips": fuse,
        }


# ── Singleton ───────────────────────────────────────────────────────

_log: Optional[BinanceApiLog] = None


def get_binance_api_log(data_dir: Path) -> BinanceApiLog:
    """Get or create the global BinanceApiLog singleton."""
    global _log
    if _log is None:
        _log = BinanceApiLog(Path(data_dir) / "binance_api_log.sqlite")
    return _log
