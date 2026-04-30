"""API-level singleton hub service for Thusnelda1.0 bots."""

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

from runtime.modules.bots.thusnelda import ThusneldaConfig, ThusneldaRunner


@dataclass
class _ThusneldaRecord:
    bot_id: str
    tag: str
    runner: ThusneldaRunner
    created_at: str
    desired_running: bool = False


class ThusneldaService:
    def __init__(self) -> None:
        self._bots: dict[str, _ThusneldaRecord] = {}
        self._db_path: Optional[Path] = None
        self._db_lock = threading.Lock()
        self._immortal_task: Optional[asyncio.Task[Any]] = None
        self._immortal_stop: Optional[asyncio.Event] = None
        self._immortal_last_reason: dict[str, str] = {}

    def attach_data_dir(self, data_dir: Path) -> None:
        db_path = Path(data_dir) / "thusnelda_hub.sqlite"
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
                    CREATE TABLE IF NOT EXISTS thusnelda_logs (
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
                    CREATE TABLE IF NOT EXISTS thusnelda_instances (
                        bot_id TEXT PRIMARY KEY,
                        tag TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        symbols_csv TEXT NOT NULL,
                        loop_interval_sec INTEGER NOT NULL,
                        between_symbol_sec INTEGER NOT NULL,
                        quote_order_qty_modulo TEXT NOT NULL,
                        factor_multiplication TEXT NOT NULL,
                        meta_equity_usdt TEXT NOT NULL,
                        reference_ts_iso TEXT NOT NULL,
                        qty_decimals INTEGER NOT NULL,
                        note TEXT NOT NULL,
                        max_drawdown_pct TEXT NOT NULL DEFAULT '0.25',
                        stop_loss_pct TEXT NOT NULL DEFAULT '0.20',
                        metrics_interval_cycles INTEGER NOT NULL DEFAULT 3,
                        simulated INTEGER NOT NULL,
                        trading_enabled INTEGER NOT NULL,
                        desired_running INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                try:
                    conn.execute("ALTER TABLE thusnelda_instances ADD COLUMN max_drawdown_pct TEXT NOT NULL DEFAULT '0.25'")
                except Exception:
                    pass
                try:
                    conn.execute("ALTER TABLE thusnelda_instances ADD COLUMN stop_loss_pct TEXT NOT NULL DEFAULT '0.20'")
                except Exception:
                    pass
                try:
                    conn.execute("ALTER TABLE thusnelda_instances ADD COLUMN metrics_interval_cycles INTEGER NOT NULL DEFAULT 3")
                except Exception:
                    pass
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS thusnelda_runtime_state (
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
                    CREATE TABLE IF NOT EXISTS thusnelda_equity_snapshots (
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
                    CREATE TABLE IF NOT EXISTS thusnelda_metrics_log (
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
                    SELECT bot_id, tag, created_at, symbols_csv, loop_interval_sec, between_symbol_sec,
                           quote_order_qty_modulo, factor_multiplication, meta_equity_usdt,
                           reference_ts_iso, qty_decimals, note, max_drawdown_pct, stop_loss_pct, metrics_interval_cycles, simulated, trading_enabled, desired_running
                    FROM thusnelda_instances
                    ORDER BY created_at ASC
                    """
                ).fetchall()
            finally:
                conn.close()
        for row in rows:
            bot_id = str(row["bot_id"]).strip()
            if not bot_id or bot_id in self._bots:
                continue
            cfg = ThusneldaConfig(
                preset_id="T1",
                symbols_csv=str(row["symbols_csv"]),
                loop_interval_sec=int(row["loop_interval_sec"]),
                between_symbol_sec=int(row["between_symbol_sec"]),
                quote_order_qty_modulo=Decimal(str(row["quote_order_qty_modulo"])),
                factor_multiplication=Decimal(str(row["factor_multiplication"])),
                meta_equity_usdt=Decimal(str(row["meta_equity_usdt"])),
                reference_ts_iso=str(row["reference_ts_iso"]),
                qty_decimals=int(row["qty_decimals"]),
                note=str(row["note"] or ""),
                max_drawdown_pct=Decimal(str(row["max_drawdown_pct"] or "0.25")),
                stop_loss_pct=Decimal(str(row["stop_loss_pct"] or "0.20")),
                metrics_interval_cycles=int(row["metrics_interval_cycles"] or 3),
                simulated=bool(int(row["simulated"])),
                trading_enabled=bool(int(row["trading_enabled"])),
            )
            cfg.normalize()
            runner = ThusneldaRunner(
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
            rec = _ThusneldaRecord(
                bot_id=bot_id,
                tag=str(row["tag"] or "Thusnelda").strip() or "Thusnelda",
                runner=runner,
                created_at=str(row["created_at"]),
                desired_running=bool(int(row["desired_running"])),
            )
            self._bots[bot_id] = rec

    def _save_instance(self, rec: _ThusneldaRecord) -> None:
        if self._db_path is None:
            return
        cfg = rec.runner.config
        with self._db_lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                conn.execute(
                    """
                    INSERT INTO thusnelda_instances (
                        bot_id, tag, created_at, symbols_csv, loop_interval_sec, between_symbol_sec,
                        quote_order_qty_modulo, factor_multiplication, meta_equity_usdt,
                        reference_ts_iso, qty_decimals, note, max_drawdown_pct, stop_loss_pct, metrics_interval_cycles, simulated, trading_enabled, desired_running
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(bot_id) DO UPDATE SET
                        tag=excluded.tag,
                        created_at=excluded.created_at,
                        symbols_csv=excluded.symbols_csv,
                        loop_interval_sec=excluded.loop_interval_sec,
                        between_symbol_sec=excluded.between_symbol_sec,
                        quote_order_qty_modulo=excluded.quote_order_qty_modulo,
                        factor_multiplication=excluded.factor_multiplication,
                        meta_equity_usdt=excluded.meta_equity_usdt,
                        reference_ts_iso=excluded.reference_ts_iso,
                        qty_decimals=excluded.qty_decimals,
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
                        cfg.symbols_csv,
                        int(cfg.loop_interval_sec),
                        int(cfg.between_symbol_sec),
                        str(cfg.quote_order_qty_modulo),
                        str(cfg.factor_multiplication),
                        str(cfg.meta_equity_usdt),
                        cfg.reference_ts_iso,
                        int(cfg.qty_decimals),
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
                conn.execute("DELETE FROM thusnelda_instances WHERE bot_id = ?", (bot_id,))
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
                    INSERT INTO thusnelda_logs (ts_utc, bot_id, tag, level, message, payload_json)
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
                    FROM thusnelda_runtime_state
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
                    INSERT INTO thusnelda_equity_snapshots (
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
                    "SELECT cycle_count FROM thusnelda_runtime_state WHERE bot_id = ?",
                    (bot_id,),
                ).fetchone()
                cycle_count = int(row[0]) if row is not None and row[0] is not None else 0
                conn.execute(
                    """
                    INSERT INTO thusnelda_runtime_state (bot_id, peak_equity_usdt, max_drawdown_seen, cycle_count, updated_at)
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
                    INSERT INTO thusnelda_metrics_log (ts_utc, bot_id, sharpe, win_rate, max_drawdown, samples)
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
                if msg == "thusnelda:equity_snapshot":
                    self._persist_equity_snapshot(bot_id, payload)
                elif msg == "thusnelda:metrics":
                    self._persist_metrics(bot_id, payload)

        return _sink

    def _record_payload(self, rec: _ThusneldaRecord) -> dict[str, Any]:
        cfg = rec.runner.config
        return {
            "bot_id": rec.bot_id,
            "tag": rec.tag,
            "created_at": rec.created_at,
            "running": rec.runner.running,
            "desired_running": rec.desired_running,
            "preset_id": cfg.preset_id,
            "symbols_csv": cfg.symbols_csv,
            "symbols": cfg.symbols(),
            "loop_interval_sec": cfg.loop_interval_sec,
            "between_symbol_sec": cfg.between_symbol_sec,
            "quote_order_qty_modulo": str(cfg.quote_order_qty_modulo),
            "factor_multiplication": str(cfg.factor_multiplication),
            "meta_equity_usdt": str(cfg.meta_equity_usdt),
            "reference_ts_iso": cfg.reference_ts_iso,
            "qty_decimals": cfg.qty_decimals,
            "note": cfg.note,
            "max_drawdown_pct": str(cfg.max_drawdown_pct),
            "stop_loss_pct": str(cfg.stop_loss_pct),
            "metrics_interval_cycles": cfg.metrics_interval_cycles,
            "simulated": cfg.simulated,
            "trading_enabled": cfg.trading_enabled,
            "last_cycle_ts": rec.runner.last_cycle_ts,
            "last_error": rec.runner.last_error,
            "last_report": rec.runner.last_report,
        }

    def create_instance(
        self,
        *,
        tag: str,
        bot_id: Optional[str] = None,
        symbols_csv: str = "BTCUSDT,ETHUSDT",
        loop_interval_sec: int = 600,
        between_symbol_sec: int = 3,
        quote_order_qty_modulo: str = "8",
        factor_multiplication: str = "0.99",
        meta_equity_usdt: str = "1000000",
        reference_ts_iso: str = "",
        qty_decimals: int = 8,
        note: str = "",
        max_drawdown_pct: str = "0.25",
        stop_loss_pct: str = "0.20",
        metrics_interval_cycles: int = 3,
        simulated: bool = True,
        trading_enabled: bool = False,
    ) -> dict[str, Any]:
        bot_id_norm = (bot_id or "").strip() or f"thusnelda-{uuid.uuid4().hex[:8]}"
        if bot_id_norm in self._bots:
            raise ValueError(f"Bot id already exists: {bot_id_norm}")
        cfg = ThusneldaConfig(
            preset_id="T1",
            symbols_csv=symbols_csv,
            loop_interval_sec=loop_interval_sec,
            between_symbol_sec=between_symbol_sec,
            quote_order_qty_modulo=Decimal(str(quote_order_qty_modulo)),
            factor_multiplication=Decimal(str(factor_multiplication)),
            meta_equity_usdt=Decimal(str(meta_equity_usdt)),
            reference_ts_iso=reference_ts_iso,
            qty_decimals=qty_decimals,
            note=note,
            max_drawdown_pct=Decimal(str(max_drawdown_pct)),
            stop_loss_pct=Decimal(str(stop_loss_pct)),
            metrics_interval_cycles=int(metrics_interval_cycles),
            simulated=simulated,
            trading_enabled=trading_enabled,
        )
        cfg.normalize()
        runner = ThusneldaRunner(
            self._runner_log_sink(bot_id_norm),
            self._runner_event_sink(bot_id_norm),
        )
        runner.apply_config(cfg)
        rec = _ThusneldaRecord(
            bot_id=bot_id_norm,
            tag=(tag or "Thusnelda").strip() or "Thusnelda",
            runner=runner,
            created_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            desired_running=False,
        )
        self._bots[bot_id_norm] = rec
        self._save_instance(rec)
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

    def update_instance(
        self,
        bot_id: str,
        *,
        tag: Optional[str] = None,
        symbols_csv: Optional[str] = None,
        loop_interval_sec: Optional[int] = None,
        between_symbol_sec: Optional[int] = None,
        quote_order_qty_modulo: Optional[str] = None,
        factor_multiplication: Optional[str] = None,
        meta_equity_usdt: Optional[str] = None,
        reference_ts_iso: Optional[str] = None,
        qty_decimals: Optional[int] = None,
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
        if symbols_csv is not None:
            cfg.symbols_csv = symbols_csv
        if loop_interval_sec is not None:
            cfg.loop_interval_sec = loop_interval_sec
        if between_symbol_sec is not None:
            cfg.between_symbol_sec = between_symbol_sec
        if quote_order_qty_modulo is not None:
            cfg.quote_order_qty_modulo = Decimal(str(quote_order_qty_modulo))
        if factor_multiplication is not None:
            cfg.factor_multiplication = Decimal(str(factor_multiplication))
        if meta_equity_usdt is not None:
            cfg.meta_equity_usdt = Decimal(str(meta_equity_usdt))
        if reference_ts_iso is not None:
            cfg.reference_ts_iso = reference_ts_iso
        if qty_decimals is not None:
            cfg.qty_decimals = qty_decimals
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

    async def _start_runner(self, rec: _ThusneldaRecord, api_key: str, api_secret: str) -> None:
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
        rec.runner._last_report = dict(rep)  # noqa: SLF001
        rec.runner._last_error = None  # noqa: SLF001
        rec.runner._last_cycle_ts = dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: SLF001
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
                    FROM thusnelda_logs
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
