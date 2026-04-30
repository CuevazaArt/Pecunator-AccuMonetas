"""API-level singleton hub service for Dorothy bots with persistent, resilient execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
import datetime as dt
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import threading
import uuid
from typing import Any, Callable, Optional

from runtime.modules.bots.dorothy import DorothyConfig, DorothyRunner


@dataclass
class _BotRecord:
    bot_id: str
    tag: str
    runner: DorothyRunner
    created_at: str
    desired_running: bool = False


class BotService:
    def __init__(self) -> None:
        self._bots: dict[str, _BotRecord] = {}
        self._default_bot_id: Optional[str] = None
        self._db_path: Optional[Path] = None
        self._db_lock = threading.Lock()
        self._immortal_task: Optional[asyncio.Task[Any]] = None
        self._immortal_stop: Optional[asyncio.Event] = None
        self._immortal_last_reason: dict[str, str] = {}

    def attach_data_dir(self, data_dir: Path) -> None:
        db_path = Path(data_dir) / "dorothy_hub.sqlite"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._init_db()
        self._load_instances_from_db()

    def _init_db(self) -> None:
        if self._db_path is None:
            return
        with self._db_lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dorothy_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts_utc TEXT NOT NULL,
                        bot_id TEXT NOT NULL,
                        tag TEXT NOT NULL,
                        level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        payload_json TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dorothy_instances (
                        bot_id TEXT PRIMARY KEY,
                        tag TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        loop_interval_sec INTEGER NOT NULL,
                        quote_order_qty TEXT NOT NULL,
                        profit_factor TEXT NOT NULL,
                        margin_drop_factor TEXT NOT NULL,
                        qty_decimals INTEGER NOT NULL,
                        price_decimals INTEGER NOT NULL,
                        note TEXT NOT NULL,
                        max_drawdown_pct TEXT NOT NULL DEFAULT '0.20',
                        stop_loss_pct TEXT NOT NULL DEFAULT '0.10',
                        metrics_interval_cycles INTEGER NOT NULL DEFAULT 5,
                        simulated INTEGER NOT NULL,
                        trading_enabled INTEGER NOT NULL,
                        desired_running INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                try:
                    conn.execute("ALTER TABLE dorothy_instances ADD COLUMN max_drawdown_pct TEXT NOT NULL DEFAULT '0.20'")
                except Exception:
                    pass
                try:
                    conn.execute("ALTER TABLE dorothy_instances ADD COLUMN stop_loss_pct TEXT NOT NULL DEFAULT '0.10'")
                except Exception:
                    pass
                try:
                    conn.execute("ALTER TABLE dorothy_instances ADD COLUMN metrics_interval_cycles INTEGER NOT NULL DEFAULT 5")
                except Exception:
                    pass
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dorothy_runtime_state (
                        bot_id TEXT PRIMARY KEY,
                        peak_equity_usdt TEXT,
                        max_drawdown_seen TEXT,
                        cycle_count INTEGER NOT NULL DEFAULT 0,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dorothy_equity_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts_utc TEXT NOT NULL,
                        bot_id TEXT NOT NULL,
                        equity_usdt TEXT NOT NULL,
                        capital_usdt TEXT,
                        drawdown_pct TEXT,
                        peak_equity_usdt TEXT,
                        trading_blocked INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dorothy_metrics_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts_utc TEXT NOT NULL,
                        bot_id TEXT NOT NULL,
                        sharpe TEXT,
                        win_rate TEXT,
                        max_drawdown TEXT,
                        samples INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def _load_instances_from_db(self) -> None:
        if self._db_path is None:
            return
        with self._db_lock:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    """
                    SELECT bot_id, tag, created_at, symbol, loop_interval_sec,
                           quote_order_qty, profit_factor, margin_drop_factor,
                           qty_decimals, price_decimals, note, max_drawdown_pct, stop_loss_pct, metrics_interval_cycles,
                           simulated, trading_enabled, desired_running
                    FROM dorothy_instances
                    ORDER BY created_at ASC
                    """
                ).fetchall()
            finally:
                conn.close()

        for row in rows:
            bot_id = str(row["bot_id"]).strip()
            if not bot_id or bot_id in self._bots:
                continue
            cfg = DorothyConfig(
                preset_id="B",
                symbol=str(row["symbol"]),
                loop_interval_sec=int(row["loop_interval_sec"]),
                quote_order_qty=Decimal(str(row["quote_order_qty"])),
                profit_factor=Decimal(str(row["profit_factor"])),
                margin_drop_factor=Decimal(str(row["margin_drop_factor"])),
                qty_decimals=int(row["qty_decimals"]),
                price_decimals=int(row["price_decimals"]),
                note=str(row["note"] or ""),
                max_drawdown_pct=Decimal(str(row["max_drawdown_pct"] or "0.20")),
                stop_loss_pct=Decimal(str(row["stop_loss_pct"] or "0.10")),
                metrics_interval_cycles=int(row["metrics_interval_cycles"] or 5),
                simulated=bool(int(row["simulated"])),
                trading_enabled=bool(int(row["trading_enabled"])),
            )
            cfg.normalize()
            runner = DorothyRunner(
                self._runner_log_sink(bot_id),
                self._runner_event_sink(bot_id),
            )
            st = self._load_runtime_state(bot_id)
            if st is not None:
                runner.restore_risk_state(
                    peak_equity_usdt=st.get("peak_equity_usdt"),
                    max_drawdown_seen=st.get("max_drawdown_seen"),
                    cycle_count=st.get("cycle_count"),
                )
            runner.apply_config(cfg)
            rec = _BotRecord(
                bot_id=bot_id,
                tag=str(row["tag"] or "Dorothy").strip() or "Dorothy",
                runner=runner,
                created_at=str(row["created_at"]),
                desired_running=bool(int(row["desired_running"])),
            )
            self._bots[bot_id] = rec
            if self._default_bot_id is None:
                self._default_bot_id = bot_id

    def _save_instance(self, rec: _BotRecord) -> None:
        if self._db_path is None:
            return
        cfg = rec.runner.config
        with self._db_lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                conn.execute(
                    """
                    INSERT INTO dorothy_instances (
                        bot_id, tag, created_at, symbol, loop_interval_sec,
                        quote_order_qty, profit_factor, margin_drop_factor,
                        qty_decimals, price_decimals, note, max_drawdown_pct, stop_loss_pct, metrics_interval_cycles,
                        simulated, trading_enabled, desired_running
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(bot_id) DO UPDATE SET
                        tag=excluded.tag,
                        created_at=excluded.created_at,
                        symbol=excluded.symbol,
                        loop_interval_sec=excluded.loop_interval_sec,
                        quote_order_qty=excluded.quote_order_qty,
                        profit_factor=excluded.profit_factor,
                        margin_drop_factor=excluded.margin_drop_factor,
                        qty_decimals=excluded.qty_decimals,
                        price_decimals=excluded.price_decimals,
                        note=excluded.note,
                        max_drawdown_pct=excluded.max_drawdown_pct,
                        stop_loss_pct=excluded.stop_loss_pct,
                        metrics_interval_cycles=excluded.metrics_interval_cycles,
                        simulated=excluded.simulated,
                        trading_enabled=excluded.trading_enabled,
                        desired_running=excluded.desired_running
                    """,
                    (
                        rec.bot_id,
                        rec.tag,
                        rec.created_at,
                        cfg.symbol,
                        int(cfg.loop_interval_sec),
                        str(cfg.quote_order_qty),
                        str(cfg.profit_factor),
                        str(cfg.margin_drop_factor),
                        int(cfg.qty_decimals),
                        int(cfg.price_decimals),
                        str(cfg.note or ""),
                        str(cfg.max_drawdown_pct),
                        str(cfg.stop_loss_pct),
                        int(cfg.metrics_interval_cycles),
                        1 if cfg.simulated else 0,
                        1 if cfg.trading_enabled else 0,
                        1 if rec.desired_running else 0,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def _delete_instance(self, bot_id: str) -> None:
        if self._db_path is None:
            return
        with self._db_lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                conn.execute("DELETE FROM dorothy_instances WHERE bot_id = ?", (bot_id,))
                conn.commit()
            finally:
                conn.close()

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
        with self._db_lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                conn.execute(
                    """
                    INSERT INTO dorothy_logs (ts_utc, bot_id, tag, level, message, payload_json)
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

    def _load_runtime_state(self, bot_id: str) -> Optional[dict[str, Any]]:
        if self._db_path is None:
            return None
        with self._db_lock:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    """
                    SELECT peak_equity_usdt, max_drawdown_seen, cycle_count
                    FROM dorothy_runtime_state
                    WHERE bot_id = ?
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

    def _persist_equity_snapshot(self, bot_id: str, payload: dict[str, Any]) -> None:
        if self._db_path is None:
            return
        ts = dt.datetime.now(dt.timezone.utc).isoformat()
        with self._db_lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                conn.execute(
                    """
                    INSERT INTO dorothy_equity_snapshots (
                        ts_utc, bot_id, equity_usdt, capital_usdt, drawdown_pct, peak_equity_usdt, trading_blocked
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts,
                        bot_id,
                        str(payload.get("equity_usdt", "0")),
                        str(payload.get("capital_usdt", "0")),
                        str(payload.get("drawdown_pct", "0")),
                        str(payload.get("peak_equity_usdt", "0")),
                        1 if payload.get("trading_blocked") else 0,
                    ),
                )
                row = conn.execute(
                    "SELECT cycle_count FROM dorothy_runtime_state WHERE bot_id = ?",
                    (bot_id,),
                ).fetchone()
                cycle_count = int(row[0]) if row is not None and row[0] is not None else 0
                conn.execute(
                    """
                    INSERT INTO dorothy_runtime_state (bot_id, peak_equity_usdt, max_drawdown_seen, cycle_count, updated_at)
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
        with self._db_lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                conn.execute(
                    """
                    INSERT INTO dorothy_metrics_log (ts_utc, bot_id, sharpe, win_rate, max_drawdown, samples)
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

    def _runner_log_sink(self, bot_id: str) -> Callable[[str], None]:
        def _sink(msg: str) -> None:
            rec = self._bots.get(bot_id)
            tag = rec.tag if rec is not None else "-"
            self._write_log(bot_id, tag, "INFO", msg)

        return _sink

    def _runner_event_sink(
        self,
        bot_id: str,
    ) -> Callable[[str, str, Optional[dict[str, Any]]], None]:
        def _sink(level: str, msg: str, payload: Optional[dict[str, Any]] = None) -> None:
            rec = self._bots.get(bot_id)
            tag = rec.tag if rec is not None else "-"
            self._write_log(bot_id, tag, level or "INFO", msg, payload)
            if isinstance(payload, dict):
                if msg == "bot:equity_snapshot":
                    self._persist_equity_snapshot(bot_id, payload)
                elif msg == "bot:metrics":
                    self._persist_metrics(bot_id, payload)

        return _sink

    def _record_payload(self, rec: _BotRecord) -> dict[str, Any]:
        cfg = rec.runner.config
        return {
            "bot_id": rec.bot_id,
            "tag": rec.tag,
            "created_at": rec.created_at,
            "running": rec.runner.running,
            "desired_running": rec.desired_running,
            "preset_id": cfg.preset_id,
            "symbol": cfg.symbol,
            "simulated": cfg.simulated,
            "trading_enabled": cfg.trading_enabled,
            "loop_interval_sec": cfg.loop_interval_sec,
            "quote_order_qty": str(cfg.quote_order_qty),
            "profit_factor": str(cfg.profit_factor),
            "margin_drop_factor": str(cfg.margin_drop_factor),
            "qty_decimals": cfg.qty_decimals,
            "price_decimals": cfg.price_decimals,
            "note": cfg.note,
            "max_drawdown_pct": str(cfg.max_drawdown_pct),
            "stop_loss_pct": str(cfg.stop_loss_pct),
            "metrics_interval_cycles": cfg.metrics_interval_cycles,
            "last_cycle_ts": rec.runner.last_cycle_ts,
            "last_error": rec.runner.last_error,
            "last_report": rec.runner.last_report,
        }

    def _default_bot(self) -> _BotRecord:
        if self._default_bot_id and self._default_bot_id in self._bots:
            return self._bots[self._default_bot_id]
        payload = self.create_instance(tag="Dorothy default")
        self._default_bot_id = payload["bot_id"]
        return self._bots[self._default_bot_id]

    @property
    def runner(self) -> DorothyRunner:
        return self._default_bot().runner

    def create_instance(
        self,
        *,
        tag: str,
        bot_id: Optional[str] = None,
        symbol: str = "XRPUSDT",
        loop_interval_sec: int = 450,
        quote_order_qty: str = "8",
        profit_factor: str = "0.05",
        margin_drop_factor: str = "0.004",
        qty_decimals: int = 8,
        price_decimals: int = 4,
        note: str = "",
        max_drawdown_pct: str = "0.20",
        stop_loss_pct: str = "0.10",
        metrics_interval_cycles: int = 5,
        simulated: bool = True,
        trading_enabled: bool = False,
    ) -> dict[str, Any]:
        bot_id_norm = (bot_id or "").strip() or f"dorothy-{uuid.uuid4().hex[:8]}"
        if bot_id_norm in self._bots:
            raise ValueError(f"Bot id already exists: {bot_id_norm}")
        cfg = DorothyConfig(
            preset_id="B",
            symbol=symbol,
            loop_interval_sec=loop_interval_sec,
            quote_order_qty=Decimal(str(quote_order_qty)),
            profit_factor=Decimal(str(profit_factor)),
            margin_drop_factor=Decimal(str(margin_drop_factor)),
            qty_decimals=qty_decimals,
            price_decimals=price_decimals,
            note=note,
            max_drawdown_pct=Decimal(str(max_drawdown_pct)),
            stop_loss_pct=Decimal(str(stop_loss_pct)),
            metrics_interval_cycles=int(metrics_interval_cycles),
            simulated=simulated,
            trading_enabled=trading_enabled,
        )
        cfg.normalize()
        runner = DorothyRunner(
            self._runner_log_sink(bot_id_norm),
            self._runner_event_sink(bot_id_norm),
        )
        runner.apply_config(cfg)
        rec = _BotRecord(
            bot_id=bot_id_norm,
            tag=(tag or "Dorothy").strip(),
            runner=runner,
            created_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            desired_running=False,
        )
        self._bots[bot_id_norm] = rec
        self._save_instance(rec)
        if self._default_bot_id is None:
            self._default_bot_id = bot_id_norm
        payload = self._record_payload(rec)
        self._write_log(bot_id_norm, rec.tag, "SYSTEM", "bot_created", payload)
        return payload

    def list_instances(self) -> list[dict[str, Any]]:
        return [
            self._record_payload(v)
            for _, v in sorted(self._bots.items(), key=lambda x: x[1].created_at)
        ]

    def hub_stats(self) -> dict[str, int]:
        total = len(self._bots)
        running = sum(1 for r in self._bots.values() if r.runner.running)
        desired = sum(1 for r in self._bots.values() if r.desired_running)
        return {
            "hub_bots_total": total,
            "hub_bots_running": running,
            "hub_bots_desired_running": desired,
        }

    def status_instance(self, bot_id: str) -> dict[str, Any]:
        rec = self._bots.get(bot_id)
        if rec is None:
            raise KeyError(bot_id)
        return self._record_payload(rec)

    def update_instance(
        self,
        bot_id: str,
        *,
        tag: Optional[str] = None,
        symbol: Optional[str] = None,
        loop_interval_sec: Optional[int] = None,
        quote_order_qty: Optional[str] = None,
        profit_factor: Optional[str] = None,
        margin_drop_factor: Optional[str] = None,
        qty_decimals: Optional[int] = None,
        price_decimals: Optional[int] = None,
        note: Optional[str] = None,
        max_drawdown_pct: Optional[str] = None,
        stop_loss_pct: Optional[str] = None,
        metrics_interval_cycles: Optional[int] = None,
        simulated: Optional[bool] = None,
        trading_enabled: Optional[bool] = None,
    ) -> dict[str, Any]:
        rec = self._bots.get(bot_id)
        if rec is None:
            raise KeyError(bot_id)
        cfg = replace(rec.runner.config)
        if symbol is not None:
            cfg.symbol = symbol
        if loop_interval_sec is not None:
            cfg.loop_interval_sec = loop_interval_sec
        if quote_order_qty is not None:
            cfg.quote_order_qty = Decimal(str(quote_order_qty))
        if profit_factor is not None:
            cfg.profit_factor = Decimal(str(profit_factor))
        if margin_drop_factor is not None:
            cfg.margin_drop_factor = Decimal(str(margin_drop_factor))
        if qty_decimals is not None:
            cfg.qty_decimals = qty_decimals
        if price_decimals is not None:
            cfg.price_decimals = price_decimals
        if note is not None:
            cfg.note = note
        if max_drawdown_pct is not None:
            cfg.max_drawdown_pct = Decimal(str(max_drawdown_pct))
        if stop_loss_pct is not None:
            cfg.stop_loss_pct = Decimal(str(stop_loss_pct))
        if metrics_interval_cycles is not None:
            cfg.metrics_interval_cycles = int(metrics_interval_cycles)
        if simulated is not None:
            cfg.simulated = simulated
        if trading_enabled is not None:
            cfg.trading_enabled = trading_enabled
        cfg.normalize()
        rec.runner.apply_config(cfg)
        if tag is not None and tag.strip():
            rec.tag = tag.strip()
        self._save_instance(rec)
        payload = self._record_payload(rec)
        self._write_log(bot_id, rec.tag, "SYSTEM", "bot_updated", payload)
        return payload

    async def _start_runner(self, rec: _BotRecord, api_key: str, api_secret: str) -> None:
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
            self._write_log(
                bot_id,
                rec.tag,
                "WARNING",
                f"bot_start_failed: {e}",
                {"error": str(e), "desired_running": True},
            )
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
        self._delete_instance(bot_id)
        del self._bots[bot_id]
        if self._default_bot_id == bot_id:
            self._default_bot_id = next(iter(self._bots.keys()), None)

    async def stop_all(self) -> None:
        for rec in self._bots.values():
            try:
                await rec.runner.stop()
            except Exception:
                pass

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
                        self._write_log(
                            rec.bot_id,
                            rec.tag,
                            "WARNING",
                            f"immortal: credential_resolver_failed {e}",
                        )
                        self._immortal_last_reason[rec.bot_id] = reason
                    continue
                if not pair:
                    reason = "waiting_credentials"
                    if self._immortal_last_reason.get(rec.bot_id) != reason:
                        self._write_log(
                            rec.bot_id,
                            rec.tag,
                            "WARNING",
                            "immortal: waiting for credentials",
                        )
                        self._immortal_last_reason[rec.bot_id] = reason
                    continue
                try:
                    await self._start_runner(rec, pair[0], pair[1])
                    self._write_log(
                        rec.bot_id,
                        rec.tag,
                        "SYSTEM",
                        "immortal: bot_resumed",
                        self._record_payload(rec),
                    )
                    self._immortal_last_reason.pop(rec.bot_id, None)
                except Exception as e:
                    reason = f"resume_failed:{type(e).__name__}"
                    if self._immortal_last_reason.get(rec.bot_id) != reason:
                        self._write_log(
                            rec.bot_id,
                            rec.tag,
                            "WARNING",
                            f"immortal: resume_failed {e}",
                        )
                        self._immortal_last_reason[rec.bot_id] = reason
            try:
                await asyncio.wait_for(self._immortal_stop.wait(), timeout=interval_sec)
            except asyncio.TimeoutError:
                pass

    def get_logs(self, bot_id: str, limit: int = 200) -> list[dict[str, Any]]:
        if self._db_path is None:
            return []
        if bot_id not in self._bots:
            raise KeyError(bot_id)
        n = max(1, min(int(limit), 1000))
        with self._db_lock:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    """
                    SELECT ts_utc, bot_id, tag, level, message, payload_json
                    FROM dorothy_logs
                    WHERE bot_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (bot_id, n),
                ).fetchall()
            finally:
                conn.close()
        out: list[dict[str, Any]] = []
        for row in reversed(rows):
            payload_raw = row["payload_json"]
            out.append(
                {
                    "ts_utc": row["ts_utc"],
                    "bot_id": row["bot_id"],
                    "tag": row["tag"],
                    "level": row["level"],
                    "message": row["message"],
                    "payload": json.loads(payload_raw) if payload_raw else None,
                }
            )
        return out

    # Compatibility layer for pre-hub API endpoints
    def get_config(self) -> DorothyConfig:
        return replace(self._default_bot().runner.config)

    def set_config(
        self,
        *,
        symbol: str,
        loop_interval_sec: int,
        quote_order_qty: str,
        profit_factor: str,
        margin_drop_factor: str,
        qty_decimals: int,
        price_decimals: int,
        note: str,
        simulated: bool,
        trading_enabled: bool,
    ) -> DorothyConfig:
        rec = self._default_bot()
        payload = self.update_instance(
            rec.bot_id,
            symbol=symbol,
            loop_interval_sec=loop_interval_sec,
            quote_order_qty=quote_order_qty,
            profit_factor=profit_factor,
            margin_drop_factor=margin_drop_factor,
            qty_decimals=qty_decimals,
            price_decimals=price_decimals,
            note=note,
            simulated=simulated,
            trading_enabled=trading_enabled,
        )
        cfg = DorothyConfig(
            preset_id=payload["preset_id"],
            symbol=payload["symbol"],
            loop_interval_sec=payload["loop_interval_sec"],
            quote_order_qty=Decimal(payload["quote_order_qty"]),
            profit_factor=Decimal(payload["profit_factor"]),
            margin_drop_factor=Decimal(payload["margin_drop_factor"]),
            qty_decimals=payload["qty_decimals"],
            price_decimals=payload["price_decimals"],
            note=payload.get("note", ""),
            simulated=payload["simulated"],
            trading_enabled=payload["trading_enabled"],
        )
        return replace(cfg)

    def status_payload(self) -> dict[str, Any]:
        rec = self._default_bot()
        p = self._record_payload(rec)
        return {
            "running": p["running"],
            "preset_id": p["preset_id"],
            "symbol": p["symbol"],
            "simulated": p["simulated"],
            "trading_enabled": p["trading_enabled"],
            "loop_interval_sec": p["loop_interval_sec"],
            "last_cycle_ts": p["last_cycle_ts"],
            "last_error": p["last_error"],
            "last_report": p["last_report"],
        }

    def mark_run_once(self, report: dict[str, Any], error: str | None = None, bot_id: str | None = None) -> None:
        rec = self._bots.get(bot_id) if bot_id else None
        if rec is None:
            rec = self._default_bot()
        rec.runner._last_report = dict(report)  # noqa: SLF001
        rec.runner._last_error = error  # noqa: SLF001
        rec.runner._last_cycle_ts = dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: SLF001
