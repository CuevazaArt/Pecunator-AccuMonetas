"""API-level hub service for Thusnelda1.0 bots — refactored to use BaseHubService."""

from __future__ import annotations

import datetime as dt
import sqlite3
import uuid
from decimal import Decimal
from typing import Any, Callable, Optional

from runtime.api.base_hub_service import BaseHubService, BotRecord
from runtime.core.db_util import open_db
from runtime.modules.bots.thusnelda import ThusneldaConfig, ThusneldaRunner


class ThusneldaService(BaseHubService):
    HUB_CONFIG = {
        "db_filename": "thusnelda_hub.sqlite",
        "table_prefix": "thusnelda",
        "equity_msg": "bot:equity_snapshot",
        "metrics_msg": "bot:metrics",
    }

    # -------------------------------------------------------------------------
    # BaseHubService abstract implementations
    # -------------------------------------------------------------------------

    def _make_runner(self, log_sink: Callable, event_sink: Callable) -> ThusneldaRunner:
        return ThusneldaRunner(log_sink, event_sink)

    def _make_config(self, **kwargs: Any) -> ThusneldaConfig:
        cfg = ThusneldaConfig(
            symbols_csv=str(kwargs.get("symbols_csv", "PEPEUSDT,SUIUSDT,NEARUSDT,INJUSDT,FETUSDT")),
            loop_interval_sec=int(kwargs.get("loop_interval_sec", 300)),
            between_symbol_sec=int(kwargs.get("between_symbol_sec", 3)),
            quote_order_qty_modulo=Decimal(str(kwargs.get("quote_order_qty_modulo", "6"))),
            factor_multiplication=Decimal(str(kwargs.get("factor_multiplication", "0.94"))),
            profit_target_pct=Decimal(str(kwargs.get("profit_target_pct", "0.06"))),
            meta_equity_usdt=Decimal(str(kwargs.get("meta_equity_usdt", "0"))),
            reference_ts_iso=str(kwargs.get("reference_ts_iso", dt.datetime.now(dt.timezone.utc).isoformat())),
            qty_decimals=int(kwargs.get("qty_decimals", 8)),
            note=str(kwargs.get("note", "")),
            max_drawdown_pct=Decimal(str(kwargs.get("max_drawdown_pct", "0.30"))),
            stop_loss_pct=Decimal(str(kwargs.get("stop_loss_pct", "0.25"))),
            metrics_interval_cycles=int(kwargs.get("metrics_interval_cycles", 3)),
            simulated=bool(kwargs.get("simulated", True)),
            trading_enabled=bool(kwargs.get("trading_enabled", False)),
        )
        cfg.normalize()
        return cfg

    def _record_extra(self, runner: ThusneldaRunner) -> dict[str, Any]:
        cfg = runner.config
        return {
            "symbols_csv": cfg.symbols_csv,
            "loop_interval_sec": cfg.loop_interval_sec,
            "between_symbol_sec": cfg.between_symbol_sec,
            "quote_order_qty_modulo": str(cfg.quote_order_qty_modulo),
            "factor_multiplication": str(cfg.factor_multiplication),
            "profit_target_pct": str(cfg.profit_target_pct),
            "meta_equity_usdt": str(cfg.meta_equity_usdt),
            "reference_ts_iso": cfg.reference_ts_iso,
            "qty_decimals": cfg.qty_decimals,
            "note": cfg.note,
            "max_drawdown_pct": str(cfg.max_drawdown_pct),
            "stop_loss_pct": str(cfg.stop_loss_pct),
            "metrics_interval_cycles": cfg.metrics_interval_cycles,
            "simulated": cfg.simulated,
            "trading_enabled": cfg.trading_enabled,
        }

    # -------------------------------------------------------------------------
    # Thusnelda-specific DB schema
    # -------------------------------------------------------------------------

    def _init_db(self) -> None:
        super()._init_db()
        if self._db_path is None:
            return
        with self._db_lock:
            conn = open_db(self._db_path)
            try:
                conn.execute("""
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
                """)
                for col_ddl in [
                    "ALTER TABLE thusnelda_instances ADD COLUMN max_drawdown_pct TEXT NOT NULL DEFAULT '0.25'",
                    "ALTER TABLE thusnelda_instances ADD COLUMN stop_loss_pct TEXT NOT NULL DEFAULT '0.20'",
                    "ALTER TABLE thusnelda_instances ADD COLUMN metrics_interval_cycles INTEGER NOT NULL DEFAULT 3",
                ]:
                    try:
                        conn.execute(col_ddl)
                    except Exception:
                        pass
                conn.commit()
            finally:
                conn.close()

    def _save_instance(self, rec: BotRecord) -> None:
        if self._db_path is None:
            return
        cfg = rec.runner.config
        with self._db_lock:
            conn = open_db(self._db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO thusnelda_instances (
                        bot_id, tag, created_at, symbols_csv, loop_interval_sec,
                        between_symbol_sec, quote_order_qty_modulo, factor_multiplication,
                        meta_equity_usdt, reference_ts_iso, qty_decimals, note,
                        max_drawdown_pct, stop_loss_pct, metrics_interval_cycles,
                        simulated, trading_enabled, desired_running
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(bot_id) DO UPDATE SET
                        tag=excluded.tag, symbols_csv=excluded.symbols_csv,
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
                        rec.bot_id, rec.tag, rec.created_at, cfg.symbols_csv,
                        int(cfg.loop_interval_sec), int(cfg.between_symbol_sec),
                        str(cfg.quote_order_qty_modulo), str(cfg.factor_multiplication),
                        str(cfg.meta_equity_usdt), cfg.reference_ts_iso,
                        int(cfg.qty_decimals), str(cfg.note or ""),
                        str(cfg.max_drawdown_pct), str(cfg.stop_loss_pct),
                        int(cfg.metrics_interval_cycles),
                        1 if cfg.simulated else 0,
                        1 if cfg.trading_enabled else 0,
                        1 if rec.desired_running else 0,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def _load_instances_from_db(self) -> None:
        if self._db_path is None:
            return
        with self._db_lock:
            conn = open_db(self._db_path)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute("""
                    SELECT * FROM thusnelda_instances ORDER BY created_at ASC
                """).fetchall()
            finally:
                conn.close()

        for row in rows:
            bot_id = str(row["bot_id"]).strip()
            if not bot_id or bot_id in self._bots:
                continue
            cfg = self._make_config(
                symbols_csv=str(row["symbols_csv"]),
                loop_interval_sec=int(row["loop_interval_sec"]),
                between_symbol_sec=int(row["between_symbol_sec"]),
                quote_order_qty_modulo=str(row["quote_order_qty_modulo"]),
                factor_multiplication=str(row["factor_multiplication"]),
                meta_equity_usdt=str(row["meta_equity_usdt"]),
                reference_ts_iso=str(row["reference_ts_iso"]),
                qty_decimals=int(row["qty_decimals"]),
                note=str(row["note"] or ""),
                max_drawdown_pct=str(row["max_drawdown_pct"] or "0.25"),
                stop_loss_pct=str(row["stop_loss_pct"] or "0.20"),
                metrics_interval_cycles=int(row["metrics_interval_cycles"] or 3),
                simulated=bool(int(row["simulated"])),
                trading_enabled=bool(int(row["trading_enabled"])),
            )
            runner = self._make_runner(self._runner_log_sink(bot_id), self._runner_event_sink(bot_id))
            st = self._load_runtime_state(bot_id)
            if st is not None:
                runner.restore_risk_state(**{k: st.get(k) for k in ("peak_equity_usdt", "max_drawdown_seen", "cycle_count")})
            runner.apply_config(cfg)
            rec = BotRecord(
                bot_id=bot_id,
                tag=str(row["tag"] or "Thusnelda").strip() or "Thusnelda",
                runner=runner,
                created_at=str(row["created_at"]),
                desired_running=bool(int(row["desired_running"])),
            )
            self._bots[bot_id] = rec

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def create_instance(self, *, tag: str, bot_id: Optional[str] = None, **kwargs: Any) -> dict[str, Any]:
        bot_id_norm = (bot_id or "").strip() or f"thusnelda-{uuid.uuid4().hex[:8]}"
        if bot_id_norm in self._bots:
            raise ValueError(f"Bot id already exists: {bot_id_norm}")
        cfg = self._make_config(**kwargs)
        runner = self._make_runner(self._runner_log_sink(bot_id_norm), self._runner_event_sink(bot_id_norm))
        runner.apply_config(cfg)
        rec = BotRecord(
            bot_id=bot_id_norm,
            tag=(tag or "Thusnelda").strip(),
            runner=runner,
            created_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        )
        self._bots[bot_id_norm] = rec
        self._save_instance(rec)
        payload = self._record_payload(rec)
        self._write_log(bot_id_norm, rec.tag, "SYSTEM", "bot_created", payload)
        return payload

    def update_instance(self, bot_id: str, *, tag: Optional[str] = None, **kwargs: Any) -> dict[str, Any]:
        rec = self._bots.get(bot_id)
        if rec is None:
            raise KeyError(bot_id)
        cfg = rec.runner.config
        merged = {
            "symbols_csv": cfg.symbols_csv,
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
        }
        for k, v in kwargs.items():
            if v is not None:
                merged[k] = v
        new_cfg = self._make_config(**merged)
        rec.runner.apply_config(new_cfg)
        if tag is not None and tag.strip():
            rec.tag = tag.strip()
        self._save_instance(rec)
        payload = self._record_payload(rec)
        self._write_log(bot_id, rec.tag, "SYSTEM", "bot_updated", payload)
        return payload
