"""Masha2.0-inspired multi-timeframe DCA strategy runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Callable, Optional

from binance.client import Client

from runtime.bot._base_runner import BaseStrategyRunner
from runtime.bot._decimal_utils import dec as _dec, quantize as _q
from runtime.bot._paper_log import log_paper_trade
from runtime.connectors.binance_gateway import normalize_binance_spot_symbol


# _dec and _q imported from runtime.bot._decimal_utils


import random
import time
import uuid

@dataclass
class MashaConfig:
    preset_id: str = "M2"
    symbols_csv: str = "BTCUSDT"
    loop_interval_sec: int = 59
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
    note: str = ""
    max_drawdown_pct: Decimal = Decimal("0.25")
    stop_loss_pct: Decimal = Decimal("0.20")  # DCA-wide: avoid premature exit
    metrics_interval_cycles: int = 5
    max_rungs_per_symbol: int = 3  # Conservative: limits BTC exposure
    simulated: bool = False
    trading_enabled: bool = True

    def normalize(self) -> None:
        self.simulated = False
        symbols = []
        for raw in (self.symbols_csv or "").split(","):
            s = raw.strip().upper()
            if not s:
                continue
            try:
                symbols.append(normalize_binance_spot_symbol(s))
            except Exception:
                continue
        if not symbols:
            symbols = ["BTCUSDT"]
        self.symbols_csv = ",".join(symbols)
        self.loop_interval_sec = max(1, min(int(self.loop_interval_sec), 86_400))
        self.quote_min_free_to_operate = max(_dec(self.quote_min_free_to_operate, "0.0001"), Decimal("0.0001"))
        self.buy_qty_base = max(_dec(self.buy_qty_base, "0.00000001"), Decimal("0.00000001"))
        self.profit_factor = max(_dec(self.profit_factor), Decimal("0.03"))
        self.margin_low_w = max(_dec(self.margin_low_w), Decimal("0"))
        self.margin_low_h = max(_dec(self.margin_low_h), Decimal("0"))
        self.periods_w = max(1, min(int(self.periods_w), 1000))
        self.mm_periods_w = max(1, min(int(self.mm_periods_w), self.periods_w))
        self.periods_h = max(1, min(int(self.periods_h), 1000))
        self.mm_periods_h = max(1, min(int(self.mm_periods_h), self.periods_h))
        self.note = (self.note or "").strip()[:20]
        self.max_drawdown_pct = max(_dec(self.max_drawdown_pct), Decimal("0"))
        self.stop_loss_pct = max(_dec(self.stop_loss_pct), Decimal("0"))
        self.metrics_interval_cycles = max(1, min(int(self.metrics_interval_cycles), 10_000))
        self.max_rungs_per_symbol = max(1, min(int(self.max_rungs_per_symbol), 100))

    def symbols(self) -> list[str]:
        return [s for s in self.symbols_csv.split(",") if s]

    def as_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["quote_min_free_to_operate"] = str(self.quote_min_free_to_operate)
        d["buy_qty_base"] = str(self.buy_qty_base)
        d["profit_factor"] = str(self.profit_factor)
        d["margin_low_w"] = str(self.margin_low_w)
        d["margin_low_h"] = str(self.margin_low_h)
        d["max_drawdown_pct"] = str(self.max_drawdown_pct)
        d["stop_loss_pct"] = str(self.stop_loss_pct)
        d["symbols"] = self.symbols()
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
        self._active_symbol: Optional[str] = None
        self._runner_id = uuid.uuid4().hex[:8]

    def restore_risk_state(self, **kwargs: Any) -> None:
        super().restore_risk_state(**{k: v for k, v in kwargs.items() if k != "active_symbol"})
        if "active_symbol" in kwargs:
            self._active_symbol = kwargs["active_symbol"]

    def apply_config(self, cfg: MashaConfig) -> None:
        cfg.normalize()
        self.config = cfg

    def _bot_key(self) -> str:
        return f"masha:{self._active_symbol or self.config.symbols_csv[:20]}"

    def _loop_log_summary(self, report: dict[str, Any]) -> str:
        return f"masha:{report.get('decision')} symbol={report.get('symbol', 'None')} simulated={report.get('simulated')}"

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

    async def _resolve_precision(self, client: Client, symbol: str) -> tuple[int, int]:
        try:
            info = await self._to_thread(lambda: client.get_symbol_info(symbol))
        except Exception:
            return 8, 8
        if not isinstance(info, dict):
            return 8, 8
        filters = info.get("filters", [])
        p_dec, q_dec = 8, 8
        for f in filters:
            if not isinstance(f, dict): continue
            ftype = str(f.get("filterType", "")).upper()
            if ftype == "PRICE_FILTER":
                tick = str(f.get("tickSize", "0")).rstrip("0").split(".")
                if len(tick) > 1: p_dec = len(tick[1])
                elif float(f.get("tickSize", "0")) == 1: p_dec = 0
            elif ftype == "LOT_SIZE":
                step = str(f.get("stepSize", "0")).rstrip("0").split(".")
                if len(step) > 1: q_dec = len(step[1])
                elif float(f.get("stepSize", "0")) == 1: q_dec = 0
        return p_dec, q_dec

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
        await self._sync_time_for_signed(client)

        symbols = c.symbols()
        if not symbols:
            return {"decision": "WAIT", "message": "No symbols configured"}

        # Fetch global open orders to find our active slots
        try:
            from runtime.core.market_cache import get_market_cache, MarketCache
            _cache = get_market_cache()
            open_orders = await _cache.get_or_fetch(
                MarketCache.scoped_key("open_orders_global", self._api_key),
                lambda: self._signed_call(client, client.get_open_orders),
                ttl_sec=15
            )
        except Exception:
            open_orders = await self._signed_call(client, client.get_open_orders)
        
        my_tag = f"masha-{getattr(self, '_bot_id', self._runner_id)}"
        
        # Determine active symbol by checking if we own any SELL LIMIT orders
        detected_active_symbol = None
        dca_price = Decimal("0")
        dca_volume = Decimal("0")
        dca_cost = Decimal("0")
        my_sell_orders = []
        
        if isinstance(open_orders, list):
            for order in open_orders:
                if not isinstance(order, dict): continue
                cid = str(order.get("clientOrderId", ""))
                sym = str(order.get("symbol", ""))
                if cid.startswith(my_tag) and str(order.get("side", "")).upper() == "SELL" and str(order.get("type", "")).upper() == "LIMIT":
                    detected_active_symbol = sym
                    my_sell_orders.append(order)
                    dca_price = _dec(order.get("price", "0"), "0")
                    dca_volume = _dec(order.get("origQty", order.get("executedQty", "0")), "0")
                    dca_cost = dca_price * dca_volume
        
        # Re-lock if we found orders, or use persisted state, or stay None
        if detected_active_symbol:
            self._active_symbol = detected_active_symbol
        elif self._active_symbol and self._active_symbol not in symbols:
            # If our persisted active_symbol isn't in open orders, the position likely closed! Unlock.
            self._active_symbol = None
            
        symbol = self._active_symbol
        is_hunting = (symbol is None)
        
        try:
            account = await self._signed_call(client, client.get_account)
        except Exception:
            account = {}
        
        balances = account.get("balances", []) if isinstance(account, dict) else []
        quote_free = Decimal("0")
        for row in balances:
            if not isinstance(row, dict): continue
            if str(row.get("asset", "")).upper() == "USDT":
                quote_free = _dec(row.get("free", "0"), "0")

        report: dict[str, Any] = {
            "preset_id": c.preset_id,
            "simulated": c.simulated,
            "trading_enabled": c.trading_enabled,
            "loop_interval_sec": c.loop_interval_sec,
        }

        if is_hunting:
            random.shuffle(symbols)
            for sym in symbols:
                try:
                    mm_w, low_w, close_w = await self._ohlc_signal(client, sym, c.timeframe_w, c.periods_w, c.mm_periods_w)
                    mm_h, low_h, close_h = await self._ohlc_signal(client, sym, c.timeframe_h, c.periods_h, c.mm_periods_h)
                    
                    cond_w = close_w < (low_w + c.margin_low_w) < mm_w
                    cond_h = close_h < (low_h + c.margin_low_h) < mm_h
                    if cond_w and cond_h:
                        symbol = sym
                        self._active_symbol = sym
                        self._last_buy_price = None  # Reset for new asset
                        report["close_h"] = str(close_h)
                        break
                except Exception as e:
                    self._emit("DEBUG", f"hunting_error {sym}: {e}")
                    continue
                    
        if not symbol:
            report["decision"] = "WAIT_HUNTING"
            report["message"] = f"Hunting across {len(symbols)} symbols. No conditions met."
            self._emit("INFO", "masha:decision", {"report": report})
            self._maybe_emit_metrics()
            return report

        # We have an active symbol (either locked or just acquired)
        report["symbol"] = symbol
        base_asset = symbol.replace("USDT", "")
        base_free = Decimal("0")
        base_locked = Decimal("0")
        for row in balances:
            if not isinstance(row, dict): continue
            if str(row.get("asset", "")).upper() == base_asset:
                base_free = _dec(row.get("free", "0"), "0")
                base_locked = _dec(row.get("locked", "0"), "0")

        if "close_h" not in report:
            try:
                ticker = await self._to_thread(lambda: client.get_symbol_ticker(symbol=symbol))
                close_h = _dec((ticker or {}).get("price", "0"), "0")
            except Exception:
                close_h = Decimal("0")

        equity = quote_free + (base_free + base_locked) * close_h
        drawdown, trading_blocked = self._register_equity(equity)
        prev_eq = self._last_equity_usdt
        self._last_equity_usdt = equity
        self._record_return(prev_eq, equity)
        self._emit("SYSTEM", "masha:equity_snapshot", {
            "equity_usdt": str(equity), "capital_usdt": str(quote_free),
            "peak_equity_usdt": str(self._peak_equity_usdt or equity),
            "drawdown_pct": str(drawdown), "trading_blocked": trading_blocked,
        })
        
        # Stop Loss Check
        if dca_price > 0 and c.stop_loss_pct > 0 and close_h > 0 and close_h <= (dca_price * (Decimal("1") - c.stop_loss_pct)):
            stop_price = dca_price * (Decimal("1") - c.stop_loss_pct)
            if not c.simulated:
                for order in my_sell_orders:
                    oid = order.get("orderId")
                    if oid:
                        await self._signed_call(client, lambda oid=oid: client.cancel_order(symbol=symbol, orderId=oid))
                p_dec, q_dec = await self._resolve_precision(client, symbol)
                sell_qty = _q(base_free, q_dec)
                if sell_qty > 0:
                    sold = await self._signed_call(
                        client, lambda q=sell_qty: client.create_order(
                            symbol=symbol, side=client.SIDE_SELL, type=client.ORDER_TYPE_MARKET,
                            quantity=str(q), newClientOrderId=f"{my_tag}-sl-{int(time.time())}"
                        )
                    )
            self._active_symbol = None  # Unlock
            rep = {"decision": "STOP_LOSS", "symbol": symbol, "dca_price": str(dca_price), "stop_price": str(stop_price)}
            self._emit("WARNING", "masha:stop_loss_triggered", rep)
            self._maybe_emit_metrics()
            return rep

        if is_hunting:
            # We just found it, condition is already known true
            cond_w, cond_h = True, True
            below_last_buy = True
        else:
            try:
                mm_w, low_w, close_w = await self._ohlc_signal(client, symbol, c.timeframe_w, c.periods_w, c.mm_periods_w)
                mm_h, low_h, close_h = await self._ohlc_signal(client, symbol, c.timeframe_h, c.periods_h, c.mm_periods_h)
                cond_w = close_w < (low_w + c.margin_low_w) < mm_w
                cond_h = close_h < (low_h + c.margin_low_h) < mm_h
            except Exception:
                cond_w, cond_h = False, False

        below_last_buy = self._last_buy_price is None or close_h < self._last_buy_price
        enough_quote = quote_free > c.quote_min_free_to_operate
        can_execute = cond_w and cond_h and enough_quote and below_last_buy and (not trading_blocked)

        active_rungs = len(my_sell_orders)
        report.update({
            "decision": "BUY_AND_REPRICE_SELL" if can_execute else "WAIT_DCA",
            "condition_w": cond_w, "condition_h": cond_h, "enough_quote": enough_quote,
            "below_last_buy": below_last_buy, "close_h": str(close_h),
            "quote_free": str(quote_free), "base_free": str(base_free),
            "dca_price": str(dca_price), "dca_volume": str(dca_volume), "dca_cost": str(dca_cost),
            "active_rungs": active_rungs, "max_rungs": c.max_rungs_per_symbol,
            "trading_blocked": trading_blocked, "drawdown_pct": str(drawdown),
        })

        if not can_execute:
            self._emit("INFO", "masha:decision", {"report": report})
            self._maybe_emit_metrics()
            return report

        if active_rungs >= c.max_rungs_per_symbol:
            report["decision"] = "BLOCKED_MAX_RUNGS"
            self._emit("WARNING", f"masha:max_rungs_reached {active_rungs}/{c.max_rungs_per_symbol}", {"report": report})
            self._maybe_emit_metrics()
            return report

        # Regime filter removed in v2.0 — replaced by TrendSignal dual-gate system.
        # Masha is OFF by directive; when reactivated, integrate TrendSignal here.

        p_dec, q_dec = await self._resolve_precision(client, symbol)
        planned_buy_qty = _q(c.buy_qty_base, q_dec)
        planned_quote_cost = planned_buy_qty * close_h

        try:
            from runtime.core.budget_guard import get_budget_guard
            bg = get_budget_guard()
            if not c.simulated and not bg.try_reserve(self._bot_key(), symbol, planned_quote_cost):
                report["decision"] = "BLOCKED_BUDGET"
                self._emit("WARNING", "masha:budget_blocked", {"report": report})
                self._maybe_emit_metrics()
                return report
        except Exception as e:
            report["decision"] = "BLOCKED_BUDGET"
            self._emit("WARNING", f"masha:budget_error {e}", {"report": report})
            self._maybe_emit_metrics()
            return report

        if c.simulated:
            report["execution"] = "SIMULATED"
            self._emit("INFO", "masha:decision", {"report": report})
            self._maybe_emit_metrics()
            return report

        # LIVE BUY
        buy_cid = f"{my_tag}-buy-{int(time.time())}"
        buy = await self._signed_call(
            client, lambda: client.create_order(
                symbol=symbol, side=client.SIDE_BUY, type=client.ORDER_TYPE_MARKET,
                quantity=str(planned_buy_qty), newClientOrderId=buy_cid
            )
        )
        self._emit("INFO", "binance:create_order_buy_market", {"symbol": symbol, "response": buy})
        
        fills = buy.get("fills") if isinstance(buy, dict) else None
        if isinstance(fills, list) and fills:
            buy_price = _dec(fills[0].get("price", "0"), "0")
            buy_qty = _dec(fills[0].get("qty", "0"), "0")
        else:
            buy_qty = _dec((buy or {}).get("executedQty", "0"), "0")
            quote_cost = _dec((buy or {}).get("cummulativeQuoteQty", "0"), "0")
            buy_price = quote_cost / buy_qty if buy_qty > 0 else close_h
            
        self._last_buy_price = buy_price if buy_price > 0 else self._last_buy_price
        buy_cost = buy_price * buy_qty

        total_cost = dca_cost + buy_cost
        total_volume = dca_volume + buy_qty
        dca_new_price = total_cost / total_volume if total_volume > 0 else close_h
        target_sell_price = _q(dca_new_price * (Decimal("1") + c.profit_factor), p_dec)
        target_sell_qty = _q(total_volume, q_dec)

        # Cancel previous SELL LIMITs
        for order in my_sell_orders:
            oid = order.get("orderId")
            if oid:
                await self._signed_call(client, lambda oid=oid: client.cancel_order(symbol=symbol, orderId=oid))

        # LIVE SELL LIMIT
        sell_cid = f"{my_tag}-sell-{int(time.time())}"
        sell = await self._signed_call(
            client, lambda: client.create_order(
                symbol=symbol, side=client.SIDE_SELL, type=client.ORDER_TYPE_LIMIT,
                timeInForce=client.TIME_IN_FORCE_GTC, quantity=str(target_sell_qty),
                price=str(target_sell_price), newClientOrderId=sell_cid
            )
        )
        self._emit("INFO", "binance:create_order_sell_limit", {"symbol": symbol, "response": sell})

        report.update({
            "execution": "LIVE", "buy_order_id": (buy or {}).get("orderId"), "sell_order_id": (sell or {}).get("orderId"),
            "filled_buy_price": str(buy_price), "new_dca_price": str(dca_new_price),
            "target_sell_price": str(target_sell_price), "target_sell_qty": str(target_sell_qty)
        })
        self._emit("INFO", "masha:decision", {"report": report})
        self._maybe_emit_metrics()
        return report
