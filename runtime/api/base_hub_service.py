"""Generic base class for Dorothy / Masha / Thusnelda hub services.

Each concrete service only needs to:

1. Inherit ``BaseHubService``.
2. Set the class-level ``HUB_CONFIG`` dict.
3. Override ``_make_runner(log_sink, event_sink)`` to return the right runner.
4. Override ``_make_config(**kwargs)`` to build the bot-specific config dataclass.
5. Override ``_record_extra(runner)`` to append bot-specific fields to the
   payload dict.
6. Override ``_save_instance(rec)`` / ``_load_instances_from_db()`` if the DB
   schema has different columns (the Masha/Thusnelda tables differ from Dorothy).

All immortality logic, WAL-backed SQLite I/O, log sinks, equity persistence,
and metrics persistence live here — written once.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from runtime.core.db_util import open_db
from runtime.core.security_util import sanitize_log_message

import logging

_LOG = logging.getLogger("pecunator.hub_base")


# ---------------------------------------------------------------------------
# Generic bot record (hold onto runner + metadata)
# ---------------------------------------------------------------------------

@dataclass
class BotRecord:
    bot_id: str
    tag: str
    runner: Any          # Typed concretely in subclasses via generics if needed
    created_at: str
    desired_running: bool = False


# ---------------------------------------------------------------------------
# BaseHubService
# ---------------------------------------------------------------------------

class BaseHubService(ABC):
    """Abstract hub service.  Subclasses configure via ``HUB_CONFIG``."""

    # --- Override in subclass -----------------------------------------------
    #: Keys: db_filename, table_prefix, metrics_msg, equity_msg
    HUB_CONFIG: dict[str, str] = {}

    # -------------------------------------------------------------------------

    def __init__(self) -> None:
        self._bots: dict[str, BotRecord] = {}
        self._default_bot_id: Optional[str] = None
        self._db_path: Optional[Path] = None
        self._db_lock = threading.Lock()
        self._immortal_task: Optional[asyncio.Task[Any]] = None
        self._immortal_stop: Optional[asyncio.Event] = None
        self._immortal_last_reason: dict[str, str] = {}

    # --- Abstract interface --------------------------------------------------

    @abstractmethod
    def _make_runner(
        self,
        log_sink: Callable[[str], None],
        event_sink: Callable[[str, str, Optional[dict[str, Any]]], None],
    ) -> Any:
        """Construct and return a new bot runner instance."""

    @abstractmethod
    def _make_config(self, **kwargs: Any) -> Any:
        """Construct and return a bot config dataclass from keyword args."""

    @abstractmethod
    def _record_extra(self, runner: Any) -> dict[str, Any]:
        """Return bot-specific fields to merge into the record payload dict."""

    @abstractmethod
    def _save_instance(self, rec: BotRecord) -> None:
        """Persist the instance to the DB (schema-specific)."""

    @abstractmethod
    def _load_instances_from_db(self) -> None:
        """Reload all instances from the DB on startup."""

    # --- DB helpers ----------------------------------------------------------

    def _db_connect(self) -> Any:
        assert self._db_path is not None
        return open_db(self._db_path)

    def _table(self, suffix: str) -> str:
        return f"{self.HUB_CONFIG['table_prefix']}_{suffix}"

    def attach_data_dir(self, data_dir: Path) -> None:
        db_path = Path(data_dir) / self.HUB_CONFIG["db_filename"]
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._init_db()
        self._load_instances_from_db()

    def _init_db(self) -> None:
        """Create base tables common to all hub services."""
        if self._db_path is None:
            return
        pfx = self.HUB_CONFIG["table_prefix"]
        with self._db_lock:
            conn = self._db_connect()
            try:
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {pfx}_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts_utc TEXT NOT NULL,
                        bot_id TEXT NOT NULL,
                        tag TEXT NOT NULL,
                        level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        payload_json TEXT
                    )
                """)
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {pfx}_runtime_state (
                        bot_id TEXT PRIMARY KEY,
                        peak_equity_usdt TEXT,
                        max_drawdown_seen TEXT,
                        cycle_count INTEGER NOT NULL DEFAULT 0,
                        updated_at TEXT NOT NULL
                    )
                """)
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {pfx}_equity_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts_utc TEXT NOT NULL,
                        bot_id TEXT NOT NULL,
                        equity_usdt TEXT NOT NULL,
                        capital_usdt TEXT,
                        drawdown_pct TEXT,
                        peak_equity_usdt TEXT,
                        trading_blocked INTEGER NOT NULL DEFAULT 0
                    )
                """)
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {pfx}_metrics_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts_utc TEXT NOT NULL,
                        bot_id TEXT NOT NULL,
                        sharpe TEXT,
                        win_rate TEXT,
                        max_drawdown TEXT,
                        samples INTEGER NOT NULL DEFAULT 0
                    )
                """)
                conn.commit()
            finally:
                conn.close()

    # --- Log / event sinks ---------------------------------------------------

    def _write_log(
        self,
        bot_id: str,
        tag: str,
        level: str,
        message: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        if self._db_path is None:
            return
        pfx = self.HUB_CONFIG["table_prefix"]
        with self._db_lock:
            conn = self._db_connect()
            try:
                conn.execute(
                    f"""
                    INSERT INTO {pfx}_logs (ts_utc, bot_id, tag, level, message, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dt.datetime.now(dt.timezone.utc).isoformat(),
                        bot_id,
                        tag,
                        level,
                        message,
                        json.dumps(payload) if payload is not None else None,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def _runner_log_sink(self, bot_id: str) -> Callable[[str], None]:
        def _sink(msg: str) -> None:
            rec = self._bots.get(bot_id)
            tag = rec.tag if rec is not None else "-"
            self._write_log(bot_id, tag, "INFO", msg)
        return _sink

    def _runner_event_sink(
        self, bot_id: str
    ) -> Callable[[str, str, Optional[dict[str, Any]]], None]:
        equity_msg = self.HUB_CONFIG.get("equity_msg", "bot:equity_snapshot")
        metrics_msg = self.HUB_CONFIG.get("metrics_msg", "bot:metrics")

        def _sink(level: str, msg: str, payload: Optional[dict[str, Any]] = None) -> None:
            rec = self._bots.get(bot_id)
            tag = rec.tag if rec is not None else "-"
            self._write_log(bot_id, tag, level or "INFO", msg, payload)
            if isinstance(payload, dict):
                if msg == equity_msg:
                    self._persist_equity_snapshot(bot_id, payload)
                elif msg == metrics_msg:
                    self._persist_metrics(bot_id, payload)
        return _sink

    # --- Equity / metrics persistence ----------------------------------------

    def _persist_equity_snapshot(self, bot_id: str, payload: dict[str, Any]) -> None:
        if self._db_path is None:
            return
        pfx = self.HUB_CONFIG["table_prefix"]
        ts = dt.datetime.now(dt.timezone.utc).isoformat()
        with self._db_lock:
            conn = self._db_connect()
            try:
                conn.execute(
                    f"""
                    INSERT INTO {pfx}_equity_snapshots
                        (ts_utc, bot_id, equity_usdt, capital_usdt, drawdown_pct, peak_equity_usdt, trading_blocked)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts, bot_id,
                        str(payload.get("equity_usdt", "0")),
                        str(payload.get("capital_usdt", "0")),
                        str(payload.get("drawdown_pct", "0")),
                        str(payload.get("peak_equity_usdt", "0")),
                        1 if payload.get("trading_blocked") else 0,
                    ),
                )
                row = conn.execute(
                    f"SELECT cycle_count FROM {pfx}_runtime_state WHERE bot_id = ?",
                    (bot_id,),
                ).fetchone()
                cycle_count = int(row[0]) if row and row[0] is not None else 0
                conn.execute(
                    f"""
                    INSERT INTO {pfx}_runtime_state
                        (bot_id, peak_equity_usdt, max_drawdown_seen, cycle_count, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(bot_id) DO UPDATE SET
                        peak_equity_usdt=excluded.peak_equity_usdt,
                        max_drawdown_seen=excluded.max_drawdown_seen,
                        cycle_count=excluded.cycle_count,
                        updated_at=excluded.updated_at
                    """,
                    (
                        bot_id,
                        str(payload.get("peak_equity_usdt", "0")),
                        str(payload.get("drawdown_pct", "0")),
                        cycle_count + 1,
                        ts,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def _persist_metrics(self, bot_id: str, payload: dict[str, Any]) -> None:
        if self._db_path is None:
            return
        pfx = self.HUB_CONFIG["table_prefix"]
        with self._db_lock:
            conn = self._db_connect()
            try:
                conn.execute(
                    f"""
                    INSERT INTO {pfx}_metrics_log
                        (ts_utc, bot_id, sharpe, win_rate, max_drawdown, samples)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dt.datetime.now(dt.timezone.utc).isoformat(),
                        bot_id,
                        str(payload.get("sharpe", "0")),
                        str(payload.get("win_rate", "0")),
                        str(payload.get("max_drawdown", "0")),
                        int(payload.get("samples", 0) or 0),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def _load_runtime_state(self, bot_id: str) -> Optional[dict[str, Any]]:
        if self._db_path is None:
            return None
        pfx = self.HUB_CONFIG["table_prefix"]
        with self._db_lock:
            conn = self._db_connect()
            conn.row_factory = __import__("sqlite3").Row
            try:
                row = conn.execute(
                    f"""
                    SELECT peak_equity_usdt, max_drawdown_seen, cycle_count
                    FROM {pfx}_runtime_state WHERE bot_id = ?
                    """,
                    (bot_id,),
                ).fetchone()
            finally:
                conn.close()
        if row is None:
            return None
        return {
            "peak_equity_usdt": row["peak_equity_usdt"],
            "max_drawdown_seen": row["max_drawdown_seen"],
            "cycle_count": int(row["cycle_count"] or 0),
        }

    # --- Record payload ------------------------------------------------------

    def _record_payload(self, rec: BotRecord) -> dict[str, Any]:
        base = {
            "bot_id": rec.bot_id,
            "tag": rec.tag,
            "created_at": rec.created_at,
            "running": rec.runner.running,
            "desired_running": rec.desired_running,
            "last_cycle_ts": rec.runner.last_cycle_ts,
            "last_error": rec.runner.last_error,
            "last_report": rec.runner.last_report,
        }
        base.update(self._record_extra(rec.runner))
        return base

    # --- CRUD ----------------------------------------------------------------

    def list_instances(self) -> list[dict[str, Any]]:
        return [
            self._record_payload(v)
            for _, v in sorted(self._bots.items(), key=lambda x: x[1].created_at)
        ]

    def hub_stats(self) -> dict[str, int]:
        total = len(self._bots)
        running = sum(1 for r in self._bots.values() if r.runner.running)
        desired = sum(1 for r in self._bots.values() if r.desired_running)
        return {"hub_bots_total": total, "hub_bots_running": running, "hub_bots_desired_running": desired}

    def status_instance(self, bot_id: str) -> dict[str, Any]:
        rec = self._bots.get(bot_id)
        if rec is None:
            raise KeyError(bot_id)
        return self._record_payload(rec)

    async def _start_runner(self, rec: BotRecord, api_key: str, api_secret: str) -> None:
        rec.runner.set_credentials(api_key, api_secret)
        await rec.runner.sync_time()
        await rec.runner.start()

    async def start_instance(self, bot_id: str, api_key: str, api_secret: str) -> dict[str, Any]:
        rec = self._bots.get(bot_id)
        if rec is None:
            raise KeyError(bot_id)
        rec.desired_running = True
        self._save_instance(rec)
        try:
            await self._start_runner(rec, api_key, api_secret)
        except Exception as e:
            self._write_log(bot_id, rec.tag, "WARNING", f"bot_start_failed: {e}", {"error": str(e)})
            raise
        payload = self._record_payload(rec)
        self._write_log(bot_id, rec.tag, "SYSTEM", "bot_started", payload)
        return payload

    async def run_once_instance(self, bot_id: str, api_key: str, api_secret: str) -> dict[str, Any]:
        rec = self._bots.get(bot_id)
        if rec is None:
            raise KeyError(bot_id)
        rec.runner.set_credentials(api_key, api_secret)
        await rec.runner.sync_time()
        rep = await rec.runner.run_once()
        self.mark_run_once(rep, error=None, bot_id=bot_id)
        payload = self._record_payload(rec)
        self._write_log(bot_id, rec.tag, "SYSTEM", "bot_run_once", payload)
        return payload

    async def stop_instance(self, bot_id: str) -> dict[str, Any]:
        rec = self._bots.get(bot_id)
        if rec is None:
            raise KeyError(bot_id)
        rec.desired_running = False
        self._save_instance(rec)
        await rec.runner.stop()
        payload = self._record_payload(rec)
        self._write_log(bot_id, rec.tag, "SYSTEM", "bot_stopped", payload)
        return payload

    async def delete_instance(self, bot_id: str) -> None:
        rec = self._bots.get(bot_id)
        if rec is None:
            raise KeyError(bot_id)
        await rec.runner.stop()
        self._write_log(bot_id, rec.tag, "SYSTEM", "bot_deleted")
        self._delete_from_db(bot_id)
        del self._bots[bot_id]
        if self._default_bot_id == bot_id:
            self._default_bot_id = next(iter(self._bots.keys()), None)

    def _delete_from_db(self, bot_id: str) -> None:
        if self._db_path is None:
            return
        pfx = self.HUB_CONFIG["table_prefix"]
        with self._db_lock:
            conn = self._db_connect()
            try:
                conn.execute(f"DELETE FROM {pfx}_instances WHERE bot_id = ?", (bot_id,))
                conn.commit()
            finally:
                conn.close()

    async def stop_all(self) -> None:
        for rec in self._bots.values():
            try:
                await rec.runner.stop()
            except Exception:
                pass

    def mark_run_once(
        self,
        report: dict[str, Any],
        *,
        error: Optional[str] = None,
        bot_id: Optional[str] = None,
    ) -> None:
        """Hook for run_once telemetry.  No-op by default; override as needed."""

    def get_logs(self, bot_id: str, limit: int = 200) -> list[dict[str, Any]]:
        if self._db_path is None:
            return []
        if bot_id not in self._bots:
            raise KeyError(bot_id)
        pfx = self.HUB_CONFIG["table_prefix"]
        n = max(1, min(int(limit), 1000))
        with self._db_lock:
            conn = self._db_connect()
            conn.row_factory = __import__("sqlite3").Row
            try:
                rows = conn.execute(
                    f"""
                    SELECT ts_utc, bot_id, tag, level, message, payload_json
                    FROM {pfx}_logs WHERE bot_id = ?
                    ORDER BY id DESC LIMIT ?
                    """,
                    (bot_id, n),
                ).fetchall()
            finally:
                conn.close()
        out: list[dict[str, Any]] = []
        for row in reversed(rows):
            payload_raw = row["payload_json"]
            out.append({
                "ts_utc": row["ts_utc"],
                "bot_id": row["bot_id"],
                "tag": row["tag"],
                "level": row["level"],
                "message": row["message"],
                "payload": json.loads(payload_raw) if payload_raw else None,
            })
        return out

    # --- Immortality ---------------------------------------------------------

    def start_immortality(
        self,
        credential_resolver: Callable[[], tuple[str, str] | None],
        interval_sec: float = 5.0,
    ) -> None:
        if self._immortal_task is not None and not self._immortal_task.done():
            return
        self._immortal_stop = asyncio.Event()
        self._immortal_task = asyncio.create_task(
            self._immortal_loop(credential_resolver, interval_sec=max(1.0, float(interval_sec)))
        )

    async def stop_immortality(self) -> None:
        if self._immortal_stop is not None:
            self._immortal_stop.set()
        task = self._immortal_task
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._immortal_task = None
        self._immortal_stop = None
        self._immortal_last_reason.clear()

    async def _immortal_loop(
        self,
        credential_resolver: Callable[[], tuple[str, str] | None],
        interval_sec: float,
    ) -> None:
        while self._immortal_stop is not None and not self._immortal_stop.is_set():
            for rec in list(self._bots.values()):
                if not rec.desired_running or rec.runner.running:
                    continue
                try:
                    pair = credential_resolver()
                except Exception as e:
                    reason = f"resolver_failed:{type(e).__name__}"
                    if self._immortal_last_reason.get(rec.bot_id) != reason:
                        self._write_log(rec.bot_id, rec.tag, "WARNING",
                                        f"immortal: credential_resolver_failed {e}")
                        self._immortal_last_reason[rec.bot_id] = reason
                    continue
                if not pair:
                    reason = "waiting_credentials"
                    if self._immortal_last_reason.get(rec.bot_id) != reason:
                        self._write_log(rec.bot_id, rec.tag, "WARNING",
                                        "immortal: waiting for credentials")
                        self._immortal_last_reason[rec.bot_id] = reason
                    continue
                try:
                    await self._start_runner(rec, pair[0], pair[1])
                    self._write_log(rec.bot_id, rec.tag, "SYSTEM", "immortal: bot_resumed",
                                    self._record_payload(rec))
                    self._immortal_last_reason.pop(rec.bot_id, None)
                except Exception as e:
                    reason = f"resume_failed:{type(e).__name__}"
                    if self._immortal_last_reason.get(rec.bot_id) != reason:
                        self._write_log(rec.bot_id, rec.tag, "WARNING",
                                        f"immortal: resume_failed {e}")
                        self._immortal_last_reason[rec.bot_id] = reason
            try:
                await asyncio.wait_for(self._immortal_stop.wait(), timeout=interval_sec)
            except asyncio.TimeoutError:
                pass
