"""Trend Signal Service — Dual-gate system for Dorothy execution.

Gate 1 — TREND (every 2h, Heikin Ashi 1h):
  Computes HA candles from raw Binance klines, then:
    MA1 = SMA(1, HA_open) — current HA open
    MA2 = SMA(2, HA_open) — avg of last 2 HA opens
  MA1 > MA2 → BULLISH  |  MA1 < MA2 → BEARISH
  MA1 == MA2 → keep last *effective* (non-neutral) trend forever

Gate 2 — ENTRY (every ≤5min, regular candles 1h):
  Current price vs open of the *active* regular 1h candle:
    price < candle_open → CLEAR (dip within candle = good entry)
    price ≥ candle_open → BLOCKED (at or above open = possible peak)

Dorothy executes ONLY when:  Gate1 == BULLISH  AND  Gate2 == CLEAR
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
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

CREATE TABLE IF NOT EXISTS entry_gate_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc        TEXT    NOT NULL,
    symbol        TEXT    NOT NULL,
    current_price REAL    NOT NULL,
    candle_open   REAL    NOT NULL,
    gate          TEXT    NOT NULL,  -- 'CLEAR' | 'BLOCKED'
    trend         TEXT    NOT NULL DEFAULT 'NEUTRAL',
    combined      TEXT    NOT NULL DEFAULT 'OFF'  -- 'ON' | 'OFF'
);
CREATE INDEX IF NOT EXISTS idx_entry_sym_ts
    ON entry_gate_log(symbol, ts_utc DESC);
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


def compute_trend(ha_candles: List[Dict[str, float]]) -> Dict[str, Any]:
    """Compute MA1/MA2 crossover signal from HA candles (Gate 1).

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
        signal = "NEUTRAL"  # Caller resolves with last effective

    return {
        "signal": signal,
        "ma1": round(ma1, 8),
        "ma2": round(ma2, 8),
        "ha_open": round(ha_candles[-1]["ha_open"], 8),
        "ha_close": round(ha_candles[-1]["ha_close"], 8),
    }


def compute_entry_gate(
    current_price: float,
    candle_open_1h: float,
) -> Dict[str, Any]:
    """Check entry gate (Gate 2): price vs regular 1h candle open.

    price < candle_open → CLEAR  (dip = good entry for long)
    price ≥ candle_open → BLOCKED (at/above open = potential peak)
    """
    if candle_open_1h <= 0:
        return {"gate": "BLOCKED", "reason": "invalid_candle_open"}

    if current_price < candle_open_1h:
        gate = "CLEAR"
    else:
        gate = "BLOCKED"

    return {
        "gate": gate,
        "current_price": round(current_price, 8),
        "candle_open": round(candle_open_1h, 8),
        "diff": round(current_price - candle_open_1h, 8),
        "diff_pct": round(((current_price - candle_open_1h) / candle_open_1h) * 100, 4),
    }


# ── In-memory state ────────────────────────────────────────────────

@dataclass
class SymbolState:
    """In-memory cache for a symbol's full gate state."""
    # Gate 1: Trend
    trend: str = "NEUTRAL"           # BULLISH | BEARISH | NEUTRAL
    last_effective_trend: str = ""   # Last non-NEUTRAL trend (persists through ties)
    ma1: float = 0.0
    ma2: float = 0.0
    trend_check_mono: float = 0.0
    trend_ts_utc: str = ""

    # Gate 2: Entry
    entry_gate: str = "BLOCKED"      # CLEAR | BLOCKED
    current_price: float = 0.0
    candle_open: float = 0.0
    entry_check_mono: float = 0.0
    entry_ts_utc: str = ""

    @property
    def should_run(self) -> bool:
        """Dorothy executes ONLY when both gates are open."""
        effective = self.last_effective_trend or self.trend
        return effective == "BULLISH" and self.entry_gate == "CLEAR"

    @property
    def effective_trend(self) -> str:
        return self.last_effective_trend or self.trend


# ── Service ─────────────────────────────────────────────────────────

class TrendSignalService:
    """Dual-gate trend + entry service for Dorothy.

    Gate 1 (trend):  Refreshes every 2h — HA MA crossover on 1h klines.
    Gate 2 (entry):  Refreshes every 5min — price vs regular 1h open.
    """

    TREND_REFRESH_SEC = 7200.0   # 2 hours
    ENTRY_REFRESH_SEC = 300.0    # 5 minutes

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
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

    def should_run(self, symbol: str) -> bool:
        """Returns True if Dorothy bots for this symbol should execute.

        Both gates must be open:
          Gate 1: trend == BULLISH (effective, including tie-break)
          Gate 2: entry == CLEAR  (price < regular 1h open)
        """
        sym = symbol.upper()
        s = self._ensure_state(sym)
        return s.should_run

    def get_signal(self, symbol: str) -> str:
        """Get effective trend for symbol (BULLISH/BEARISH)."""
        sym = symbol.upper()
        s = self._ensure_state(sym)
        return s.effective_trend

    def get_entry_gate(self, symbol: str) -> str:
        """Get entry gate status (CLEAR/BLOCKED)."""
        sym = symbol.upper()
        s = self._ensure_state(sym)
        return s.entry_gate

    def get_full_state(self, symbol: str) -> Dict[str, Any]:
        """Get complete state for a symbol."""
        sym = symbol.upper()
        s = self._ensure_state(sym)
        return {
            "symbol": sym,
            "should_run": s.should_run,
            "trend": s.effective_trend,
            "trend_raw": s.trend,
            "ma1": s.ma1,
            "ma2": s.ma2,
            "ma_diff": round(s.ma1 - s.ma2, 8),
            "trend_last_check": s.trend_ts_utc,
            "entry_gate": s.entry_gate,
            "current_price": s.current_price,
            "candle_open_1h": s.candle_open,
            "price_vs_open": round(s.current_price - s.candle_open, 8),
            "entry_last_check": s.entry_ts_utc,
        }

    def get_all_signals(self) -> Dict[str, Dict[str, Any]]:
        """Get all cached signals."""
        result = {}
        for sym, s in self._cache.items():
            result[sym] = {
                "should_run": s.should_run,
                "trend": s.effective_trend,
                "ma1": s.ma1,
                "ma2": s.ma2,
                "entry_gate": s.entry_gate,
                "price": s.current_price,
                "candle_open": s.candle_open,
                "trend_check": s.trend_ts_utc,
                "entry_check": s.entry_ts_utc,
            }
        return result

    # ── Refresh checks ──────────────────────────────────────────────

    def needs_trend_refresh(self, symbol: str) -> bool:
        """Check if trend (Gate 1) needs refresh (every 2h)."""
        s = self._cache.get(symbol.upper())
        if s is None or s.trend_check_mono == 0.0:
            return True
        return (time.monotonic() - s.trend_check_mono) >= self.TREND_REFRESH_SEC

    def needs_entry_refresh(self, symbol: str) -> bool:
        """Check if entry gate (Gate 2) needs refresh (every 5min)."""
        s = self._cache.get(symbol.upper())
        if s is None or s.entry_check_mono == 0.0:
            return True
        return (time.monotonic() - s.entry_check_mono) >= self.ENTRY_REFRESH_SEC

    # ── Gate 1: Trend update ────────────────────────────────────────

    def update_trend(self, symbol: str, klines_1h: List[List]) -> Dict[str, Any]:
        """Update trend from 1h HA klines (Gate 1).

        Args:
            symbol: e.g. "BTCUSDT"
            klines_1h: Raw Binance 1h klines
        """
        sym = symbol.upper()
        ha = compute_heikin_ashi(klines_1h)
        result = compute_trend(ha)
        now_utc = datetime.now(timezone.utc).isoformat()
        now_mono = time.monotonic()

        with self._lock:
            s = self._cache.get(sym) or SymbolState()

            # Resolve tie: if NEUTRAL, keep last effective trend
            if result["signal"] == "NEUTRAL":
                if s.last_effective_trend:
                    result["signal"] = s.last_effective_trend
                    result["reason"] = "tie_kept_effective"
                else:
                    # Try DB for historical effective trend
                    db_trend = self._load_last_effective_trend(sym)
                    if db_trend:
                        result["signal"] = db_trend
                        result["reason"] = "tie_kept_db"
                    else:
                        result["signal"] = "BEARISH"  # Conservative
                        result["reason"] = "tie_default_bearish"

            # Update effective trend only when signal is definitive
            if result["signal"] in ("BULLISH", "BEARISH"):
                s.last_effective_trend = result["signal"]

            s.trend = result["signal"]
            s.ma1 = result["ma1"]
            s.ma2 = result["ma2"]
            s.trend_check_mono = now_mono
            s.trend_ts_utc = now_utc
            self._cache[sym] = s

        # Persist
        self._persist_trend(sym, result, now_utc)

        _LOG.info(
            "Gate1 TREND %s: %s (MA1=%.2f MA2=%.2f diff=%.4f)",
            sym, result["signal"], result["ma1"], result["ma2"],
            result["ma1"] - result["ma2"],
        )
        return result

    # ── Gate 2: Entry gate update ───────────────────────────────────

    def update_entry_gate(
        self,
        symbol: str,
        current_price: float,
        candle_open_1h: float,
    ) -> Dict[str, Any]:
        """Update entry gate from current price vs regular 1h candle open.

        Args:
            symbol: e.g. "BTCUSDT"
            current_price: Latest ticker price
            candle_open_1h: Open of the *current active* regular 1h candle
        """
        sym = symbol.upper()
        gate_result = compute_entry_gate(current_price, candle_open_1h)
        now_utc = datetime.now(timezone.utc).isoformat()
        now_mono = time.monotonic()

        with self._lock:
            s = self._cache.get(sym) or SymbolState()
            s.entry_gate = gate_result["gate"]
            s.current_price = gate_result["current_price"]
            s.candle_open = gate_result["candle_open"]
            s.entry_check_mono = now_mono
            s.entry_ts_utc = now_utc
            self._cache[sym] = s

            combined = "ON" if s.should_run else "OFF"

        # Persist (throttled — only log when gate changes or every ~5min)
        self._persist_entry(sym, gate_result, s.effective_trend, combined, now_utc)

        _LOG.info(
            "Gate2 ENTRY %s: %s (price=%.2f open=%.2f diff=%.2f) → combined=%s",
            sym, gate_result["gate"],
            current_price, candle_open_1h,
            current_price - candle_open_1h, combined,
        )

        return {
            **gate_result,
            "trend": s.effective_trend,
            "combined": combined,
            "should_run": combined == "ON",
        }

    # ── Combined update (convenience) ───────────────────────────────

    def update_both(
        self,
        symbol: str,
        klines_1h: List[List],
        current_price: float,
    ) -> Dict[str, Any]:
        """Update both gates in one call.

        Extracts regular 1h candle open from the last kline,
        then runs both gate computations.
        """
        sym = symbol.upper()

        # Gate 1: Trend from HA klines
        trend_result = self.update_trend(sym, klines_1h)

        # Gate 2: Entry from regular candle open
        # Last kline = current active 1h candle
        candle_open = float(klines_1h[-1][1]) if klines_1h else 0.0
        entry_result = self.update_entry_gate(sym, current_price, candle_open)

        return {
            "symbol": sym,
            "trend": trend_result,
            "entry": entry_result,
            "should_run": entry_result.get("should_run", False),
        }

    # ── DB persistence ──────────────────────────────────────────────

    def _persist_trend(self, symbol: str, result: Dict, ts_utc: str) -> None:
        try:
            conn = open_db(self._db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO trend_signals
                        (ts_utc, symbol, interval, ma1_value, ma2_value,
                         signal, ha_open, ha_close, source)
                    VALUES (?, ?, '1h', ?, ?, ?, ?, ?, 'binance_klines')
                    """,
                    (
                        ts_utc, symbol,
                        result["ma1"], result["ma2"], result["signal"],
                        result.get("ha_open", 0), result.get("ha_close", 0),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            _LOG.warning("Persist trend error: %s", exc)

    def _persist_entry(
        self, symbol: str, gate: Dict, trend: str, combined: str, ts_utc: str
    ) -> None:
        try:
            conn = open_db(self._db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO entry_gate_log
                        (ts_utc, symbol, current_price, candle_open,
                         gate, trend, combined)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts_utc, symbol,
                        gate["current_price"], gate["candle_open"],
                        gate["gate"], trend, combined,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            _LOG.warning("Persist entry error: %s", exc)

    def _load_last_effective_trend(self, symbol: str) -> Optional[str]:
        """Load the last non-NEUTRAL trend from DB history."""
        try:
            conn = open_db(self._db_path)
            try:
                row = conn.execute(
                    """
                    SELECT signal FROM trend_signals
                    WHERE symbol = ? AND signal IN ('BULLISH', 'BEARISH')
                    ORDER BY ts_utc DESC LIMIT 1
                    """,
                    (symbol,),
                ).fetchone()
                return row[0] if row else None
            finally:
                conn.close()
        except Exception:
            return None

    def _ensure_state(self, symbol: str) -> SymbolState:
        """Get or create state, loading from DB if needed."""
        s = self._cache.get(symbol)
        if s is not None:
            return s
        # Try DB
        db_trend = self._load_last_effective_trend(symbol)
        s = SymbolState()
        if db_trend:
            s.trend = db_trend
            s.last_effective_trend = db_trend
        with self._lock:
            self._cache[symbol] = s
        return s

    # ── History queries ─────────────────────────────────────────────

    def get_trend_history(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        conn = open_db(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT ts_utc, ma1_value, ma2_value, signal, ha_open, ha_close
                FROM trend_signals WHERE symbol = ?
                ORDER BY ts_utc DESC LIMIT ?
                """,
                (symbol.upper(), min(limit, 500)),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_entry_history(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        conn = open_db(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT ts_utc, current_price, candle_open, gate, trend, combined
                FROM entry_gate_log WHERE symbol = ?
                ORDER BY ts_utc DESC LIMIT ?
                """,
                (symbol.upper(), min(limit, 1000)),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def purge_old(self, days: int = 30) -> int:
        conn = open_db(self._db_path)
        try:
            c1 = conn.execute(
                "DELETE FROM trend_signals WHERE ts_utc < datetime('now', ?)",
                (f"-{days} days",),
            ).rowcount
            c2 = conn.execute(
                "DELETE FROM entry_gate_log WHERE ts_utc < datetime('now', ?)",
                (f"-{days} days",),
            ).rowcount
            conn.commit()
            return c1 + c2
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
