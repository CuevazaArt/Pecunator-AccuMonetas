"""Centralized telemetry persistence — snapshots all observable metrics.

Every metric that appears on a chart or dashboard is recorded periodically
so that:
  1. Charts load historical data on startup instead of starting empty.
  2. All data survives restarts (trazability).
  3. Statistical analysis and evolution studies can be performed offline.

The collector runs as a background asyncio task, sampling every N seconds.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

_LOG = logging.getLogger("pecunator.telemetry_collector")

# ── Schema ────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS telemetry_snapshots (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc            TEXT    NOT NULL,

    -- Account equity & capital breakdown
    equity_usdt       REAL,
    free_usdt         REAL,
    locked_usdt       REAL,
    margin_usdt       REAL,

    -- API weight
    used_weight_1m    INTEGER,
    weight_limit_1m   INTEGER,

    -- Order rate
    order_count_10s   INTEGER,
    order_limit_10s   INTEGER,

    -- Fleet state
    bots_running      INTEGER,
    bots_total        INTEGER,
    dorothy_running   INTEGER,
    dorothy_total     INTEGER,
    elphaba_running   INTEGER,
    elphaba_total     INTEGER,

    -- Fuse status
    api_fuse_ok       INTEGER,
    order_fuse_ok     INTEGER,

    -- Gateway
    gateway_running   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry_snapshots(ts_utc);
"""


class TelemetryCollector:
    """Periodically snapshots all observable metrics to SQLite.

    Usage:
        collector = TelemetryCollector(data_dir)
        await collector.start(ctx)  # starts background task
        await collector.stop()      # cancels background task
    """

    def __init__(
        self,
        data_dir: Path,
        interval_sec: float = 10.0,
    ) -> None:
        self._db_path = Path(data_dir) / "telemetry_snapshots.sqlite"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._interval = max(2.0, interval_sec)
        self._lock = threading.Lock()
        self._task: Optional[asyncio.Task[None]] = None
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.executescript(_SCHEMA)
            # WAL for concurrent reads
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA busy_timeout = 3000")
        _LOG.info("telemetry_collector: DB ready at %s", self._db_path)

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def start(self, ctx: Any) -> None:
        """Start the background collection loop."""
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop(ctx))
        _LOG.info("telemetry_collector: started (interval=%.0fs)", self._interval)

    async def stop(self) -> None:
        """Cancel the background task."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        _LOG.info("telemetry_collector: stopped")

    async def _loop(self, ctx: Any) -> None:
        """Main collection loop — runs until cancelled."""
        cycle = 0
        while True:
            try:
                snapshot = self._collect(ctx)
                self._persist(snapshot)
                # Push to WebSocket clients (zero-polling telemetry)
                await self._broadcast(snapshot)
                # Prune old snapshots every ~100 cycles (~16 min at 10s interval)
                cycle += 1
                if cycle % 100 == 0:
                    self._prune_old_snapshots(days=7)
            except Exception as e:
                _LOG.warning("telemetry_collector: sample failed: %s", e)
            await asyncio.sleep(self._interval)

    async def _broadcast(self, snapshot: dict[str, Any]) -> None:
        """Push snapshot to all connected WebSocket clients."""
        try:
            from runtime.core.ws_broadcaster import get_broadcaster
            await get_broadcaster().publish("TELEMETRY_TICK", snapshot)
        except Exception as e:
            _LOG.debug("telemetry_collector: ws broadcast skipped: %s", e)

    # ── Collection ────────────────────────────────────────────────────

    def _collect(self, ctx: Any) -> dict[str, Any]:
        """Gather all observable metrics from the running context."""
        state = getattr(ctx, "state", None)
        snapshot: dict[str, Any] = {
            "ts_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

        # -- Account equity & capital --
        equity = 0.0
        free_usdt = 0.0
        locked_usdt = 0.0
        if state:
            # Equity from state
            eq_raw = getattr(state, "account_equity", None)
            if isinstance(eq_raw, dict):
                equity = float(eq_raw.get("current", 0) or 0)
            elif eq_raw is not None:
                try:
                    equity = float(eq_raw)
                except (ValueError, TypeError):
                    pass

            # Balances
            balances = getattr(state, "balances", None) or []
            for b in balances:
                if isinstance(b, dict) and b.get("asset") == "USDT":
                    free_usdt = float(b.get("free", 0) or 0)
                    locked_usdt = float(b.get("locked", 0) or 0)
                    break

        margin_usdt = max(0.0, equity - free_usdt - locked_usdt)
        # Always emit numeric values — let the UI decide how to render zero.
        # Sending None caused the frontend to discard ticks, freezing charts.
        snapshot["equity_usdt"] = equity
        snapshot["free_usdt"] = free_usdt
        snapshot["locked_usdt"] = locked_usdt
        snapshot["margin_usdt"] = margin_usdt

        # -- API weight --
        snapshot["used_weight_1m"] = getattr(state, "api_weight_used_1m", None) if state else None
        try:
            from runtime.core.settings import api_weight_limit_1m_display
            snapshot["weight_limit_1m"] = api_weight_limit_1m_display()
        except Exception:
            snapshot["weight_limit_1m"] = 6000

        # -- Order rate --
        snapshot["order_count_10s"] = getattr(state, "order_count_10s", None) if state else None
        # Order limit from fuse
        order_limit = None
        try:
            from runtime.core.order_fuse import get_order_fuse
            fuse = get_order_fuse()
            order_limit = fuse.order_limit_10s
        except Exception:
            pass
        snapshot["order_limit_10s"] = order_limit

        # -- Fleet state --
        d_running = 0
        d_total = 0
        e_running = 0
        e_total = 0
        dorothy_bots_list: list[dict[str, Any]] = []
        elphaba_bots_list: list[dict[str, Any]] = []
        try:
            from runtime.api import deps
            bot_svc = deps.get_bot()
            dorothy_bots_list = bot_svc.list_instances()
            for b in dorothy_bots_list:
                d_total += 1
                if b.get("running"):
                    d_running += 1
        except Exception:
            pass
        try:
            from runtime.api import deps
            eph_svc = deps.get_elphaba()
            elphaba_bots_list = eph_svc.list_instances()
            for b in elphaba_bots_list:
                e_total += 1
                if b.get("running"):
                    e_running += 1
        except Exception:
            pass
        snapshot["dorothy_running"] = d_running
        snapshot["dorothy_total"] = d_total
        snapshot["elphaba_running"] = e_running
        snapshot["elphaba_total"] = e_total
        snapshot["bots_running"] = d_running + e_running
        snapshot["bots_total"] = d_total + e_total
        snapshot["dorothy_bots"] = dorothy_bots_list
        snapshot["elphaba_bots"] = elphaba_bots_list

        # -- Fuse status --
        snapshot["api_fuse_ok"] = 1
        try:
            from runtime.core.api_fuse import get_api_fuse
            snapshot["api_fuse_ok"] = 0 if get_api_fuse().is_tripped() else 1
        except Exception:
            pass
        snapshot["order_fuse_ok"] = 1
        try:
            from runtime.core.order_fuse import get_order_fuse
            snapshot["order_fuse_ok"] = 0 if get_order_fuse().is_tripped() else 1
        except Exception:
            pass

        # -- Gateway --
        gw = getattr(ctx, "gateway", None)
        snapshot["gateway_running"] = 1 if gw else 0

        # -- Gateway snapshot (replaces REST polling) --
        try:
            from runtime.api._helpers import build_snapshot as _build_gw_snap
            gw_snap = _build_gw_snap(ctx)
            snapshot["gateway_snapshot"] = gw_snap.model_dump() if hasattr(gw_snap, "model_dump") else gw_snap.dict()
        except Exception:
            snapshot["gateway_snapshot"] = None

        # -- Order ledger stats (replaces REST polling) --
        try:
            from runtime.core.order_ledger import get_order_ledger
            ledger = get_order_ledger()
            snapshot["order_ledger_stats"] = ledger.stats()
            snapshot["order_ledger_recent"] = ledger.recent(limit=12)
        except Exception:
            snapshot["order_ledger_stats"] = None
            snapshot["order_ledger_recent"] = None

        return snapshot

    # ── Persistence ───────────────────────────────────────────────────

    def _persist(self, snapshot: dict[str, Any]) -> None:
        """Write a single snapshot row to SQLite."""
        cols = [
            "ts_utc", "equity_usdt", "free_usdt", "locked_usdt", "margin_usdt",
            "used_weight_1m", "weight_limit_1m",
            "order_count_10s", "order_limit_10s",
            "bots_running", "bots_total",
            "dorothy_running", "dorothy_total",
            "elphaba_running", "elphaba_total",
            "api_fuse_ok", "order_fuse_ok",
            "gateway_running",
        ]
        placeholders = ", ".join("?" for _ in cols)
        col_names = ", ".join(cols)
        values = tuple(snapshot.get(c) for c in cols)

        with self._lock:
            with sqlite3.connect(str(self._db_path), timeout=3) as conn:
                conn.execute(
                    f"INSERT INTO telemetry_snapshots ({col_names}) VALUES ({placeholders})",
                    values,
                )
                conn.commit()
    # ── Rotation ────────────────────────────────────────────────────────

    def _prune_old_snapshots(self, days: int = 7) -> None:
        """Delete telemetry rows older than ``days`` to prevent DB bloat."""
        cutoff = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
        ).isoformat()
        try:
            with self._lock:
                with sqlite3.connect(str(self._db_path), timeout=3) as conn:
                    cur = conn.execute(
                        "DELETE FROM telemetry_snapshots WHERE ts_utc < ?",
                        (cutoff,),
                    )
                    conn.commit()
                    deleted = cur.rowcount
            if deleted > 0:
                _LOG.info(
                    "telemetry_collector: pruned %d rows older than %d days",
                    deleted, days,
                )
        except Exception as e:
            _LOG.warning("telemetry_collector: prune failed: %s", e)

    # ── Query API ─────────────────────────────────────────────────────

    def history(
        self,
        minutes: int = 60,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Return recent telemetry snapshots for charting."""
        cutoff = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes)
        ).isoformat()
        with self._lock:
            with sqlite3.connect(str(self._db_path), timeout=2) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT * FROM telemetry_snapshots
                    WHERE ts_utc >= ?
                    ORDER BY ts_utc ASC
                    LIMIT ?
                    """,
                    (cutoff, limit),
                ).fetchall()
                return [dict(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        """Basic statistics on the telemetry store."""
        with self._lock:
            with sqlite3.connect(str(self._db_path), timeout=2) as conn:
                total = conn.execute("SELECT count(*) FROM telemetry_snapshots").fetchone()[0]
                first = conn.execute("SELECT min(ts_utc) FROM telemetry_snapshots").fetchone()[0]
                last = conn.execute("SELECT max(ts_utc) FROM telemetry_snapshots").fetchone()[0]
                return {
                    "total_rows": total,
                    "first_ts": first,
                    "last_ts": last,
                    "db_path": str(self._db_path),
                }


# ── Singleton ─────────────────────────────────────────────────────────

_collector: Optional[TelemetryCollector] = None


def get_telemetry_collector(data_dir: Optional[Path] = None) -> TelemetryCollector:
    """Get or create the singleton TelemetryCollector."""
    global _collector
    if _collector is None:
        if data_dir is None:
            raise RuntimeError("TelemetryCollector not initialized — provide data_dir")
        _collector = TelemetryCollector(data_dir)
    return _collector
