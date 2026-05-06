"""Regime cache — SQLite persistence for VMO classifications.

Stores MarketRegime snapshots and provides fast lookups for the
latest regime per (symbol, timeframe) pair.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from runtime.core.db_util import open_db
from runtime.modules.vision.chart_analyzer import MarketRegime

_LOG = logging.getLogger("pecunator.vmo.cache")

_DDL = """\
CREATE TABLE IF NOT EXISTS regime_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT    NOT NULL,
    timeframe       TEXT    NOT NULL,
    trend           TEXT    NOT NULL,
    trend_strength  TEXT    NOT NULL,
    volatility      TEXT    NOT NULL,
    regime          TEXT    NOT NULL,
    confidence      REAL    NOT NULL,
    recommended_bot TEXT    NOT NULL,
    risk_level      TEXT    NOT NULL,
    notes           TEXT,
    capture_source  TEXT    NOT NULL DEFAULT '',
    capture_path    TEXT,
    captured_at     TEXT    NOT NULL,
    analyzed_at     TEXT    NOT NULL,
    llm_provider    TEXT    NOT NULL DEFAULT '',
    llm_model       TEXT    NOT NULL DEFAULT '',
    elapsed_ms      INTEGER NOT NULL DEFAULT 0,
    UNIQUE(symbol, timeframe, captured_at)
);

CREATE INDEX IF NOT EXISTS idx_regime_symbol_tf
    ON regime_snapshots(symbol, timeframe, analyzed_at DESC);

CREATE INDEX IF NOT EXISTS idx_regime_analyzed
    ON regime_snapshots(analyzed_at DESC);
"""


class RegimeCache:
    """SQLite-backed regime classification cache."""

    def __init__(self, db_path: Path | str):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = open_db(self._db_path)
        try:
            conn.executescript(_DDL)
        finally:
            conn.close()

    def store(
        self,
        regime: MarketRegime,
        capture_path: Optional[str] = None,
    ) -> int:
        """Insert a regime snapshot. Returns the row ID."""
        conn = open_db(self._db_path)
        try:
            cur = conn.execute(
                """
                INSERT OR REPLACE INTO regime_snapshots
                    (symbol, timeframe, trend, trend_strength, volatility,
                     regime, confidence, recommended_bot, risk_level, notes,
                     capture_source, capture_path, captured_at, analyzed_at,
                     llm_provider, llm_model, elapsed_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    regime.symbol, regime.timeframe, regime.trend,
                    regime.trend_strength, regime.volatility, regime.regime,
                    regime.confidence, regime.recommended_bot,
                    regime.risk_level, regime.notes,
                    regime.capture_source, capture_path,
                    regime.captured_at, regime.analyzed_at,
                    regime.llm_provider, regime.llm_model,
                    regime.elapsed_ms,
                ),
            )
            conn.commit()
            return cur.lastrowid or 0
        finally:
            conn.close()

    def store_many(
        self,
        items: list[tuple[MarketRegime, Optional[str]]]
    ) -> int:
        """Insert multiple regime snapshots efficiently. Returns number of rows."""
        if not items:
            return 0
        conn = open_db(self._db_path)
        try:
            cur = conn.executemany(
                """
                INSERT OR REPLACE INTO regime_snapshots
                    (symbol, timeframe, trend, trend_strength, volatility,
                     regime, confidence, recommended_bot, risk_level, notes,
                     capture_source, capture_path, captured_at, analyzed_at,
                     llm_provider, llm_model, elapsed_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        r.symbol, r.timeframe, r.trend,
                        r.trend_strength, r.volatility, r.regime,
                        r.confidence, r.recommended_bot,
                        r.risk_level, r.notes,
                        r.capture_source, path,
                        r.captured_at, r.analyzed_at,
                        r.llm_provider, r.llm_model,
                        r.elapsed_ms,
                    ) for r, path in items
                ]
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    def get_latest(
        self,
        symbol: str = "",
        timeframe: str = "",
        limit: int = 50,
    ) -> list[MarketRegime]:
        """Get the latest regime snapshots, newest first."""
        conn = open_db(self._db_path)
        try:
            clauses: list[str] = []
            params: list[Any] = []
            if symbol:
                clauses.append("symbol = ?")
                params.append(symbol)
            if timeframe:
                clauses.append("timeframe = ?")
                params.append(timeframe)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = conn.execute(
                f"""
                SELECT symbol, timeframe, trend, trend_strength, volatility,
                       regime, confidence, recommended_bot, risk_level, notes,
                       capture_source, captured_at, analyzed_at,
                       llm_provider, llm_model, elapsed_ms
                FROM regime_snapshots {where}
                ORDER BY analyzed_at DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
            return [
                MarketRegime(
                    symbol=r[0], timeframe=r[1], trend=r[2],
                    trend_strength=r[3], volatility=r[4], regime=r[5],
                    confidence=r[6], recommended_bot=r[7],
                    risk_level=r[8], notes=r[9] or "",
                    capture_source=r[10] or "",
                    captured_at=r[11], analyzed_at=r[12],
                    llm_provider=r[13] or "", llm_model=r[14] or "",
                    elapsed_ms=r[15],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def get_latest_per_symbol(self) -> dict[str, dict[str, MarketRegime]]:
        """Get the most recent regime for each (symbol, timeframe) pair.

        Returns: {symbol: {timeframe: MarketRegime}}
        """
        conn = open_db(self._db_path)
        try:
            rows = conn.execute(
                """
                SELECT symbol, timeframe, trend, trend_strength, volatility,
                       regime, confidence, recommended_bot, risk_level, notes,
                       capture_source, captured_at, analyzed_at,
                       llm_provider, llm_model, elapsed_ms
                FROM regime_snapshots r1
                WHERE analyzed_at = (
                    SELECT MAX(r2.analyzed_at)
                    FROM regime_snapshots r2
                    WHERE r2.symbol = r1.symbol AND r2.timeframe = r1.timeframe
                )
                ORDER BY symbol, timeframe
                """
            ).fetchall()
            result: dict[str, dict[str, MarketRegime]] = {}
            for r in rows:
                sym = r[0]
                tf = r[1]
                regime = MarketRegime(
                    symbol=sym, timeframe=tf, trend=r[2],
                    trend_strength=r[3], volatility=r[4], regime=r[5],
                    confidence=r[6], recommended_bot=r[7],
                    risk_level=r[8], notes=r[9] or "",
                    capture_source=r[10] or "",
                    captured_at=r[11], analyzed_at=r[12],
                    llm_provider=r[13] or "", llm_model=r[14] or "",
                    elapsed_ms=r[15],
                )
                result.setdefault(sym, {})[tf] = regime
            return result
        finally:
            conn.close()

    def count(self, symbol: str = "") -> int:
        """Count total snapshots."""
        conn = open_db(self._db_path)
        try:
            if symbol:
                row = conn.execute(
                    "SELECT COUNT(*) FROM regime_snapshots WHERE symbol = ?",
                    (symbol,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) FROM regime_snapshots"
                ).fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def summary(self) -> dict[str, Any]:
        """Quick summary of the regime cache."""
        conn = open_db(self._db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*), MIN(analyzed_at), MAX(analyzed_at) "
                "FROM regime_snapshots"
            ).fetchone()
            return {
                "total_snapshots": row[0] if row else 0,
                "first_snapshot": row[1] if row else None,
                "last_snapshot": row[2] if row else None,
            }
        finally:
            conn.close()
