"""Hub State Persistence — Core state machine for Dorothy/Elphaba symmetric hubs.

Provides a robust local source of truth for:
1. Hub Instances: Registered bots, their symbols, and configurations.
2. Active Rungs (DCA Positions): Tracking every buy, its paired sell limit,
   and status (OPEN, CLOSED, ORPHANED).
3. Hub Decisions: Historical audit log of decisions per cycle.

This mitigates the risk of relying purely on Binance's current open orders,
preventing "orphaned" positions when manual intervention occurs or the API flakes.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from runtime.core.db_util import open_db

_LOG = logging.getLogger("pecunator.core.hub_state")

_DDL = """\
CREATE TABLE IF NOT EXISTS hub_instances (
    bot_id          TEXT PRIMARY KEY,
    bot_type        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    config_json     TEXT,
    state           TEXT NOT NULL DEFAULT 'STOPPED',
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS hub_rungs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id          TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    buy_order_id    TEXT NOT NULL,
    sell_order_id   TEXT,
    buy_price       TEXT NOT NULL,
    sell_price      TEXT,
    qty             TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'OPEN',
    created_at      REAL NOT NULL,
    closed_at       REAL,
    FOREIGN KEY(bot_id) REFERENCES hub_instances(bot_id)
);
CREATE INDEX IF NOT EXISTS idx_rungs_bot ON hub_rungs(bot_id);
CREATE INDEX IF NOT EXISTS idx_rungs_status ON hub_rungs(status);

CREATE TABLE IF NOT EXISTS hub_decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              REAL NOT NULL,
    bot_id          TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    decision        TEXT NOT NULL,
    market_price    TEXT,
    equity_usdt     TEXT,
    drawdown_pct    TEXT,
    active_rungs    INTEGER,
    FOREIGN KEY(bot_id) REFERENCES hub_instances(bot_id)
);
CREATE INDEX IF NOT EXISTS idx_decisions_bot_ts ON hub_decisions(bot_id, ts);
"""


class HubStateStore:
    """Singleton for managing local hub state."""

    def __init__(self, data_dir: Path | str) -> None:
        self._db_path = Path(data_dir) / "hub_state.sqlite"
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

    # ── Instances ─────────────────────────────────────────────────────

    def register_instance(self, bot_id: str, bot_type: str, symbol: str, config: dict[str, Any]) -> None:
        now = time.time()
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO hub_instances (bot_id, bot_type, symbol, config_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(bot_id) DO UPDATE SET
                   config_json=excluded.config_json, updated_at=excluded.updated_at""",
                (bot_id, bot_type, symbol, json.dumps(config), now, now),
            )
            conn.commit()
        finally:
            conn.close()

    def update_instance_state(self, bot_id: str, state: str) -> None:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE hub_instances SET state=?, updated_at=? WHERE bot_id=?",
                (state, time.time(), bot_id)
            )
            conn.commit()
        finally:
            conn.close()

    def list_instances(self, bot_type: Optional[str] = None) -> list[dict[str, Any]]:
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        try:
            if bot_type:
                rows = conn.execute("SELECT * FROM hub_instances WHERE bot_type=?", (bot_type,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM hub_instances").fetchall()
        finally:
            conn.close()
            
        results = []
        for r in rows:
            d = dict(r)
            d["config"] = json.loads(d["config_json"]) if d["config_json"] else {}
            results.append(d)
        return results

    # ── Rungs (DCA Positions) ─────────────────────────────────────────

    def open_rung(
        self, bot_id: str, symbol: str, buy_order_id: str, buy_price: str, qty: str
    ) -> int:
        """Register a new buy (rung). Returns internal rung ID."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO hub_rungs (bot_id, symbol, buy_order_id, buy_price, qty, status, created_at)
                   VALUES (?, ?, ?, ?, ?, 'OPEN', ?)""",
                (bot_id, symbol, buy_order_id, buy_price, qty, time.time())
            )
            conn.commit()
            return cur.lastrowid or 0
        finally:
            conn.close()

    def link_sell_to_rung(self, rung_id: int, sell_order_id: str, sell_price: str) -> None:
        """Link the Take Profit LIMIT order to the active rung."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE hub_rungs SET sell_order_id=?, sell_price=? WHERE id=?",
                (sell_order_id, sell_price, rung_id)
            )
            conn.commit()
        finally:
            conn.close()

    def close_rung(self, rung_id: int, status: str = 'CLOSED') -> None:
        """Mark a rung as closed (TP filled) or orphaned."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE hub_rungs SET status=?, closed_at=? WHERE id=?",
                (status, time.time(), rung_id)
            )
            conn.commit()
        finally:
            conn.close()

    def get_open_rungs(self, bot_id: str) -> list[dict[str, Any]]:
        """Get all currently OPEN rungs for a specific bot."""
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM hub_rungs WHERE bot_id=? AND status='OPEN' ORDER BY created_at ASC",
                (bot_id,)
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    # ── Decisions ─────────────────────────────────────────────────────

    def log_decision(
        self, bot_id: str, symbol: str, decision: str,
        market_price: Optional[str] = None,
        equity_usdt: Optional[str] = None,
        drawdown_pct: Optional[str] = None,
        active_rungs: Optional[int] = None,
    ) -> None:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO hub_decisions (ts, bot_id, symbol, decision, market_price, equity_usdt, drawdown_pct, active_rungs)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (time.time(), bot_id, symbol, decision, market_price, equity_usdt, drawdown_pct, active_rungs)
            )
            conn.commit()
        finally:
            conn.close()


# ── Singleton ───────────────────────────────────────────────────────

_hub_state: Optional[HubStateStore] = None

def get_hub_state(data_dir: Optional[Path | str] = None) -> HubStateStore:
    global _hub_state
    if _hub_state is None:
        if data_dir is None:
            from runtime.core.settings import data_dir as _data_dir
            data_dir = _data_dir()
        _hub_state = HubStateStore(data_dir)
    return _hub_state
