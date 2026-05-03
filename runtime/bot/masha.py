"""Masha2.0-inspired multi-timeframe DCA strategy runner."""

from __future__ import annotations

import asyncio
import datetime as dt
import time
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Any, Callable, Optional

from binance.client import Client

from runtime.connectors.binance_gateway import normalize_binance_spot_symbol
from runtime.core.security_util import sanitize_log_message


def _dec(x: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(x))
    except Exception:
        return Decimal(default)


def _q(x: Decimal, places: int) -> Decimal:
    if places < 0:
        places = 0
    step = Decimal(10) ** Decimal(-places)
    return x.quantize(step, rounding=ROUND_DOWN)


@dataclass
class MashaConfig:
    preset_id: str = "M2"
    symbol: str = "BTCUSDT"
    base_asset: str = "BTC"
    quote_asset: str = "USDT"
    loop_interval_sec: int = 300
    quote_min_free_to_operate: Decimal = Decimal("6")
    buy_qty_base: Decimal = Decimal("0.001")
    profit_factor: Decimal = Decimal("0.01")
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
        self.profit_factor = max(_dec(self.profit_factor), Decimal("0"))
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


class MashaRunner:
    def __init__(
        self,
        log: Callable[[str], None],
        event_log: Optional[Callable[[str, str, Optional[dict[str, Any]]], None]] = None,
    ) -> None:
        self.config = MashaConfig()
        self.config.normalize()
        self._log = log
        self._event_log = event_log
        self._task: Optional[asyncio.Task[Any]] = None
        self._stop = asyncio.Event()
        self._last_report: dict[str, Any] = {}
        self._last_error: Optional[str] = None
        self._last_cycle_ts: Optional[str] = None
        self._api_key: Optional[str] = None
        self._api_secret: Optional[str] = None
        self._client: Optional[Client] = None
        self._error_streak = 0
        self._last_buy_price: Optional[Decimal] = None
        self._peak_equity_usdt: Optional[Decimal] = None
        self._last_equity_usdt: Optional[Decimal] = None
        self._max_drawdown_seen: Decimal = Decimal("0")
        self._equity_returns: list[Decimal] = []
        self._cycle_count = 0

    def _emit(self, level: str, message: str, payload: Optional[dict[str, Any]] = None) -> None:
        if self._event_log is not None:
            try:
                self._event_log(level, message, payload)
                return
            except Exception:
                pass
        self._log(message)

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def last_report(self) -> dict[str, Any]:
        return dict(self._last_report)

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def last_cycle_ts(self) -> Optional[str]:
        return self._last_cycle_ts

    def apply_config(self, cfg: MashaConfig) -> None:
        cfg.normalize()
        self.config = cfg

    def set_credentials(self, api_key: str, api_secret: str) -> None:
        self._api_key = api_key.strip()
        self._api_secret = api_secret.strip()

    def _ensure_client(self) -> Client:
        if not self._api_key or not self._api_secret:
            raise RuntimeError("No credentials resolved for bot")
        if self._client is None:
            self._client = Client(
                self._api_key,
                self._api_secret,
                requests_params={"timeout": 30},
            )
        return self._client

    async def _to_thread(self, fn: Callable[[], Any]) -> Any:
        return await asyncio.to_thread(fn)

    def restore_risk_state(
        self,
        *,
        peak_equity_usdt: Optional[str] = None,
        max_drawdown_seen: Optional[str] = None,
        cycle_count: Optional[int] = None,
    ) -> None:
        if peak_equity_usdt is not None:
            v = _dec(peak_equity_usdt, "0")
            self._peak_equity_usdt = v if v > 0 else None
        if max_drawdown_seen is not None:
            self._max_drawdown_seen = max(Decimal("0"), _dec(max_drawdown_seen, "0"))
        if cycle_count is not None:
            self._cycle_count = max(0, int(cycle_count))

    def _register_equity(self, equity: Decimal) -> tuple[Decimal, bool]:
        if self._peak_equity_usdt is None or equity > self._peak_equity_usdt:
            self._peak_equity_usdt = equity
        peak = self._peak_equity_usdt or equity
        dd = Decimal("0")
        if peak > 0:
            dd = (peak - equity) / peak
        if dd > self._max_drawdown_seen:
            self._max_drawdown_seen = dd
        blocked = dd > self.config.max_drawdown_pct
        return dd, blocked

    def _record_return(self, equity: Decimal) -> None:
        prev = self._last_equity_usdt
        self._last_equity_usdt = equity
        if prev is None or prev <= 0:
            return
        r = (equity - prev) / prev
        self._equity_returns.append(r)
        if len(self._equity_returns) > 500:
            self._equity_returns = self._equity_returns[-500:]

    def _compute_metrics(self) -> dict[str, Any]:
        rs = self._equity_returns
        n = len(rs)
        if n == 0:
            return {"sharpe": "0", "win_rate": "0", "max_drawdown": str(self._max_drawdown_seen), "samples": 0}
        wins = sum(1 for r in rs if r > 0)
        mean = sum(rs, Decimal("0")) / Decimal(n)
        var = sum((r - mean) * (r - mean) for r in rs) / Decimal(n)
        std = var.sqrt() if var > 0 else Decimal("0")
        sharpe = (mean / std) * Decimal(n).sqrt() if std > 0 else Decimal("0")
        return {
            "sharpe": str(sharpe),
            "win_rate": str(Decimal(wins) / Decimal(n)),
            "max_drawdown": str(self._max_drawdown_seen),
            "samples": n,
        }

    def _maybe_emit_metrics(self) -> None:
        self._cycle_count += 1
        if self._cycle_count % self.config.metrics_interval_cycles == 0:
            self._emit("SYSTEM", "masha:metrics", self._compute_metrics())

    async def _sync_time_for_signed(self, client: Client) -> None:
        data = await self._to_thread(lambda: client.get_server_time())
        server_ms = int((data or {}).get("serverTime", 0) or 0)
        local_ms = int(time.time() * 1000)
        offset_ms = server_ms - local_ms
        try:
            client.timestamp_offset = offset_ms
        except Exception:
            pass
        self._emit(
            "INFO",
            f"masha:time_sync offset_ms={offset_ms}",
            {"server_time": data, "offset_ms": offset_ms},
        )

    async def _signed_call(self, client: Client, fn: Callable[[], Any]) -> Any:
        try:
            return await self._to_thread(fn)
        except Exception as e:
            # Retry once after timestamp sync to match original script's tolerance.
            if "-1021" not in str(e):
                raise
            await self._sync_time_for_signed(client)
            return await self._to_thread(fn)

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
            from runtime.core.market_cache import get_market_cache
            _cache = get_market_cache()
            open_orders = await _cache.get_or_fetch(
                f"open_orders:{symbol}",
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
            from runtime.core.market_cache import get_market_cache
            _cache = get_market_cache()
            account = await _cache.get_or_fetch(
                "account",
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
        self._record_return(equity)
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
        if not can_execute:
            self._maybe_emit_metrics()
            return report

        planned_buy_qty = _q(c.buy_qty_base, c.qty_decimals)
        report["planned_buy_qty_base"] = str(planned_buy_qty)

        if c.simulated:
            report["execution"] = "SIMULATED"
            report["message"] = "Dry run only; no orders sent."
            self._emit("INFO", "masha:decision", {"report": report})
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

    async def sync_time(self) -> dict[str, Any]:
        client = self._ensure_client()
        data = await self._to_thread(lambda: client.get_server_time())
        server_ms = int(data.get("serverTime", 0) or 0)
        local_ms = int(time.time() * 1000)
        offset_ms = server_ms - local_ms
        try:
            client.timestamp_offset = offset_ms
        except Exception:
            pass
        self._emit(
            "INFO",
            f"masha:time_sync offset_ms={offset_ms}",
            {"server_time": data, "offset_ms": offset_ms},
        )
        return {
            "local_time_ms": local_ms,
            "server_time_ms": server_ms,
            "offset_ms": offset_ms,
            "source": "masha",
        }

    async def _loop(self) -> None:
        while not self._stop.is_set():
            sleep_sec = float(self.config.loop_interval_sec)
            # ── Governor permission gate ─────────────────────────
            try:
                from runtime.core.weight_governor import get_weight_governor
                gov = get_weight_governor()
                bot_key = f"masha:{self.config.symbol}"
                wait = gov.request_permission(bot_key)
                if wait == float('inf'):
                    self._emit("WARNING", "governor:LOCKOUT — ciclo omitido (zona emergencia)")
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=sleep_sec)
                    except asyncio.TimeoutError:
                        pass
                    continue
                if wait > 0:
                    self._emit("INFO", f"governor:throttle — esperando {wait:.1f}s")
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=wait)
                    except asyncio.TimeoutError:
                        pass
                    if self._stop.is_set():
                        break
            except Exception:
                pass  # Governor unavailable — proceed normally
            try:
                rep = await self.run_once()

                self._last_report = rep
                self._last_error = None
                self._last_cycle_ts = dt.datetime.now(dt.timezone.utc).isoformat()
                self._error_streak = 0
                self._emit(
                    "INFO",
                    f"masha:{rep.get('decision')} symbol={rep.get('symbol')} simulated={rep.get('simulated')}",
                    {"report": rep},
                )
                # Report cycle to coordinator for phase tracking
                try:
                    from runtime.core.bot_coordinator import get_bot_coordinator
                    get_bot_coordinator().report_cycle(f"masha:{self.config.symbol}")
                except Exception:
                    pass
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._last_error = sanitize_log_message(str(e))
                self._error_streak += 1
                if self._client is not None:
                    try:
                        self._client.session.close()
                    except Exception:
                        pass
                    self._client = None
                sleep_sec = min(
                    60.0,
                    max(2.0, min(float(self.config.loop_interval_sec), float(2 ** min(self._error_streak, 6)))),
                )
                self._emit("ERROR", f"masha:error {self._last_error}", {"error": self._last_error})
                self._emit(
                    "WARNING",
                    f"masha:retry_in {sleep_sec:.0f}s (streak={self._error_streak})",
                    {"retry_sec": sleep_sec, "streak": self._error_streak},
                )
            # Add coordinator jitter to prevent cycle collisions
            try:
                from runtime.core.bot_coordinator import get_bot_coordinator
                jitter = get_bot_coordinator().compute_jitter(f"masha:{self.config.symbol}")
                if jitter > 0:
                    sleep_sec += jitter
            except Exception:
                pass
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=sleep_sec)
            except asyncio.TimeoutError:
                pass

    async def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        t = self._task
        if t is not None:
            t.cancel()
            await asyncio.gather(t, return_exceptions=True)
        self._task = None
        if self._client is not None:
            try:
                self._client.session.close()
            except Exception:
                pass
            self._client = None
