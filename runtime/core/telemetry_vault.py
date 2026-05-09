"""Telemetry Vault — Unified historical data store for all Pecunator telemetry.

Centralizes storage of:
  - Kline (candlestick) history for backtesting and statistical analysis
  - Capture index (PNG metadata, not BLOBs) for VMO image tracking
  - Bot decision log (every decision made or rejected, with reasoning)

Policy: "We already paid for the data — use it to the maximum."
Purge mechanism: configurable retention per table, post-analysis.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from runtime.core.db_util import open_db
from runtime.core.exception_zoo import get_exception_zoo

_LOG = logging.getLogger("pecunator.core.telemetry_vault")

_DDL = """\
-- Kline (candlestick) history
CREATE TABLE IF NOT EXISTS kline_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT    NOT NULL,
    interval    TEXT    NOT NULL,
    open_time   INTEGER NOT NULL,
    open        TEXT    NOT NULL,
    high        TEXT    NOT NULL,
    low         TEXT    NOT NULL,
    close       TEXT    NOT NULL,
    volume      TEXT    NOT NULL,
    close_time  INTEGER NOT NULL,
    quote_vol   TEXT    NOT NULL DEFAULT '0',
    trades      INTEGER NOT NULL DEFAULT 0,
    ingested_utc TEXT   NOT NULL,
    UNIQUE(symbol, interval, open_time)
);
CREATE INDEX IF NOT EXISTS idx_kline_sym_int
    ON kline_history(symbol, interval, open_time DESC);

-- VMO capture index (metadata only, PNG stored on disk)
CREATE TABLE IF NOT EXISTS capture_index (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT    NOT NULL,
    timeframe       TEXT    NOT NULL,
    captured_at_utc TEXT    NOT NULL,
    file_path       TEXT    NOT NULL,
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    source          TEXT    NOT NULL DEFAULT '',
    indicators      TEXT    NOT NULL DEFAULT '',
    regime_id       INTEGER,
    regime          TEXT    NOT NULL DEFAULT '',
    confidence      REAL    NOT NULL DEFAULT 0.0,
    recommended_bot TEXT    NOT NULL DEFAULT '',
    UNIQUE(symbol, timeframe, captured_at_utc)
);
CREATE INDEX IF NOT EXISTS idx_capture_sym
    ON capture_index(symbol, timeframe, captured_at_utc DESC);

-- Bot decision log
CREATE TABLE IF NOT EXISTS bot_decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc          TEXT    NOT NULL,
    bot_id          TEXT    NOT NULL,
    bot_type        TEXT    NOT NULL,
    symbol          TEXT    NOT NULL DEFAULT '',
    decision        TEXT    NOT NULL,
    action_taken    INTEGER NOT NULL DEFAULT 0,
    reason          TEXT    NOT NULL DEFAULT '',
    regime_at_time  TEXT    NOT NULL DEFAULT '',
    equity_usdt     TEXT    NOT NULL DEFAULT '0',
    pnl_usdt        TEXT    NOT NULL DEFAULT '0',
    blocked_by      TEXT    NOT NULL DEFAULT '',
    context_json    TEXT    NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_botdec_ts
    ON bot_decisions(ts_utc DESC);
CREATE INDEX IF NOT EXISTS idx_botdec_bot
    ON bot_decisions(bot_id, ts_utc DESC);

-- Prospector scans
CREATE TABLE IF NOT EXISTS prospector_scans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc          TEXT    NOT NULL,
    symbol          TEXT    NOT NULL,
    evi_score       REAL    NOT NULL,
    grade           TEXT    NOT NULL,
    adx             REAL    NOT NULL,
    choppiness      REAL    NOT NULL,
    avg_speed       REAL    NOT NULL,
    freq_extreme    REAL    NOT NULL,
    kurtosis        REAL    NOT NULL,
    margin_eligible INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_prospector_ts
    ON prospector_scans(ts_utc DESC);
"""


class TelemetryVault:
    """Unified historical data store."""

    def __init__(self, db_path: Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        conn = open_db(self._path)
        try:
            conn.executescript(_DDL)
        finally:
            conn.close()

    # ── Kline History ───────────────────────────────────────────────

    def store_klines(
        self, symbol: str, interval: str, klines: list[list]
    ) -> int:
        """Store raw klines from Binance. Returns rows inserted."""
        if not klines:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        rows = []
        for k in klines:
            try:
                rows.append((
                    symbol, interval,
                    int(k[0]),       # open_time
                    str(k[1]),       # open
                    str(k[2]),       # high
                    str(k[3]),       # low
                    str(k[4]),       # close
                    str(k[5]),       # volume
                    int(k[6]),       # close_time
                    str(k[7]),       # quote_volume
                    int(k[8]),       # trades
                    now,
                ))
            except (IndexError, ValueError, TypeError) as exc:
                zoo = get_exception_zoo()
                zoo.register(exc, module="telemetry_vault", context=f"kline_parse:{symbol}")
                continue

        if not rows:
            return 0

        with self._lock:
            conn = open_db(self._path)
            try:
                cur = conn.executemany(
                    """
                    INSERT OR IGNORE INTO kline_history
                        (symbol, interval, open_time, open, high, low, close,
                         volume, close_time, quote_vol, trades, ingested_utc)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                conn.commit()
                return cur.rowcount
            except Exception as exc:
                zoo = get_exception_zoo()
                zoo.register(exc, module="telemetry_vault", context=f"store_klines:{symbol}")
                return 0
            finally:
                conn.close()

    def get_klines(
        self, symbol: str, interval: str, limit: int = 500
    ) -> list[dict[str, Any]]:
        """Retrieve stored klines (newest first)."""
        conn = open_db(self._path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM kline_history
                WHERE symbol = ? AND interval = ?
                ORDER BY open_time DESC LIMIT ?
                """,
                (symbol, interval, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def kline_coverage(self) -> list[dict[str, Any]]:
        """Summary of kline data per symbol/interval."""
        conn = open_db(self._path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT symbol, interval,
                       COUNT(*) as candles,
                       MIN(open_time) as first_ts,
                       MAX(open_time) as last_ts
                FROM kline_history
                GROUP BY symbol, interval
                ORDER BY symbol, interval
                """
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def compute_oscillation_pct(
        self, symbol: str, interval: str = "4h", num_candles: int = 30
    ) -> float:
        """Compute average price oscillation range for a symbol.

        Calculates mean((high - low) / close) * 100 over the most recent
        ``num_candles`` stored candles. This represents the natural swing
        range of the asset — the input to the adaptive profit formula in
        :class:`AutoTuner`.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").
            interval: Candle timeframe (e.g. "4h", "1d").
            num_candles: Number of recent candles to average over.

        Returns:
            Oscillation percentage (e.g. 5.2 means ~5.2% average range).
            Returns 0.0 if insufficient data.
        """
        conn = open_db(self._path)
        try:
            rows = conn.execute(
                """
                SELECT high, low, close FROM kline_history
                WHERE symbol = ? AND interval = ?
                ORDER BY open_time DESC LIMIT ?
                """,
                (symbol, interval, num_candles),
            ).fetchall()
            if len(rows) < 3:
                return 0.0
            total = 0.0
            valid = 0
            for row in rows:
                try:
                    h = float(row[0])
                    l = float(row[1])
                    c = float(row[2])
                    if c > 0:
                        total += ((h - l) / c) * 100.0
                        valid += 1
                except (ValueError, TypeError, ZeroDivisionError):
                    continue
            return round(total / valid, 2) if valid > 0 else 0.0
        finally:
            conn.close()

    # ── Capture Index ───────────────────────────────────────────────

    def index_capture(
        self,
        symbol: str,
        timeframe: str,
        captured_at: str,
        file_path: str,
        file_size: int = 0,
        source: str = "",
        indicators: str = "",
        regime: str = "",
        confidence: float = 0.0,
        recommended_bot: str = "",
    ) -> int:
        """Index a VMO capture PNG file."""
        with self._lock:
            conn = open_db(self._path)
            try:
                cur = conn.execute(
                    """
                    INSERT OR REPLACE INTO capture_index
                        (symbol, timeframe, captured_at_utc, file_path,
                         file_size_bytes, source, indicators,
                         regime, confidence, recommended_bot)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol, timeframe, captured_at,
                        file_path, file_size, source,
                        indicators, regime, confidence,
                        recommended_bot,
                    ),
                )
                conn.commit()
                return cur.lastrowid or 0
            finally:
                conn.close()

    # ── Bot Decisions ───────────────────────────────────────────────

    def log_decision(
        self,
        bot_id: str,
        bot_type: str,
        decision: str,
        action_taken: bool = False,
        symbol: str = "",
        reason: str = "",
        regime: str = "",
        equity_usdt: str = "0",
        pnl_usdt: str = "0",
        blocked_by: str = "",
        context: Optional[dict] = None,
    ) -> None:
        """Log a bot decision (taken or rejected)."""
        import json
        now = datetime.now(timezone.utc).isoformat()
        ctx = json.dumps(context or {}, default=str)[:1000]

        with self._lock:
            conn = open_db(self._path)
            try:
                conn.execute(
                    """
                    INSERT INTO bot_decisions
                        (ts_utc, bot_id, bot_type, symbol, decision,
                         action_taken, reason, regime_at_time,
                         equity_usdt, pnl_usdt, blocked_by, context_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now, bot_id[:60], bot_type[:20], symbol[:20],
                        decision[:120], 1 if action_taken else 0,
                        reason[:250], regime[:20],
                        equity_usdt[:30], pnl_usdt[:30],
                        blocked_by[:60], ctx,
                    ),
                )
                conn.commit()
            except Exception as exc:
                zoo = get_exception_zoo()
                zoo.register(exc, module="telemetry_vault", context="log_decision")
            finally:
                conn.close()

    # ── Analytics Queries (AI-friendly) ─────────────────────────────

    def get_winrate_by_regime(self) -> list[dict[str, Any]]:
        """Win rate per regime type (for AI/statistical analysis)."""
        conn = open_db(self._path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT regime_at_time,
                       COUNT(*) as total_decisions,
                       SUM(CASE WHEN action_taken = 1 THEN 1 ELSE 0 END) as actions_taken,
                       SUM(CASE WHEN CAST(pnl_usdt AS REAL) > 0 THEN 1 ELSE 0 END) as wins,
                       SUM(CASE WHEN CAST(pnl_usdt AS REAL) < 0 THEN 1 ELSE 0 END) as losses,
                       ROUND(AVG(CAST(pnl_usdt AS REAL)), 4) as avg_pnl
                FROM bot_decisions
                WHERE regime_at_time != ''
                GROUP BY regime_at_time
                """
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Prospector Scans ────────────────────────────────────────────

    def log_prospector_scan(
        self,
        symbol: str,
        evi_score: float,
        grade: str,
        adx: float,
        choppiness: float,
        avg_speed: float,
        freq_extreme: float,
        kurtosis: float,
        margin_eligible: bool,
    ) -> None:
        """Log a prospector scan result."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = open_db(self._path)
            try:
                conn.execute(
                    """
                    INSERT INTO prospector_scans
                        (ts_utc, symbol, evi_score, grade, adx, choppiness,
                         avg_speed, freq_extreme, kurtosis, margin_eligible)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now, symbol, float(evi_score), grade, float(adx),
                        float(choppiness), float(avg_speed), float(freq_extreme),
                        float(kurtosis), 1 if margin_eligible else 0
                    ),
                )
                conn.commit()
            except Exception as exc:
                zoo = get_exception_zoo()
                zoo.register(exc, module="telemetry_vault", context="log_prospector_scan")
            finally:
                conn.close()

    # ── Purge ───────────────────────────────────────────────────────

    def purge_old_data(self, kline_days: int = 365, decision_days: int = 90, capture_days: int = 30) -> dict[str, int]:
        """Purge old data post-analysis. Returns rows deleted per table."""
        conn = open_db(self._path)
        deleted = {}
        try:
            for table, days, ts_col in [
                ("kline_history", kline_days, "ingested_utc"),
                ("bot_decisions", decision_days, "ts_utc"),
                ("capture_index", capture_days, "captured_at_utc"),
            ]:
                cur = conn.execute(
                    f"DELETE FROM {table} WHERE {ts_col} < datetime('now', ?)",
                    (f"-{days} days",),
                )
                deleted[table] = cur.rowcount
            conn.commit()
            _LOG.info("Telemetry purge: %s", deleted)
        finally:
            conn.close()
        return deleted

    def summary(self) -> dict[str, Any]:
        conn = open_db(self._path)
        try:
            klines = conn.execute("SELECT COUNT(*) FROM kline_history").fetchone()[0]
            captures = conn.execute("SELECT COUNT(*) FROM capture_index").fetchone()[0]
            decisions = conn.execute("SELECT COUNT(*) FROM bot_decisions").fetchone()[0]
            return {
                "kline_candles": klines,
                "indexed_captures": captures,
                "bot_decisions": decisions,
            }
        finally:
            conn.close()


# ── Singleton ───────────────────────────────────────────────────────

_vault: Optional[TelemetryVault] = None


def get_telemetry_vault(data_dir: Optional[Path] = None) -> TelemetryVault:
    global _vault
    if _vault is None:
        d = data_dir or Path("runtime/data")
        _vault = TelemetryVault(Path(d) / "telemetry_vault.sqlite")
    return _vault
