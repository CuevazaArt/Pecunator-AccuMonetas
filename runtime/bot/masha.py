"""Masha2.0-inspired multi-timeframe DCA strategy runner."""

from __future__ import annotations

import asyncio
import datetime as dt
import time
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Callable, Optional

from binance.client import Client

from runtime.bot._base_runner import BaseStrategyRunner
from runtime.bot._decimal_utils import dec as _dec, quantize as _q
from runtime.bot._paper_log import log_paper_trade
from runtime.connectors.binance_gateway import normalize_binance_spot_symbol


# _dec and _q imported from runtime.bot._decimal_utils


@dataclass
class MashaConfig:
    preset_id: str = "M2"
    symbol: str = "BTCUSDT"
    base_asset: str = "BTC"
    quote_asset: str = "USDT"
    loop_interval_sec: int = 300
    quote_min_free_to_operate: Decimal = Decimal("6")
    buy_qty_base: Decimal = Decimal("0.001")
    profit_factor: Decimal = Decimal("0.05")  # L0: min 3%, default 5%
    timeframe_w: str = "1w"
    periods_w: int = 2
    mm_periods_w: int = 2
    margin_low_w: Decimal = Decimal("0.03")
    timeframe_h: str = "1h"
    periods_h: int = 2
    mm_periods_h: int = 2
    margin_low_h: Decimal = Decimal("0.003")
    qty_decimals: int = 8
    price_decimals: int = 8
    note: str = ""
    # [MEJORA] Proteccion de riesgo configurable.
    max_drawdown_pct: Decimal = Decimal("0.25")
    stop_loss_pct: Decimal = Decimal("0.15")
    metrics_interval_cycles: int = 5
    # T0.1: Hard ceiling on DCA rungs.
    max_rungs_per_symbol: int = 5
    simulated: bool = True
    trading_enabled: bool = False

    def normalize(self) -> None:
        self.symbol = normalize_binance_spot_symbol(self.symbol)
        self.base_asset = (self.base_asset or "").strip().upper() or "BTC"
        self.quote_asset = (self.quote_asset or "").strip().upper() or "USDT"
        if not self.symbol.endswith(self.quote_asset):
            # Keep config coherent with symbol quote by default.
            self.quote_asset = self.symbol[-4:] if len(self.symbol) >= 4 else self.quote_asset
        self.loop_interval_sec = max(1, min(int(self.loop_interval_sec), 86_400))
        self.quote_min_free_to_operate = max(_dec(self.quote_min_free_to_operate, "0.0001"), Decimal("0.0001"))
        self.buy_qty_base = max(_dec(self.buy_qty_base, "0.00000001"), Decimal("0.00000001"))
        # L0 floor: 3% minimum profit to ensure viability after commissions
        self.profit_factor = max(_dec(self.profit_factor), Decimal("0.03"))
        self.margin_low_w = max(_dec(self.margin_low_w), Decimal("0"))
        self.margin_low_h = max(_dec(self.margin_low_h), Decimal("0"))
        self.periods_w = max(1, min(int(self.periods_w), 1000))
        self.mm_periods_w = max(1, min(int(self.mm_periods_w), self.periods_w))
        self.periods_h = max(1, min(int(self.periods_h), 1000))
        self.mm_periods_h = max(1, min(int(self.mm_periods_h), self.periods_h))
        self.qty_decimals = max(0, min(int(self.qty_decimals), 18))
        self.price_decimals = max(0, min(int(self.price_decimals), 18))
        self.note = (self.note or "").strip()[:20]
        self.max_drawdown_pct = max(_dec(self.max_drawdown_pct), Decimal("0"))
        self.stop_loss_pct = max(_dec(self.stop_loss_pct), Decimal("0"))
        self.metrics_interval_cycles = max(1, min(int(self.metrics_interval_cycles), 10_000))
        self.max_rungs_per_symbol = max(1, min(int(self.max_rungs_per_symbol), 100))

    def as_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["quote_min_free_to_operate"] = str(self.quote_min_free_to_operate)
        d["buy_qty_base"] = str(self.buy_qty_base)
        d["profit_factor"] = str(self.profit_factor)
        d["margin_low_w"] = str(self.margin_low_w)
        d["margin_low_h"] = str(self.margin_low_h)
        d["max_drawdown_pct"] = str(self.max_drawdown_pct)
        d["stop_loss_pct"] = str(self.stop_loss_pct)
        d["mode"] = "SIMULATED" if self.simulated else "LIVE"
        return d


class MashaRunner(BaseStrategyRunner):

    BOT_TYPE = "masha"

    def __init__(
        self,
        log: Callable[[str], None],
        event_log: Optional[Callable[[str, str, Optional[dict[str, Any]]], None]] = None,
    ) -> None:
        super().__init__(log, event_log)
        self.config = MashaConfig()
        self.config.normalize()
        self._last_buy_price: Optional[Decimal] = None

    def apply_config(self, cfg: MashaConfig) -> None:
        cfg.normalize()
        self.config = cfg

    def _bot_key(self) -> str:
        return f"masha:{self.config.symbol}"

    def _loop_log_summary(self, report: dict[str, Any]) -> str:
        return f"masha:{report.get('decision')} symbol={report.get('symbol')} simulated={report.get('simulated')}"

    async def _ohlc_signal(
        self,
        client: Client,
        symbol: str,
        timeframe: str,
        periods: int,
        mm_periods: int,
    ) -> tuple[Decimal, Decimal, Decimal]:
        time_unit = "hours"
        if "m" in timeframe:
            time_unit = "minutes"
        elif "h" in timeframe:
            time_unit = "hours"
        elif "d" in timeframe:
            time_unit = "days"
        elif "w" in timeframe:
            time_unit = "weeks"
        elif "M" in timeframe:
            time_unit = "months"
        start_time = f"{periods} {time_unit} ago UTC"
        klines = await self._to_thread(
            lambda: client.get_historical_klines(symbol, timeframe, start_time)
        )
        # Note: klines are NOT cached here because they're per-symbol/timeframe
        # and per-bot config. Cache benefit is low vs complexity.
        if not isinstance(klines, list) or not klines:
            raise RuntimeError(f"No OHLC data for {symbol} {timeframe}")

        medians: list[Decimal] = []
        for row in klines:
            if not isinstance(row, list) or len(row) < 5:
                continue
            high = _dec(row[2], "0")
            low = _dec(row[3], "0")
            medians.append((high + low) / Decimal("2"))
        if not medians:
            raise RuntimeError(f"No median data for {symbol} {timeframe}")
        mm_n = max(1, min(mm_periods, len(medians)))
        mm_price = sum(medians[-mm_n:], Decimal("0")) / Decimal(mm_n)
        last_low = _dec(klines[-1][3], "0")
        last_close = _dec(klines[-1][4], "0")
        return mm_price, last_low, last_close

    async def run_once(self) -> dict[str, Any]:
        from runtime.core.api_fuse import get_api_fuse
        fuse = get_api_fuse()
        if fuse.is_tripped():
            remaining = fuse.remaining_cooldown_sec()
            self._emit("WARNING", f"API FUSE ACTIVO: ciclo omitido ({remaining:.0f}s restantes)")
            return {"decision": "FUSE_TRIPPED", "remaining_sec": remaining}
        c = self.config
        c.normalize()
        if not c.simulated and not c.trading_enabled:
            raise RuntimeError("LIVE mode requires trading_enabled=true (explicit switch).")
        client = self._ensure_client()
        symbol = c.symbol

        await self._sync_time_for_signed(client)

        # DCA anchor: current SELL LIMIT.
        try:
            from runtime.core.market_cache import get_market_cache, MarketCache
            _cache = get_market_cache()
            open_orders = await _cache.get_or_fetch(
                MarketCache.scoped_key(f"open_orders:{symbol}", self._api_key),
                lambda: self._signed_call(client, lambda: client.get_open_orders(symbol=symbol)),
            )
        except Exception:
            open_orders = await self._signed_call(client, lambda: client.get_open_orders(symbol=symbol))
        self._emit("INFO", "binance:get_open_orders", {"symbol": symbol, "response": open_orders})
        dca_price = Decimal("0")
        dca_volume = Decimal("0")
        dca_cost = Decimal("0")
        if isinstance(open_orders, list):
            for order in open_orders:
                if not isinstance(order, dict):
                    continue
                if str(order.get("side", "")).upper() != "SELL":
                    continue
                if str(order.get("status", "")).upper() != "NEW":
                    continue
                dca_price = _dec(order.get("price", "0"), "0")
                dca_volume = _dec(order.get("origQty", order.get("executedQty", "0")), "0")
                dca_cost = dca_price * dca_volume
                break

        mm_w, low_w, close_w = await self._ohlc_signal(
            client,
            symbol,
            c.timeframe_w,
            c.periods_w,
            c.mm_periods_w,
        )
        mm_h, low_h, close_h = await self._ohlc_signal(
            client,
            symbol,
            c.timeframe_h,
            c.periods_h,
            c.mm_periods_h,
        )

        try:
            from runtime.core.market_cache import get_market_cache, MarketCache
            _cache = get_market_cache()
            account = await _cache.get_or_fetch(
                MarketCache.scoped_key("account", self._api_key),
                lambda: self._signed_call(client, client.get_account),
            )
        except Exception:
            account = await self._signed_call(client, client.get_account)
        self._emit("INFO", "binance:get_account", {"symbol": symbol, "response": account})
        base_free = Decimal("0")
        base_locked = Decimal("0")
        quote_free = Decimal("0")
        quote_locked = Decimal("0")
        balances = account.get("balances", []) if isinstance(account, dict) else []
        if isinstance(balances, list):
            for row in balances:
                if not isinstance(row, dict):
                    continue
                asset = str(row.get("asset", "")).upper()
                if asset == c.base_asset:
                    base_free = _dec(row.get("free", "0"), "0")
                    base_locked = _dec(row.get("locked", "0"), "0")
                elif asset == c.quote_asset:
                    quote_free = _dec(row.get("free", "0"), "0")
                    quote_locked = _dec(row.get("locked", "0"), "0")

        cond_w = close_w < (low_w + c.margin_low_w) < mm_w
        cond_h = close_h < (low_h + c.margin_low_h) < mm_h
        equity = quote_free + (base_free + base_locked) * close_h
        drawdown, trading_blocked = self._register_equity(equity)
        prev_eq = self._last_equity_usdt
        self._last_equity_usdt = equity
        self._record_return(prev_eq, equity)
        self._emit(
            "SYSTEM",
            "masha:equity_snapshot",
            {
                "equity_usdt": str(equity),
                "capital_usdt": str(quote_free),
                "peak_equity_usdt": str(self._peak_equity_usdt or equity),
                "drawdown_pct": str(drawdown),
                "trading_blocked": trading_blocked,
            },
        )
        if dca_price > 0 and c.stop_loss_pct > 0 and close_h <= (dca_price * (Decimal("1") - c.stop_loss_pct)):
            stop_price = dca_price * (Decimal("1") - c.stop_loss_pct)
            payload = {
                "symbol": symbol,
                "dca_price": str(dca_price),
                "market_price": str(close_h),
                "stop_price": str(stop_price),
            }
            if c.simulated:
                payload["execution"] = "SIMULATED"
                self._emit("WARNING", "masha:stop_loss_triggered", payload)
            else:
                if isinstance(open_orders, list):
                    for order in open_orders:
                        if not isinstance(order, dict):
                            continue
                        if str(order.get("side", "")).upper() != "SELL":
                            continue
                        oid = order.get("orderId")
                        if oid is None:
                            continue
                        cancelled = await self._signed_call(
                            client,
                            lambda oid=oid: client.cancel_order(symbol=symbol, orderId=oid),
                        )
                        self._emit("INFO", "binance:cancel_order_stop_loss", {"symbol": symbol, "response": cancelled})
                sell_qty = _q(base_free, c.qty_decimals)
                if sell_qty > 0:
                    sold = await self._signed_call(
                        client,
                        lambda q=sell_qty: client.create_order(
                            symbol=symbol,
                            side=client.SIDE_SELL,
                            type=client.ORDER_TYPE_MARKET,
                            quantity=str(q),
                        ),
                    )
                    self._emit("INFO", "binance:create_order_sell_market_stop_loss", {"symbol": symbol, "response": sold})
                payload["execution"] = "LIVE"
                self._emit("WARNING", "masha:stop_loss_triggered", payload)
            rep = {
                "preset_id": c.preset_id,
                "symbol": symbol,
                "simulated": c.simulated,
                "trading_enabled": c.trading_enabled,
                "decision": "STOP_LOSS",
                "dca_price": str(dca_price),
                "market_price": str(close_h),
                "stop_price": str(stop_price),
                "loop_interval_sec": c.loop_interval_sec,
            }
            self._maybe_emit_metrics()
            return rep
        should_buy = cond_w and cond_h
        below_last_buy = self._last_buy_price is None or close_h < self._last_buy_price
        enough_quote = quote_free > c.quote_min_free_to_operate
        can_execute = should_buy and enough_quote and below_last_buy and (not trading_blocked)

        report: dict[str, Any] = {
            "preset_id": c.preset_id,
            "symbol": symbol,
            "base_asset": c.base_asset,
            "quote_asset": c.quote_asset,
            "simulated": c.simulated,
            "trading_enabled": c.trading_enabled,
            "decision": "BUY_AND_REPRICE_SELL" if can_execute else "WAIT",
            "condition_w": cond_w,
            "condition_h": cond_h,
            "enough_quote": enough_quote,
            "below_last_buy": below_last_buy,
            "close_w": str(close_w),
            "close_h": str(close_h),
            "mm_w": str(mm_w),
            "mm_h": str(mm_h),
            "low_w": str(low_w),
            "low_h": str(low_h),
            "quote_free": str(quote_free),
            "quote_locked": str(quote_locked),
            "base_free": str(base_free),
            "base_locked": str(base_locked),
            "dca_price": str(dca_price),
            "dca_volume": str(dca_volume),
            "dca_cost": str(dca_cost),
            "loop_interval_sec": c.loop_interval_sec,
            "trading_blocked": trading_blocked,
            "drawdown_pct": str(drawdown),
        }
        # T0.1: Count active DCA rungs (open SELL orders = active positions)
        sell_orders = [o for o in (open_orders if isinstance(open_orders, list) else [])
                       if str(o.get("side", "")).upper() == "SELL"]
        active_rungs = len(sell_orders)
        report["active_rungs"] = active_rungs
        report["max_rungs"] = c.max_rungs_per_symbol

        if not can_execute:
            self._maybe_emit_metrics()
            return report

        # T0.1: Block new buys when rung ceiling is reached
        if active_rungs >= c.max_rungs_per_symbol:
            report["decision"] = "BLOCKED_MAX_RUNGS"
            self._emit(
                "WARNING",
                f"masha:max_rungs_reached {active_rungs}/{c.max_rungs_per_symbol}",
                {"report": report},
            )
            self._maybe_emit_metrics()
            return report

        # T1.1: Regime filter gate
        try:
            from runtime.core.regime_filter import get_regime_filter
            regime_ok, regime_reason = await get_regime_filter().is_favorable(
                symbol, client, _to_thread=self._to_thread,
            )
            if not regime_ok:
                report["decision"] = "BLOCKED_REGIME"
                report["regime_reason"] = regime_reason
                self._emit("WARNING", f"masha:regime_blocked {regime_reason}", {"report": report})
                self._maybe_emit_metrics()
                return report
        except Exception:
            # FAIL-CLOSED: if regime filter fails, block the trade
            report["decision"] = "BLOCKED_REGIME"
            report["regime_reason"] = "FAIL_CLOSED:regime_filter_error"
            self._emit("WARNING", "masha:regime_blocked FAIL_CLOSED", {"report": report})
            self._maybe_emit_metrics()
            return report

        planned_buy_qty = _q(c.buy_qty_base, c.qty_decimals)
        report["planned_buy_qty_base"] = str(planned_buy_qty)

        if c.simulated:
            report["execution"] = "SIMULATED"
            report["message"] = "Dry run only; no orders sent."
            self._emit("INFO", "masha:decision", {"report": report})
            log_paper_trade("masha", symbol, report.get("decision", ""), report)
            self._maybe_emit_metrics()
            return report

        buy = await self._signed_call(
            client,
            lambda: client.create_order(
                symbol=symbol,
                side=client.SIDE_BUY,
                type=client.ORDER_TYPE_MARKET,
                quantity=str(planned_buy_qty),
            ),
        )
        self._emit("INFO", "binance:create_order_buy_market", {"symbol": symbol, "response": buy})
        fills = buy.get("fills") if isinstance(buy, dict) else None
        if isinstance(fills, list) and fills:
            buy_price = _dec(fills[0].get("price", "0"), "0")
            buy_qty = _dec(fills[0].get("qty", "0"), "0")
        else:
            buy_qty = _dec((buy or {}).get("executedQty", "0"), "0")
            quote_cost = _dec((buy or {}).get("cummulativeQuoteQty", "0"), "0")
            buy_price = quote_cost / buy_qty if buy_qty > 0 else Decimal("0")
        self._last_buy_price = buy_price if buy_price > 0 else self._last_buy_price
        buy_cost = buy_price * buy_qty

        total_cost = dca_cost + buy_cost
        total_volume = dca_volume + buy_qty
        if total_volume <= 0:
            raise RuntimeError("Invalid DCA volume after buy")
        dca_new_price = total_cost / total_volume
        target_sell_price = _q(
            dca_new_price * (Decimal("1") + c.profit_factor),
            c.price_decimals,
        )
        target_sell_qty = _q(total_volume, c.qty_decimals)

        # Cancel previous SELL LIMITs first (same as original script).
        if isinstance(open_orders, list):
            for order in open_orders:
                if not isinstance(order, dict):
                    continue
                if str(order.get("side", "")).upper() == "SELL" and str(order.get("type", "")).upper() == "LIMIT":
                    oid = order.get("orderId")
                    if oid is None:
                        continue
                    cancelled = await self._signed_call(
                        client,
                        lambda oid=oid: client.cancel_order(symbol=symbol, orderId=oid),
                    )
                    self._emit(
                        "INFO",
                        "binance:cancel_order_sell_limit",
                        {"symbol": symbol, "response": cancelled},
                    )

        sell = await self._signed_call(
            client,
            lambda: client.create_order(
                symbol=symbol,
                side=client.SIDE_SELL,
                type=client.ORDER_TYPE_LIMIT,
                timeInForce=client.TIME_IN_FORCE_GTC,
                quantity=str(target_sell_qty),
                price=str(target_sell_price),
            ),
        )
        self._emit("INFO", "binance:create_order_sell_limit", {"symbol": symbol, "response": sell})
        report["execution"] = "LIVE"
        report["buy_order_id"] = (buy or {}).get("orderId")
        report["sell_order_id"] = (sell or {}).get("orderId")
        report["filled_buy_price"] = str(buy_price)
        report["filled_buy_qty"] = str(buy_qty)
        report["new_dca_price"] = str(dca_new_price)
        report["target_sell_price"] = str(target_sell_price)
        report["target_sell_qty"] = str(target_sell_qty)
        self._emit("INFO", "masha:decision", {"report": report})
        self._maybe_emit_metrics()
        return report
