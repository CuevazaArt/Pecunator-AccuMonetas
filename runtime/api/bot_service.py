"""API-level singleton bot service for Dorothy preset B."""

from __future__ import annotations

from dataclasses import replace
import datetime as dt
from decimal import Decimal
from typing import Any

from runtime.bot.dorothy import DorothyConfig, DorothyRunner


class BotService:
    def __init__(self) -> None:
        self.runner = DorothyRunner(self._log_sink)

    def _log_sink(self, _msg: str) -> None:
        # Runtime logs are already handled by AppContext in API routes.
        return

    def get_config(self) -> DorothyConfig:
        return replace(self.runner.config)

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
        simulated: bool,
        trading_enabled: bool,
    ) -> DorothyConfig:
        cfg = DorothyConfig(
            preset_id="B",
            symbol=symbol,
            loop_interval_sec=loop_interval_sec,
            quote_order_qty=Decimal(quote_order_qty),
            profit_factor=Decimal(profit_factor),
            margin_drop_factor=Decimal(margin_drop_factor),
            qty_decimals=qty_decimals,
            price_decimals=price_decimals,
            simulated=simulated,
            trading_enabled=trading_enabled,
        )
        cfg.normalize()
        self.runner.apply_config(cfg)
        return replace(cfg)

    def status_payload(self) -> dict[str, Any]:
        cfg = self.runner.config
        return {
            "running": self.runner.running,
            "preset_id": cfg.preset_id,
            "symbol": cfg.symbol,
            "simulated": cfg.simulated,
            "trading_enabled": cfg.trading_enabled,
            "loop_interval_sec": cfg.loop_interval_sec,
            "last_cycle_ts": self.runner.last_cycle_ts,
            "last_error": self.runner.last_error,
            "last_report": self.runner.last_report,
        }

    def mark_run_once(self, report: dict[str, Any], error: str | None = None) -> None:
        self.runner._last_report = dict(report)  # noqa: SLF001
        self.runner._last_error = error  # noqa: SLF001
        self.runner._last_cycle_ts = dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: SLF001
