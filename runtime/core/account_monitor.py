"""Account Monitor — Periodic balance/equity snapshots for accounts and sub-accounts.

Takes snapshots of account state at configurable intervals and persists
them for trend analysis, rebalancing signals, and audit trails.

Monitors:
  - Total equity in USDT
  - Free vs locked balances
  - Open positions / orders count
  - P&L since last snapshot
  - Triggers rebalancing signals when thresholds are crossed

Design: Resilient to disconnections, partial data, and API failures.
Every snapshot attempt is logged, including failures.
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

_LOG = logging.getLogger("pecunator.core.account_monitor")

_DDL = """\
CREATE TABLE IF NOT EXISTS account_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc          TEXT    NOT NULL,
    account_id      TEXT    NOT NULL DEFAULT 'main',
    total_equity    TEXT    NOT NULL DEFAULT '0',
    free_usdt       TEXT    NOT NULL DEFAULT '0',
    locked_usdt     TEXT    NOT NULL DEFAULT '0',
    in_earn         TEXT    NOT NULL DEFAULT '0',
    open_orders     INTEGER NOT NULL DEFAULT 0,
    open_positions  INTEGER NOT NULL DEFAULT 0,
    pnl_since_last  TEXT    NOT NULL DEFAULT '0',
    snapshot_ok     INTEGER NOT NULL DEFAULT 1,
    error_note      TEXT    NOT NULL DEFAULT '',
    api_weight_used INTEGER NOT NULL DEFAULT 0,
    assets_json     TEXT    NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_acct_ts
    ON account_snapshots(account_id, ts_utc DESC);

CREATE TABLE IF NOT EXISTS rebalance_signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc          TEXT    NOT NULL,
    account_id      TEXT    NOT NULL DEFAULT 'main',
    signal_type     TEXT    NOT NULL,
    description     TEXT    NOT NULL,
    current_value   TEXT    NOT NULL DEFAULT '0',
    threshold       TEXT    NOT NULL DEFAULT '0',
    acknowledged    INTEGER NOT NULL DEFAULT 0,
    acted_on        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_rebal_ts
    ON rebalance_signals(ts_utc DESC);
"""


class AccountMonitor:
    """Periodic account state monitor with rebalancing signal detection."""

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

    def record_snapshot(
        self,
        account_id: str = "main",
        total_equity: str = "0",
        free_usdt: str = "0",
        locked_usdt: str = "0",
        in_earn: str = "0",
        open_orders: int = 0,
        open_positions: int = 0,
        api_weight_used: int = 0,
        assets_json: str = "[]",
        error_note: str = "",
    ) -> int:
        """Record an account snapshot. Returns row ID."""
        now = datetime.now(timezone.utc).isoformat()

        # Calculate P&L since last snapshot
        pnl = "0"
        try:
            last = self.get_latest_snapshot(account_id)
            if last and last.get("total_equity"):
                prev = float(last["total_equity"])
                curr = float(total_equity)
                pnl = str(round(curr - prev, 4))
        except Exception:
            pass

        snapshot_ok = 1 if not error_note else 0

        with self._lock:
            conn = open_db(self._path)
            try:
                cur = conn.execute(
                    """
                    INSERT INTO account_snapshots
                        (ts_utc, account_id, total_equity, free_usdt,
                         locked_usdt, in_earn, open_orders, open_positions,
                         pnl_since_last, snapshot_ok, error_note,
                         api_weight_used, assets_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now, account_id[:30], total_equity[:30],
                        free_usdt[:30], locked_usdt[:30], in_earn[:30],
                        open_orders, open_positions, pnl,
                        snapshot_ok, error_note[:250],
                        api_weight_used, assets_json[:5000],
                    ),
                )
                conn.commit()

                # Check rebalancing thresholds
                if snapshot_ok:
                    self._check_rebalance_signals(
                        conn, account_id, total_equity, free_usdt
                    )

                return cur.lastrowid or 0
            except Exception as exc:
                zoo = get_exception_zoo()
                zoo.register(exc, module="account_monitor", context="record_snapshot")
                return 0
            finally:
                conn.close()

    def _check_rebalance_signals(
        self, conn: sqlite3.Connection,
        account_id: str, equity: str, free_usdt: str,
    ) -> None:
        """Detect conditions that warrant rebalancing."""
        try:
            equity_f = float(equity)
            free_f = float(free_usdt)

            if equity_f <= 0:
                return

            now = datetime.now(timezone.utc).isoformat()
            free_pct = (free_f / equity_f) * 100

            # Signal: Too little free liquidity (<5%)
            if free_pct < 5.0:
                conn.execute(
                    """
                    INSERT INTO rebalance_signals
                        (ts_utc, account_id, signal_type, description,
                         current_value, threshold)
                    VALUES (?, ?, 'LOW_LIQUIDITY', ?, ?, '5%')
                    """,
                    (
                        now, account_id,
                        f"Free USDT is {free_pct:.1f}% of equity ({free_usdt} / {equity})",
                        f"{free_pct:.1f}%",
                    ),
                )

            # Signal: Excess idle capital (>60% free)
            if free_pct > 60.0 and equity_f > 100:
                conn.execute(
                    """
                    INSERT INTO rebalance_signals
                        (ts_utc, account_id, signal_type, description,
                         current_value, threshold)
                    VALUES (?, ?, 'EXCESS_IDLE', ?, ?, '60%')
                    """,
                    (
                        now, account_id,
                        f"Free USDT is {free_pct:.1f}% of equity — consider deploying to Earn or bots",
                        f"{free_pct:.1f}%",
                    ),
                )

            conn.commit()
        except (ValueError, TypeError):
            pass

    def get_latest_snapshot(self, account_id: str = "main") -> Optional[dict[str, Any]]:
        conn = open_db(self._path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM account_snapshots
                WHERE account_id = ? AND snapshot_ok = 1
                ORDER BY ts_utc DESC LIMIT 1
                """,
                (account_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_history(
        self, account_id: str = "main", limit: int = 100
    ) -> list[dict[str, Any]]:
        conn = open_db(self._path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT ts_utc, total_equity, free_usdt, locked_usdt,
                       in_earn, open_orders, pnl_since_last, snapshot_ok
                FROM account_snapshots
                WHERE account_id = ?
                ORDER BY ts_utc DESC LIMIT ?
                """,
                (account_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_pending_signals(self, account_id: str = "") -> list[dict[str, Any]]:
        """Get unacknowledged rebalance signals."""
        conn = open_db(self._path)
        try:
            conn.row_factory = sqlite3.Row
            if account_id:
                rows = conn.execute(
                    "SELECT * FROM rebalance_signals WHERE account_id = ? AND acknowledged = 0 ORDER BY ts_utc DESC",
                    (account_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM rebalance_signals WHERE acknowledged = 0 ORDER BY ts_utc DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def acknowledge_signal(self, signal_id: int, acted_on: bool = False) -> bool:
        conn = open_db(self._path)
        try:
            cur = conn.execute(
                "UPDATE rebalance_signals SET acknowledged = 1, acted_on = ? WHERE id = ?",
                (1 if acted_on else 0, signal_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def purge_old(self, days: int = 90) -> int:
        conn = open_db(self._path)
        try:
            c1 = conn.execute(
                "DELETE FROM account_snapshots WHERE ts_utc < datetime('now', ?)",
                (f"-{days} days",),
            ).rowcount
            c2 = conn.execute(
                "DELETE FROM rebalance_signals WHERE ts_utc < datetime('now', ?) AND acknowledged = 1",
                (f"-{days} days",),
            ).rowcount
            conn.commit()
            return c1 + c2
        finally:
            conn.close()

    def summary(self) -> dict[str, Any]:
        conn = open_db(self._path)
        try:
            total = conn.execute("SELECT COUNT(*) FROM account_snapshots").fetchone()[0]
            signals = conn.execute(
                "SELECT COUNT(*) FROM rebalance_signals WHERE acknowledged = 0"
            ).fetchone()[0]
            return {
                "total_snapshots": total,
                "pending_signals": signals,
            }
        finally:
            conn.close()


# ── Singleton ───────────────────────────────────────────────────────

_monitor: Optional[AccountMonitor] = None


def get_account_monitor(data_dir: Optional[Path] = None) -> AccountMonitor:
    global _monitor
    if _monitor is None:
        d = data_dir or Path("runtime/data")
        _monitor = AccountMonitor(Path(d) / "account_monitor.sqlite")
    return _monitor
