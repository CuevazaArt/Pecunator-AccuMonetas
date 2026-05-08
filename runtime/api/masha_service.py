"""API-level hub service for Masha2.0 bots — refactored to use BaseHubService."""

from __future__ import annotations

import datetime as dt
import sqlite3
import uuid
from decimal import Decimal
from typing import Any, Callable, Optional

from runtime.api.base_hub_service import BaseHubService, BotRecord
from runtime.core.db_util import open_db
from runtime.modules.bots.masha import MashaConfig, MashaRunner


class MashaService(BaseHubService):
    HUB_CONFIG = {
        "db_filename": "masha_hub.sqlite",
        "table_prefix": "masha",
        "equity_msg": "bot:equity_snapshot",
        "metrics_msg": "bot:metrics",
    }

    # -------------------------------------------------------------------------
    # BaseHubService abstract implementations
    # -------------------------------------------------------------------------

    def _make_runner(self, log_sink: Callable, event_sink: Callable) -> MashaRunner:
        return MashaRunner(log_sink, event_sink)

    def _make_config(self, **kwargs: Any) -> MashaConfig:
        cfg = MashaConfig(
            symbols_csv=kwargs.get("symbols_csv", kwargs.get("symbol", "BTCUSDT")),
            loop_interval_sec=int(kwargs.get("loop_interval_sec", 59)),
            quote_min_free_to_operate=Decimal(str(kwargs.get("quote_min_free_to_operate", "10"))),
            buy_qty_base=Decimal(str(kwargs.get("buy_qty_base", "0.001"))),
            profit_factor=Decimal(str(kwargs.get("profit_factor", "0.015"))),
            timeframe_w=str(kwargs.get("timeframe_w", "1w")),
            periods_w=int(kwargs.get("periods_w", 4)),
            mm_periods_w=int(kwargs.get("mm_periods_w", 4)),
            margin_low_w=Decimal(str(kwargs.get("margin_low_w", "0.02"))),
            timeframe_h=str(kwargs.get("timeframe_h", "1h")),
            periods_h=int(kwargs.get("periods_h", 24)),
            mm_periods_h=int(kwargs.get("mm_periods_h", 24)),
            margin_low_h=Decimal(str(kwargs.get("margin_low_h", "0.01"))),
            qty_decimals=int(kwargs.get("qty_decimals", 5)),
            price_decimals=int(kwargs.get("price_decimals", 2)),
            note=str(kwargs.get("note", "")),
            max_drawdown_pct=Decimal(str(kwargs.get("max_drawdown_pct", "0.25"))),
            stop_loss_pct=Decimal(str(kwargs.get("stop_loss_pct", "0.15"))),
            metrics_interval_cycles=int(kwargs.get("metrics_interval_cycles", 5)),
            simulated=bool(kwargs.get("simulated", True)),
            trading_enabled=bool(kwargs.get("trading_enabled", False)),
        )
        cfg.normalize()
        return cfg

    def _record_extra(self, runner: MashaRunner) -> dict[str, Any]:
        cfg = runner.config
        return {
            "symbols_csv": cfg.symbols_csv,
            "loop_interval_sec": cfg.loop_interval_sec,
            "quote_min_free_to_operate": str(cfg.quote_min_free_to_operate),
            "buy_qty_base": str(cfg.buy_qty_base),
            "profit_factor": str(cfg.profit_factor),
            "timeframe_w": cfg.timeframe_w,
            "periods_w": cfg.periods_w,
            "mm_periods_w": cfg.mm_periods_w,
            "margin_low_w": str(cfg.margin_low_w),
            "timeframe_h": cfg.timeframe_h,
            "periods_h": cfg.periods_h,
            "mm_periods_h": cfg.mm_periods_h,
            "margin_low_h": str(cfg.margin_low_h),
            "qty_decimals": cfg.qty_decimals,
            "price_decimals": cfg.price_decimals,
            "note": cfg.note,
            "max_drawdown_pct": str(cfg.max_drawdown_pct),
            "stop_loss_pct": str(cfg.stop_loss_pct),
            "metrics_interval_cycles": cfg.metrics_interval_cycles,
            "simulated": cfg.simulated,
            "trading_enabled": cfg.trading_enabled,
        }

    # -------------------------------------------------------------------------
    # Masha-specific DB schema
    # -------------------------------------------------------------------------

    def _init_db(self) -> None:
        super()._init_db()
        if self._db_path is None:
            return
        with self._db_lock:
            conn = open_db(self._db_path)
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS masha_instances (
                        bot_id TEXT PRIMARY KEY,
                        tag TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        base_asset TEXT NOT NULL,
                        quote_asset TEXT NOT NULL,
                        loop_interval_sec INTEGER NOT NULL,
                        quote_min_free_to_operate TEXT NOT NULL,
                        buy_qty_base TEXT NOT NULL,
                        profit_factor TEXT NOT NULL,
                        timeframe_w TEXT NOT NULL,
                        periods_w INTEGER NOT NULL,
                        mm_periods_w INTEGER NOT NULL,
                        margin_low_w TEXT NOT NULL,
                        timeframe_h TEXT NOT NULL,
                        periods_h INTEGER NOT NULL,
                        mm_periods_h INTEGER NOT NULL,
                        margin_low_h TEXT NOT NULL,
                        qty_decimals INTEGER NOT NULL,
                        price_decimals INTEGER NOT NULL,
                        note TEXT NOT NULL,
                        max_drawdown_pct TEXT NOT NULL DEFAULT '0.25',
                        stop_loss_pct TEXT NOT NULL DEFAULT '0.15',
                        metrics_interval_cycles INTEGER NOT NULL DEFAULT 5,
                        simulated INTEGER NOT NULL,
                        trading_enabled INTEGER NOT NULL,
                        desired_running INTEGER NOT NULL DEFAULT 0
                    )
                """)
                for col_ddl in [
                    "ALTER TABLE masha_instances ADD COLUMN max_drawdown_pct TEXT NOT NULL DEFAULT '0.25'",
                    "ALTER TABLE masha_instances ADD COLUMN stop_loss_pct TEXT NOT NULL DEFAULT '0.15'",
                    "ALTER TABLE masha_instances ADD COLUMN metrics_interval_cycles INTEGER NOT NULL DEFAULT 5",
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
                    INSERT INTO masha_instances (
                        bot_id, tag, created_at, symbol, base_asset, quote_asset,
                        loop_interval_sec, quote_min_free_to_operate, buy_qty_base,
                        profit_factor, timeframe_w, periods_w, mm_periods_w, margin_low_w,
                        timeframe_h, periods_h, mm_periods_h, margin_low_h,
                        qty_decimals, price_decimals, note,
                        max_drawdown_pct, stop_loss_pct, metrics_interval_cycles,
                        simulated, trading_enabled, desired_running
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(bot_id) DO UPDATE SET
                        tag=excluded.tag, symbol=excluded.symbol,
                        base_asset=excluded.base_asset, quote_asset=excluded.quote_asset,
                        loop_interval_sec=excluded.loop_interval_sec,
                        quote_min_free_to_operate=excluded.quote_min_free_to_operate,
                        buy_qty_base=excluded.buy_qty_base,
                        profit_factor=excluded.profit_factor,
                        timeframe_w=excluded.timeframe_w, periods_w=excluded.periods_w,
                        mm_periods_w=excluded.mm_periods_w, margin_low_w=excluded.margin_low_w,
                        timeframe_h=excluded.timeframe_h, periods_h=excluded.periods_h,
                        mm_periods_h=excluded.mm_periods_h, margin_low_h=excluded.margin_low_h,
                        qty_decimals=excluded.qty_decimals, price_decimals=excluded.price_decimals,
                        note=excluded.note,
                        max_drawdown_pct=excluded.max_drawdown_pct,
                        stop_loss_pct=excluded.stop_loss_pct,
                        metrics_interval_cycles=excluded.metrics_interval_cycles,
                        simulated=excluded.simulated, trading_enabled=excluded.trading_enabled,
                        desired_running=excluded.desired_running
                    """,
                    (
                        rec.bot_id, rec.tag, rec.created_at, cfg.symbols_csv,
                        "DYN", "DYN",
                        int(cfg.loop_interval_sec),
                        str(cfg.quote_min_free_to_operate), str(cfg.buy_qty_base),
                        str(cfg.profit_factor),
                        cfg.timeframe_w, int(cfg.periods_w), int(cfg.mm_periods_w), str(cfg.margin_low_w),
                        cfg.timeframe_h, int(cfg.periods_h), int(cfg.mm_periods_h), str(cfg.margin_low_h),
                        int(cfg.qty_decimals), int(cfg.price_decimals), str(cfg.note or ""),
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
                    SELECT * FROM masha_instances ORDER BY created_at ASC
                """).fetchall()
            finally:
                conn.close()

        for row in rows:
            bot_id = str(row["bot_id"]).strip()
            if not bot_id or bot_id in self._bots:
                continue
            cfg = self._make_config(
                symbols_csv=str(row["symbol"]),
                loop_interval_sec=int(row["loop_interval_sec"]),
                quote_min_free_to_operate=str(row["quote_min_free_to_operate"]),
                buy_qty_base=str(row["buy_qty_base"]),
                profit_factor=str(row["profit_factor"]),
                timeframe_w=str(row["timeframe_w"]), periods_w=int(row["periods_w"]),
                mm_periods_w=int(row["mm_periods_w"]), margin_low_w=str(row["margin_low_w"]),
                timeframe_h=str(row["timeframe_h"]), periods_h=int(row["periods_h"]),
                mm_periods_h=int(row["mm_periods_h"]), margin_low_h=str(row["margin_low_h"]),
                qty_decimals=int(row["qty_decimals"]), price_decimals=int(row["price_decimals"]),
                note=str(row["note"] or ""),
                max_drawdown_pct=str(row["max_drawdown_pct"] or "0.25"),
                stop_loss_pct=str(row["stop_loss_pct"] or "0.15"),
                metrics_interval_cycles=int(row["metrics_interval_cycles"] or 5),
                simulated=bool(int(row["simulated"])),
                trading_enabled=bool(int(row["trading_enabled"])),
            )
            runner = self._make_runner(self._runner_log_sink(bot_id), self._runner_event_sink(bot_id))
            st = self._load_runtime_state(bot_id)
            if st is not None:
                runner.restore_risk_state(**{k: st.get(k) for k in ("peak_equity_usdt", "max_drawdown_seen", "cycle_count", "active_symbol")})
            runner.apply_config(cfg)
            rec = BotRecord(
                bot_id=bot_id,
                tag=str(row["tag"] or "Masha").strip() or "Masha",
                runner=runner,
                created_at=str(row["created_at"]),
                desired_running=bool(int(row["desired_running"])),
            )
            self._bots[bot_id] = rec

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def create_instance(self, *, tag: str, bot_id: Optional[str] = None, **kwargs: Any) -> dict[str, Any]:
        bot_id_norm = (bot_id or "").strip() or f"masha-{uuid.uuid4().hex[:8]}"
        if bot_id_norm in self._bots:
            raise ValueError(f"Bot id already exists: {bot_id_norm}")
        cfg = self._make_config(**kwargs)
        runner = self._make_runner(self._runner_log_sink(bot_id_norm), self._runner_event_sink(bot_id_norm))
        runner.apply_config(cfg)
        rec = BotRecord(
            bot_id=bot_id_norm,
            tag=(tag or "Masha").strip(),
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
        merged = {k: getattr(cfg, k) for k in vars(cfg) if not k.startswith("_")}
        # Stringify Decimals
        for k in ("quote_min_free_to_operate", "buy_qty_base", "profit_factor",
                  "margin_low_w", "margin_low_h", "max_drawdown_pct", "stop_loss_pct"):
            merged[k] = str(merged.get(k, "0"))
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
