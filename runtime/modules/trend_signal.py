"""Trend Signal Service — Heikin Ashi MA crossover for Dorothy on/off.

Computes Heikin Ashi candles from raw Binance klines, then derives:
  MA1 = SMA(1, HA_open)  →  simply the current HA open
  MA2 = SMA(2, HA_open)  →  average of last 2 HA opens

Signal:
  MA1 > MA2  →  BULLISH  →  Dorothy bots for this symbol = ON
  MA1 < MA2  →  BEARISH  →  Dorothy bots for this symbol = OFF
  MA1 == MA2 →  keep last known signal (tie-breaker)

Refresh cadence: every 2 hours per symbol (configurable).
One signal per symbol applies to ALL Dorothy instances on that symbol.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.core.db_util import open_db

_LOG = logging.getLogger("pecunator.modules.trend_signal")

# ── DDL ─────────────────────────────────────────────────────────────

_DDL = """\
CREATE TABLE IF NOT EXISTS trend_signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc      TEXT    NOT NULL,
    symbol      TEXT    NOT NULL,
    interval    TEXT    NOT NULL DEFAULT '1h',
    ma1_value   REAL    NOT NULL,
    ma2_value   REAL    NOT NULL,
    signal      TEXT    NOT NULL,  -- 'BULLISH' | 'BEARISH'
    ha_open     REAL    NOT NULL DEFAULT 0,
    ha_close    REAL    NOT NULL DEFAULT 0,
    source      TEXT    NOT NULL DEFAULT 'binance_klines'
);
CREATE INDEX IF NOT EXISTS idx_trend_sym_ts
    ON trend_signals(symbol, ts_utc DESC);
"""


# ── Heikin Ashi computation ─────────────────────────────────────────

def compute_heikin_ashi(klines: List[List]) -> List[Dict[str, float]]:
    """Convert raw Binance klines to Heikin Ashi OHLC.

    Each kline: [open_time, open, high, low, close, volume, ...]
    Returns list of dicts with ha_open, ha_high, ha_low, ha_close.
    """
    if not klines:
        return []

    result: List[Dict[str, float]] = []

    for i, k in enumerate(klines):
        o = float(k[1])
        h = float(k[2])
        l = float(k[3])  # noqa: E741
        c = float(k[4])

        ha_close = (o + h + l + c) / 4.0

        if i == 0:
            # First candle: HA_Open = (Open + Close) / 2
            ha_open = (o + c) / 2.0
        else:
            prev = result[i - 1]
            ha_open = (prev["ha_open"] + prev["ha_close"]) / 2.0

        ha_high = max(h, ha_open, ha_close)
        ha_low = min(l, ha_open, ha_close)

        result.append({
            "ha_open": ha_open,
            "ha_high": ha_high,
            "ha_low": ha_low,
            "ha_close": ha_close,
            "ts": int(k[0]),
        })

    return result


def compute_signal(ha_candles: List[Dict[str, float]]) -> Dict[str, Any]:
    """Compute MA1/MA2 crossover signal from HA candles.

    MA1 = SMA(1, HA_open) = last HA_open
    MA2 = SMA(2, HA_open) = avg of last 2 HA_opens
    """
    if len(ha_candles) < 2:
        return {"signal": "NEUTRAL", "ma1": 0.0, "ma2": 0.0, "reason": "insufficient_data"}

    ma1 = ha_candles[-1]["ha_open"]
    ma2 = (ha_candles[-1]["ha_open"] + ha_candles[-2]["ha_open"]) / 2.0

    if ma1 > ma2:
        signal = "BULLISH"
    elif ma1 < ma2:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"  # Caller resolves with last known

    return {
        "signal": signal,
        "ma1": round(ma1, 8),
        "ma2": round(ma2, 8),
        "ha_open": round(ha_candles[-1]["ha_open"], 8),
        "ha_close": round(ha_candles[-1]["ha_close"], 8),
    }


# ── Trend Signal Store ──────────────────────────────────────────────

@dataclass
class SymbolState:
    """In-memory cache for a symbol's trend state."""
    signal: str = "NEUTRAL"
    ma1: float = 0.0
    ma2: float = 0.0
    last_check_mono: float = 0.0
    last_ts_utc: str = ""


class TrendSignalService:
    """Manages trend signals for Dorothy symbols.

    Fetches klines from Binance, computes HA + MA crossover,
    stores results in SQLite, and caches in memory.
    """

    def __init__(
        self,
        db_path: Path,
        refresh_seconds: float = 7200.0,  # 2 hours default
        kline_interval: str = "1h",
        kline_limit: int = 10,  # Only need last few candles
    ) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._refresh_sec = refresh_seconds
        self._kline_interval = kline_interval
        self._kline_limit = kline_limit
        self._lock = threading.Lock()
        self._cache: Dict[str, SymbolState] = {}
        self._init_schema()

    def _init_schema(self) -> None:
        conn = open_db(self._db_path)
        try:
            conn.executescript(_DDL)
        finally:
            conn.close()

    # ── Public API ──────────────────────────────────────────────────

    def get_signal(self, symbol: str) -> str:
        """Get current signal for symbol. Returns 'BULLISH' or 'BEARISH'.

        If no data yet, returns 'NEUTRAL' (Dorothy should stay off).
        """
        s = self._cache.get(symbol.upper())
        if s is None:
            # Try loading from DB
            s = self._load_from_db(symbol.upper())
            if s:
                self._cache[symbol.upper()] = s
        return s.signal if s else "NEUTRAL"

    def get_all_signals(self) -> Dict[str, Dict[str, Any]]:
        """Get all cached signals."""
        result = {}
        for sym, state in self._cache.items():
            result[sym] = {
                "signal": state.signal,
                "ma1": state.ma1,
                "ma2": state.ma2,
                "last_check": state.last_ts_utc,
            }
        return result

    def should_run(self, symbol: str) -> bool:
        """Returns True if Dorothy bots for this symbol should be active."""
        sig = self.get_signal(symbol.upper())
        return sig == "BULLISH"

    def needs_refresh(self, symbol: str) -> bool:
        """Check if a symbol needs a fresh kline fetch."""
        s = self._cache.get(symbol.upper())
        if s is None:
            return True
        elapsed = time.monotonic() - s.last_check_mono
        return elapsed >= self._refresh_sec

    def update_from_klines(
        self, symbol: str, klines: List[List]
    ) -> Dict[str, Any]:
        """Compute trend from raw Binance klines and update cache + DB.

        Args:
            symbol: e.g. "BTCUSDT"
            klines: Raw Binance kline data (list of lists)

        Returns:
            Signal result dict with ma1, ma2, signal.
        """
        symbol = symbol.upper()
        ha_candles = compute_heikin_ashi(klines)
        result = compute_signal(ha_candles)

        now_utc = datetime.now(timezone.utc).isoformat()
        now_mono = time.monotonic()

        # Resolve NEUTRAL (tie) with last known signal
        if result["signal"] == "NEUTRAL":
            prev = self._cache.get(symbol)
            if prev and prev.signal in ("BULLISH", "BEARISH"):
                result["signal"] = prev.signal
                result["reason"] = "tie_kept_previous"
            else:
                # Load from DB as fallback
                db_state = self._load_from_db(symbol)
                if db_state and db_state.signal in ("BULLISH", "BEARISH"):
                    result["signal"] = db_state.signal
                    result["reason"] = "tie_kept_db"
                else:
                    result["signal"] = "BEARISH"  # Conservative default
                    result["reason"] = "tie_default_bearish"

        # Update cache
        state = SymbolState(
            signal=result["signal"],
            ma1=result["ma1"],
            ma2=result["ma2"],
            last_check_mono=now_mono,
            last_ts_utc=now_utc,
        )
        with self._lock:
            self._cache[symbol] = state

        # Persist to DB
        self._persist(symbol, result, now_utc)

        _LOG.info(
            "TrendSignal %s: %s (MA1=%.2f, MA2=%.2f, diff=%.4f)",
            symbol, result["signal"], result["ma1"], result["ma2"],
            result["ma1"] - result["ma2"],
        )

        return result

    # ── DB persistence ──────────────────────────────────────────────

    def _persist(self, symbol: str, result: Dict, ts_utc: str) -> None:
        try:
            conn = open_db(self._db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO trend_signals
                        (ts_utc, symbol, interval, ma1_value, ma2_value,
                         signal, ha_open, ha_close, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'binance_klines')
                    """,
                    (
                        ts_utc,
                        symbol,
                        self._kline_interval,
                        result["ma1"],
                        result["ma2"],
                        result["signal"],
                        result.get("ha_open", 0),
                        result.get("ha_close", 0),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            _LOG.warning("TrendSignal persist error: %s", exc)

    def _load_from_db(self, symbol: str) -> Optional[SymbolState]:
        try:
            conn = open_db(self._db_path)
            try:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    """
                    SELECT signal, ma1_value, ma2_value, ts_utc
                    FROM trend_signals
                    WHERE symbol = ?
                    ORDER BY ts_utc DESC LIMIT 1
                    """,
                    (symbol,),
                ).fetchone()
                if row:
                    return SymbolState(
                        signal=row["signal"],
                        ma1=row["ma1_value"],
                        ma2=row["ma2_value"],
                        last_ts_utc=row["ts_utc"],
                    )
            finally:
                conn.close()
        except Exception:
            pass
        return None

    def get_history(
        self, symbol: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get historical signals for a symbol."""
        conn = open_db(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT ts_utc, ma1_value, ma2_value, signal,
                       ha_open, ha_close
                FROM trend_signals
                WHERE symbol = ?
                ORDER BY ts_utc DESC LIMIT ?
                """,
                (symbol.upper(), min(limit, 500)),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def purge_old(self, days: int = 30) -> int:
        conn = open_db(self._db_path)
        try:
            c = conn.execute(
                "DELETE FROM trend_signals WHERE ts_utc < datetime('now', ?)",
                (f"-{days} days",),
            ).rowcount
            conn.commit()
            return c
        finally:
            conn.close()


# ── Singleton ───────────────────────────────────────────────────────

_service: Optional[TrendSignalService] = None


def get_trend_signal_service(
    data_dir: Optional[Path] = None,
) -> TrendSignalService:
    global _service
    if _service is None:
        d = data_dir or Path("runtime/data")
        _service = TrendSignalService(Path(d) / "trend_signals.sqlite")
    return _service
