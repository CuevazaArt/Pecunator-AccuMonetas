"""T0.3: Forensic order ledger — append-only record of every order sent to Binance.

Every call to client.create_order() in any bot MUST be preceded by
order_ledger.record(). This creates an immutable audit trail with:
- Full order parameters (symbol, side, type, qty, price)
- Decision context (reason, drawdown state, guard state, active rungs)
- Bot identity (bot_id, bot_type)
- Binance response (order_id, status) — updated post-execution

Unlike the event log which is verbose telemetry, this ledger is:
- Append-only (no updates, no deletes)
- Forensic (every field needed to reconstruct why an order was placed)
- Queryable (indexed by bot_id, symbol, timestamp)
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from runtime.core.db_util import open_db

_LOG = logging.getLogger("pecunator.core.order_ledger")

_DDL = """\
CREATE TABLE IF NOT EXISTS order_ledger (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                  REAL    NOT NULL,
    ts_utc              TEXT    NOT NULL,
    bot_id              TEXT    NOT NULL,
    bot_type            TEXT    NOT NULL,
    symbol              TEXT    NOT NULL,
    side                TEXT    NOT NULL,
    order_type          TEXT    NOT NULL,
    qty                 TEXT    NOT NULL,
    price               TEXT,
    quote_order_qty     TEXT,
    reason              TEXT    NOT NULL,
    drawdown_pct        TEXT,
    active_rungs        INTEGER,
    max_rungs           INTEGER,
    trading_blocked     INTEGER NOT NULL DEFAULT 0,
    guard_state         TEXT,
    binance_order_id    TEXT,
    binance_status      TEXT,
    execution_mode      TEXT    NOT NULL DEFAULT 'SIMULATED',
    extra_json          TEXT
);
CREATE INDEX IF NOT EXISTS idx_ol_bot ON order_ledger(bot_id);
CREATE INDEX IF NOT EXISTS idx_ol_symbol ON order_ledger(symbol);
CREATE INDEX IF NOT EXISTS idx_ol_ts ON order_ledger(ts);
"""


class OrderLedger:
    """Singleton forensic order ledger — append-only."""

    def __init__(self, data_dir: Path | str) -> None:
        self._db_path = Path(data_dir) / "order_ledger.sqlite"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = open_db(self._db_path)
        try:
            conn.executescript(_DDL)
        finally:
            conn.close()

    def _conn(self) -> sqlite3.Connection:
        return open_db(self._db_path)

    def record(
        self,
        *,
        bot_id: str,
        bot_type: str,
        symbol: str,
        side: str,
        order_type: str,
        qty: str,
        price: Optional[str] = None,
        quote_order_qty: Optional[str] = None,
        reason: str,
        drawdown_pct: Optional[str] = None,
        active_rungs: Optional[int] = None,
        max_rungs: Optional[int] = None,
        trading_blocked: bool = False,
        guard_state: Optional[str] = None,
        execution_mode: str = "SIMULATED",
        extra: Optional[dict[str, Any]] = None,
    ) -> int:
        """Record an order BEFORE sending it to Binance. Returns ledger row ID."""
        import json
        now = time.time()
        now_utc = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO order_ledger
                    (ts, ts_utc, bot_id, bot_type, symbol, side, order_type,
                     qty, price, quote_order_qty, reason, drawdown_pct,
                     active_rungs, max_rungs, trading_blocked, guard_state,
                     execution_mode, extra_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    now, now_utc, bot_id, bot_type, symbol, side, order_type,
                    qty, price, quote_order_qty, reason, drawdown_pct,
                    active_rungs, max_rungs, 1 if trading_blocked else 0,
                    guard_state, execution_mode,
                    json.dumps(extra) if extra else None,
                ),
            )
            conn.commit()
            row_id = cur.lastrowid or 0
        finally:
            conn.close()
        _LOG.info(
            "order_ledger: %s %s %s %s qty=%s price=%s reason=%s [id=%d]",
            bot_type, side, order_type, symbol, qty, price, reason, row_id,
        )
        return row_id

    def update_binance_response(
        self, ledger_id: int, order_id: str, status: str,
    ) -> None:
        """Update ledger row with Binance response AFTER execution."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE order_ledger SET binance_order_id=?, binance_status=? WHERE id=?",
                (order_id, status, ledger_id),
            )
            conn.commit()
        finally:
            conn.close()

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent orders for display."""
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM order_ledger ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        """Summary statistics."""
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM order_ledger").fetchone()[0]
            live = conn.execute(
                "SELECT COUNT(*) FROM order_ledger WHERE execution_mode='LIVE'"
            ).fetchone()[0]
            sim = conn.execute(
                "SELECT COUNT(*) FROM order_ledger WHERE execution_mode='SIMULATED'"
            ).fetchone()[0]
        finally:
            conn.close()
        return {"total_orders": total, "live_orders": live, "simulated_orders": sim}


# ── Singleton ───────────────────────────────────────────────────────

_ledger: Optional[OrderLedger] = None


def get_order_ledger(data_dir: Optional[Path | str] = None) -> OrderLedger:
    """Get or create the global OrderLedger singleton."""
    global _ledger
    if _ledger is None:
        if data_dir is None:
            from runtime.core.settings import data_dir as _data_dir
            data_dir = _data_dir()
        _ledger = OrderLedger(data_dir)
    return _ledger
