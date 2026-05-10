"""API-level hub service for Elphaba (Anti-Dorothy) bots.

Follows the same BaseHubService pattern as Dorothy's BotService.
Manages margin short bots via SQLite persistence + immortality.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from decimal import Decimal
from typing import Any, Callable, Optional
import uuid

from runtime.api.base_hub_service import BaseHubService, BotRecord
from runtime.core.db_util import open_db
from runtime.bot.elphaba import ElphabaConfig, ElphabaRunner


class ElphabaService(BaseHubService):
    HUB_CONFIG = {
        "db_filename": "elphaba_hub.sqlite",
        "table_prefix": "elphaba",
        "equity_msg": "bot:equity_snapshot",
        "metrics_msg": "bot:metrics",
    }

    # -------------------------------------------------------------------------
    # BaseHubService abstract implementations
    # -------------------------------------------------------------------------

    def _make_runner(self, log_sink: Callable, event_sink: Callable) -> ElphabaRunner:
        return ElphabaRunner(log_sink, event_sink)

    def _make_config(self, **kwargs: Any) -> ElphabaConfig:
        cfg = ElphabaConfig(
            preset_id=str(kwargs.get("preset_id", "E1")),
            symbol=kwargs.get("symbol", "XRPUSDT"),
            loop_interval_sec=int(kwargs.get("loop_interval_sec", 450)),
            quote_order_qty=Decimal(str(kwargs.get("quote_order_qty", "6"))),
            profit_factor=Decimal(str(kwargs.get("profit_factor", "0.05"))),
            margin_rise_factor=Decimal(str(kwargs.get("margin_rise_factor", "0.03"))),
            qty_decimals=int(kwargs.get("qty_decimals", 8)),
            price_decimals=int(kwargs.get("price_decimals", 4)),
            note=str(kwargs.get("note", "")),
            max_drawdown_pct=Decimal(str(kwargs.get("max_drawdown_pct", "0.20"))),
            metrics_interval_cycles=int(kwargs.get("metrics_interval_cycles", 5)),
            max_rungs_per_symbol=int(kwargs.get("max_rungs_per_symbol", 3)),
        )
        cfg.normalize()
        return cfg

    def _record_extra(self, runner: ElphabaRunner) -> dict[str, Any]:
        cfg = runner.config
        return {
            "preset_id": cfg.preset_id,
            "symbol": cfg.symbol,
            "loop_interval_sec": cfg.loop_interval_sec,
            "quote_order_qty": str(cfg.quote_order_qty),
            "profit_factor": str(cfg.profit_factor),
            "margin_rise_factor": str(cfg.margin_rise_factor),
            "margin_drop_factor": "0",
            "qty_decimals": cfg.qty_decimals,
            "price_decimals": cfg.price_decimals,
            "note": cfg.note,
            "max_drawdown_pct": str(cfg.max_drawdown_pct),
            "stop_loss_pct": "0.0",
            "metrics_interval_cycles": cfg.metrics_interval_cycles,
            "max_rungs_per_symbol": cfg.max_rungs_per_symbol,
            "margin_type": cfg.margin_type,
        }

    # -------------------------------------------------------------------------
    # Elphaba DB schema
    # -------------------------------------------------------------------------

    def _init_db(self) -> None:
        super()._init_db()
        if self._db_path is None:
            return
        with self._db_lock:
            conn = open_db(self._db_path)
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS elphaba_instances (
                        bot_id TEXT PRIMARY KEY,
                        tag TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        loop_interval_sec INTEGER NOT NULL,
                        quote_order_qty TEXT NOT NULL,
                        profit_factor TEXT NOT NULL,
                        margin_rise_factor TEXT NOT NULL DEFAULT '0.03',
                        qty_decimals INTEGER NOT NULL,
                        price_decimals INTEGER NOT NULL,
                        note TEXT NOT NULL DEFAULT '',
                        max_drawdown_pct TEXT NOT NULL DEFAULT '0.20',
                        metrics_interval_cycles INTEGER NOT NULL DEFAULT 5,
                        max_rungs_per_symbol INTEGER NOT NULL DEFAULT 3,
                        trading_enabled INTEGER NOT NULL DEFAULT 0,
                        desired_running INTEGER NOT NULL DEFAULT 0
                    )
                """)
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
                    INSERT INTO elphaba_instances (
                        bot_id, tag, created_at, symbol, loop_interval_sec,
                        quote_order_qty, profit_factor, margin_rise_factor,
                        qty_decimals, price_decimals, note, max_drawdown_pct,
                        metrics_interval_cycles, max_rungs_per_symbol,
                        trading_enabled, desired_running
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(bot_id) DO UPDATE SET
                        tag=excluded.tag, symbol=excluded.symbol,
                        loop_interval_sec=excluded.loop_interval_sec,
                        quote_order_qty=excluded.quote_order_qty,
                        profit_factor=excluded.profit_factor,
                        margin_rise_factor=excluded.margin_rise_factor,
                        qty_decimals=excluded.qty_decimals,
                        price_decimals=excluded.price_decimals,
                        note=excluded.note,
                        max_drawdown_pct=excluded.max_drawdown_pct,
                        metrics_interval_cycles=excluded.metrics_interval_cycles,
                        max_rungs_per_symbol=excluded.max_rungs_per_symbol,
                        trading_enabled=excluded.trading_enabled,
                        desired_running=excluded.desired_running
                    """,
                    (
                        rec.bot_id, rec.tag, rec.created_at, cfg.symbol,
                        int(cfg.loop_interval_sec),
                        str(cfg.quote_order_qty), str(cfg.profit_factor),
                        str(cfg.margin_rise_factor),
                        int(cfg.qty_decimals), int(cfg.price_decimals),
                        str(cfg.note or ""),
                        str(cfg.max_drawdown_pct),
                        int(cfg.metrics_interval_cycles),
                        int(cfg.max_rungs_per_symbol),
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
                    SELECT bot_id, tag, created_at, symbol, loop_interval_sec,
                           quote_order_qty, profit_factor, margin_rise_factor,
                           qty_decimals, price_decimals, note, max_drawdown_pct,
                           metrics_interval_cycles, max_rungs_per_symbol,
                           trading_enabled, desired_running
                    FROM elphaba_instances ORDER BY created_at ASC
                """).fetchall()
            finally:
                conn.close()

        for row in rows:
            bot_id = str(row["bot_id"]).strip()
            if not bot_id or bot_id in self._bots:
                continue
            cfg = self._make_config(
                symbol=str(row["symbol"]),
                loop_interval_sec=int(row["loop_interval_sec"]),
                quote_order_qty=str(row["quote_order_qty"]),
                profit_factor=str(row["profit_factor"]),
                margin_rise_factor=str(row["margin_rise_factor"] or "0.03"),
                qty_decimals=int(row["qty_decimals"]),
                price_decimals=int(row["price_decimals"]),
                note=str(row["note"] or ""),
                max_drawdown_pct=str(row["max_drawdown_pct"] or "0.20"),
                metrics_interval_cycles=int(row["metrics_interval_cycles"] or 5),
                max_rungs_per_symbol=int(row["max_rungs_per_symbol"] or 3),
                trading_enabled=bool(int(row["trading_enabled"])),
            )
            runner = self._make_runner(
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
            rec = BotRecord(
                bot_id=bot_id,
                tag=str(row["tag"] or "Elphaba").strip() or "Elphaba",
                runner=runner,
                created_at=str(row["created_at"]),
                desired_running=bool(int(row["desired_running"])),
            )
            self._bots[bot_id] = rec
            if self._default_bot_id is None:
                self._default_bot_id = bot_id

    # -------------------------------------------------------------------------
    # Elphaba CRUD (same pattern as Dorothy)
    # -------------------------------------------------------------------------

    def create_instance(self, *, tag: str, bot_id: Optional[str] = None, **kwargs: Any) -> dict[str, Any]:
        bot_id_norm = (bot_id or "").strip() or f"elphaba-{uuid.uuid4().hex[:8]}"
        if bot_id_norm in self._bots:
            raise ValueError(f"Bot id already exists: {bot_id_norm}")
        cfg = self._make_config(**kwargs)
        runner = self._make_runner(
            self._runner_log_sink(bot_id_norm),
            self._runner_event_sink(bot_id_norm),
        )
        runner.apply_config(cfg)
        rec = BotRecord(
            bot_id=bot_id_norm,
            tag=(tag or "Elphaba").strip(),
            runner=runner,
            created_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        )
        self._bots[bot_id_norm] = rec
        self._save_instance(rec)
        if self._default_bot_id is None:
            self._default_bot_id = bot_id_norm
        payload = self._record_payload(rec)
        self._write_log(bot_id_norm, rec.tag, "SYSTEM", "bot_created", payload)
        return payload

    def update_instance(self, bot_id: str, *, tag: Optional[str] = None, **kwargs: Any) -> dict[str, Any]:
        rec = self._bots.get(bot_id)
        if rec is None:
            raise KeyError(bot_id)
        old_cfg = rec.runner.config
        merged = {
            "symbol": old_cfg.symbol,
            "loop_interval_sec": old_cfg.loop_interval_sec,
            "quote_order_qty": str(old_cfg.quote_order_qty),
            "profit_factor": str(old_cfg.profit_factor),
            "margin_rise_factor": str(old_cfg.margin_rise_factor),
            "qty_decimals": old_cfg.qty_decimals,
            "price_decimals": old_cfg.price_decimals,
            "note": old_cfg.note,
            "max_drawdown_pct": str(old_cfg.max_drawdown_pct),
            "metrics_interval_cycles": old_cfg.metrics_interval_cycles,
            "max_rungs_per_symbol": old_cfg.max_rungs_per_symbol,
            "trading_enabled": old_cfg.trading_enabled,
        }
        for k, v in kwargs.items():
            if v is not None:
                merged[k] = v
        cfg = self._make_config(**merged)
        rec.runner.apply_config(cfg)
        if tag is not None and tag.strip():
            rec.tag = tag.strip()
        self._save_instance(rec)
        payload = self._record_payload(rec)
        self._write_log(bot_id, rec.tag, "SYSTEM", "bot_updated", payload)
        return payload
