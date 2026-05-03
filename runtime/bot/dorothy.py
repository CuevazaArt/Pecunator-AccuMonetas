"""ExampleJV-inspired rule set with safe defaults (simulated by default)."""

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
class DorothyConfig:
    # Preset B with safe mode defaults.
    preset_id: str = "B"
    symbol: str = "XRPUSDT"
    loop_interval_sec: int = 450
    quote_order_qty: Decimal = Decimal("8")
    profit_factor: Decimal = Decimal("0.05")
    margin_drop_factor: Decimal = Decimal("0.004")
    qty_decimals: int = 8
    price_decimals: int = 4
    note: str = ""
    # [MEJORA] Proteccion de riesgo configurable.
    max_drawdown_pct: Decimal = Decimal("0.20")
    stop_loss_pct: Decimal = Decimal("0.10")
    metrics_interval_cycles: int = 5
    simulated: bool = True
    trading_enabled: bool = False

    def normalize(self) -> None:
        self.symbol = normalize_binance_spot_symbol(self.symbol)
        self.loop_interval_sec = max(1, min(int(self.loop_interval_sec), 86_400))
        self.quote_order_qty = max(_dec(self.quote_order_qty, "0.0001"), Decimal("0.0001"))
        self.profit_factor = max(_dec(self.profit_factor), Decimal("0"))
        self.margin_drop_factor = max(_dec(self.margin_drop_factor), Decimal("0"))
        self.qty_decimals = max(0, min(int(self.qty_decimals), 18))
        self.price_decimals = max(0, min(int(self.price_decimals), 18))
        self.note = (self.note or "").strip()[:20]
        self.max_drawdown_pct = max(_dec(self.max_drawdown_pct), Decimal("0"))
        self.stop_loss_pct = max(_dec(self.stop_loss_pct), Decimal("0"))
        self.metrics_interval_cycles = max(1, min(int(self.metrics_interval_cycles), 10_000))

    def as_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["quote_order_qty"] = str(self.quote_order_qty)
        d["profit_factor"] = str(self.profit_factor)
        d["margin_drop_factor"] = str(self.margin_drop_factor)
        d["max_drawdown_pct"] = str(self.max_drawdown_pct)
        d["stop_loss_pct"] = str(self.stop_loss_pct)
        d["mode"] = "SIMULATED" if self.simulated else "LIVE"
        return d


class DorothyRunner:
    def __init__(
        self,
        log: Callable[[str], None],
        event_log: Optional[Callable[[str, str, Optional[dict[str, Any]]], None]] = None,
    ) -> None:
        self.config = DorothyConfig()
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
        # [MEJORA] Estado persistible por eventos (SQLite en servicios hub).
        self._peak_equity_usdt: Optional[Decimal] = None
        self._last_equity_usdt: Optional[Decimal] = None
        self._max_drawdown_seen: Decimal = Decimal("0")
        self._equity_returns: list[Decimal] = []
        self._cycle_count = 0

    def _emit(
        self,
        level: str,
        message: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
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

    def apply_config(self, cfg: DorothyConfig) -> None:
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

    async def _compute_equity_usdt(self, client: Client, base_asset: str = "USDT") -> tuple[Decimal, Decimal]:
        # Use MarketCache: account/tickers are shared across ALL bots
        try:
            from runtime.core.market_cache import get_market_cache
            _cache = get_market_cache()
            account = await _cache.get_or_fetch(
                "account",
                lambda: self._to_thread(client.get_account),
            )
            tickers = await _cache.get_or_fetch(
                "tickers",
                lambda: self._to_thread(client.get_all_tickers),
            )
        except Exception:
            # Fallback: direct call if cache unavailable
            account = await self._to_thread(client.get_account)
            tickers = await self._to_thread(client.get_all_tickers)
        prices: dict[str, Decimal] = {}
        if isinstance(tickers, list):
            for t in tickers:
                if isinstance(t, dict):
                    prices[str(t.get("symbol", "")).upper()] = _dec(t.get("price", "0"), "0")
        equity = Decimal("0")
        base_free = Decimal("0")
        balances = account.get("balances", []) if isinstance(account, dict) else []
        if isinstance(balances, list):
            for b in balances:
                if not isinstance(b, dict):
                    continue
                asset = str(b.get("asset", "")).upper()
                free = _dec(b.get("free", "0"), "0")
                locked = _dec(b.get("locked", "0"), "0")
                total = free + locked
                if total <= 0:
                    continue
                if asset == base_asset:
                    equity += total
                    base_free = free
                    continue
                px = prices.get(f"{asset}{base_asset}")
                if px and px > 0:
                    equity += total * px
        return equity, base_free

    def _register_equity(self, equity: Decimal) -> tuple[Decimal, bool]:
        if self._peak_equity_usdt is None or equity > self._peak_equity_usdt:
            self._peak_equity_usdt = equity
        peak = self._peak_equity_usdt or equity
        dd = Decimal("0")
        if peak > 0:
            dd = (peak - equity) / peak
        if dd > self._max_drawdown_seen:
            self._max_drawdown_seen = dd
        if self._equity_returns:
            prev = self._equity_returns[-1]
            _ = prev
        blocked = dd > self.config.max_drawdown_pct
        return dd, blocked

    def _record_return(self, prev_equity: Optional[Decimal], equity: Decimal) -> None:
        if prev_equity is None or prev_equity <= 0:
            return
        r = (equity - prev_equity) / prev_equity
        self._equity_returns.append(r)
        if len(self._equity_returns) > 500:
            self._equity_returns = self._equity_returns[-500:]

    def _compute_metrics(self) -> dict[str, Any]:
        rs = self._equity_returns
        n = len(rs)
        if n == 0:
            return {
                "sharpe": "0",
                "win_rate": "0",
                "max_drawdown": str(self._max_drawdown_seen),
                "samples": 0,
            }
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
            self._emit("SYSTEM", "bot:metrics", self._compute_metrics())

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
            raise RuntimeError(
                "LIVE mode requires trading_enabled=true (explicit switch).",
            )
        client = self._ensure_client()
        symbol = c.symbol
        prev_equity = self._last_equity_usdt
        equity, capital = await self._compute_equity_usdt(client)
        drawdown, trading_blocked = self._register_equity(equity)
        self._record_return(prev_equity, equity)
        self._last_equity_usdt = equity
        self._emit(
            "SYSTEM",
            "bot:equity_snapshot",
            {
                "equity_usdt": str(equity),
                "capital_usdt": str(capital),
                "peak_equity_usdt": str(self._peak_equity_usdt or equity),
                "drawdown_pct": str(drawdown),
                "trading_blocked": trading_blocked,
            },
        )

        try:
            from runtime.core.market_cache import get_market_cache
            _cache = get_market_cache()
            open_orders = await _cache.get_or_fetch(
                f"open_orders:{symbol}",
                lambda: self._to_thread(lambda: client.get_open_orders(symbol=symbol)),
            )
        except Exception:
            open_orders = await self._to_thread(lambda: client.get_open_orders(symbol=symbol))
        if not isinstance(open_orders, list):
            open_orders = []
        self._emit(
            "INFO",
            "binance:get_open_orders",
            {"symbol": symbol, "response": open_orders},
        )
        sell_limit = [
            o
            for o in open_orders
            if str(o.get("side")) == "SELL" and str(o.get("type")) == "LIMIT"
        ]
        lowest_sell = None
        if sell_limit:
            lowest_sell = min(sell_limit, key=lambda o: _dec(o.get("price", "0"), "0"))

        try:
            from runtime.core.market_cache import get_market_cache
            _cache = get_market_cache()
            ticker = await _cache.get_or_fetch(
                f"symbol_ticker:{symbol}",
                lambda: self._to_thread(lambda: client.get_symbol_ticker(symbol=symbol)),
            )
        except Exception:
            ticker = await self._to_thread(lambda: client.get_symbol_ticker(symbol=symbol))
        self._emit(
            "INFO",
            "binance:get_symbol_ticker",
            {"symbol": symbol, "response": ticker},
        )
        market_price = _dec(ticker.get("price", "0"), "0")
        if lowest_sell is not None and c.stop_loss_pct > 0:
            anchor_sell_price = _dec(lowest_sell.get("price", "0"), "0")
            implied_buy = anchor_sell_price / (Decimal("1") + c.profit_factor) if c.profit_factor >= 0 else anchor_sell_price
            stop_price = implied_buy * (Decimal("1") - c.stop_loss_pct)
            if market_price <= stop_price:
                stop_payload: dict[str, Any] = {
                    "symbol": symbol,
                    "anchor_sell_price": str(anchor_sell_price),
                    "implied_buy_price": str(implied_buy),
                    "stop_price": str(stop_price),
                    "market_price": str(market_price),
                }
                if c.simulated:
                    stop_payload["execution"] = "SIMULATED"
                    self._emit("WARNING", "bot:stop_loss_triggered", stop_payload)
                else:
                    oid = lowest_sell.get("orderId")
                    qty = _dec(lowest_sell.get("origQty", "0"), "0")
                    if oid is not None:
                        cancelled = await self._to_thread(lambda o=oid: client.cancel_order(symbol=symbol, orderId=o))
                        self._emit("INFO", "binance:cancel_order_stop_loss", {"symbol": symbol, "response": cancelled})
                    if qty > 0:
                        sold = await self._to_thread(
                            lambda q=qty: client.create_order(
                                symbol=symbol,
                                side=client.SIDE_SELL,
                                type=client.ORDER_TYPE_MARKET,
                                quantity=str(_q(q, c.qty_decimals)),
                            )
                        )
                        self._emit("INFO", "binance:create_order_sell_market_stop_loss", {"symbol": symbol, "response": sold})
                    stop_payload["execution"] = "LIVE"
                    self._emit("WARNING", "bot:stop_loss_triggered", stop_payload)
                stop_report = {
                    "preset_id": c.preset_id,
                    "symbol": symbol,
                    "simulated": c.simulated,
                    "trading_enabled": c.trading_enabled,
                    "decision": "STOP_LOSS",
                    "market_price": str(market_price),
                    "stop_price": str(stop_price),
                    "loop_interval_sec": c.loop_interval_sec,
                }
                self._maybe_emit_metrics()
                return stop_report
        should_buy = False
        threshold = None
        if lowest_sell is not None:
            trigger = _dec(lowest_sell.get("price", "0"), "0")
            threshold = trigger * (Decimal("1") - (c.profit_factor + c.margin_drop_factor))
            should_buy = market_price <= threshold
        else:
            should_buy = True

        report: dict[str, Any] = {
            "preset_id": c.preset_id,
            "symbol": symbol,
            "simulated": c.simulated,
            "trading_enabled": c.trading_enabled,
            "open_orders_count": len(open_orders),
            "has_sell_limit_anchor": lowest_sell is not None,
            "market_price": str(market_price),
            "entry_threshold_price": str(threshold) if threshold is not None else None,
            "decision": "BUY_AND_SELL" if should_buy else "WAIT",
            "sell_anchor_price": str(_dec(lowest_sell.get("price", "0"), "0")) if lowest_sell else None,
            "loop_interval_sec": c.loop_interval_sec,
        }
        if trading_blocked:
            report["decision"] = "WAIT_DRAWDOWN_GUARD"
            report["trading_blocked"] = True
            report["drawdown_pct"] = str(drawdown)
            self._emit("WARNING", "bot:drawdown_guard_active", {"report": report})
            self._maybe_emit_metrics()
            return report
        if not should_buy:
            self._maybe_emit_metrics()
            return report

        est_buy = market_price if market_price > 0 else Decimal("1")
        est_qty = c.quote_order_qty / est_buy if est_buy > 0 else Decimal("0")
        est_sell = est_buy * (Decimal("1") + c.profit_factor)
        report["planned_quote_order_qty"] = str(c.quote_order_qty)
        report["planned_buy_price"] = str(est_buy)
        report["planned_sell_price"] = str(est_sell)
        report["planned_qty"] = str(_q(est_qty, c.qty_decimals))

        if c.simulated:
            report["execution"] = "SIMULATED"
            report["message"] = "Dry run only; no orders sent."
            self._emit("INFO", "bot:decision", {"report": report})
            self._maybe_emit_metrics()
            return report

        buy = await self._to_thread(
            lambda: client.create_order(
                symbol=symbol,
                side=client.SIDE_BUY,
                type=client.ORDER_TYPE_MARKET,
                quoteOrderQty=str(c.quote_order_qty),
            )
        )
        self._emit(
            "INFO",
            "binance:create_order_buy_market",
            {"symbol": symbol, "response": buy},
        )
        fills = buy.get("fills") or []
        if fills:
            buy_price = _dec(fills[0].get("price", "0"), "0")
        else:
            executed = _dec(buy.get("executedQty", "0"), "0")
            quote = _dec(buy.get("cummulativeQuoteQty", "0"), "0")
            buy_price = quote / executed if executed > 0 else est_buy
        qty = _dec(buy.get("executedQty", "0"), "0")
        sell_price = _q(buy_price * (Decimal("1") + c.profit_factor), c.price_decimals)
        sell_qty = _q(qty, c.qty_decimals)
        sell = await self._to_thread(
            lambda: client.create_order(
                symbol=symbol,
                side=client.SIDE_SELL,
                type=client.ORDER_TYPE_LIMIT,
                timeInForce=client.TIME_IN_FORCE_GTC,
                quantity=str(sell_qty),
                price=str(sell_price),
            )
        )
        self._emit(
            "INFO",
            "binance:create_order_sell_limit",
            {"symbol": symbol, "response": sell},
        )
        report["execution"] = "LIVE"
        report["buy_order_id"] = buy.get("orderId")
        report["sell_order_id"] = sell.get("orderId")
        report["filled_qty"] = str(qty)
        report["filled_buy_price"] = str(buy_price)
        report["placed_sell_price"] = str(sell_price)
        self._emit("INFO", "bot:decision", {"report": report})
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
            f"bot:time_sync offset_ms={offset_ms}",
            {"server_time": data, "offset_ms": offset_ms},
        )
        return {
            "local_time_ms": local_ms,
            "server_time_ms": server_ms,
            "offset_ms": offset_ms,
            "source": "bot",
        }

    async def _loop(self) -> None:
        while not self._stop.is_set():
            sleep_sec = float(self.config.loop_interval_sec)
            # ── Governor permission gate ─────────────────────────
            try:
                from runtime.core.weight_governor import get_weight_governor
                gov = get_weight_governor()
                bot_key = f"dorothy:{self.config.symbol}"
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
                    f"bot:{rep.get('decision')} symbol={rep.get('symbol')} simulated={rep.get('simulated')}",
                    {"report": rep},
                )
                # Report cycle to coordinator for phase tracking
                try:
                    from runtime.core.bot_coordinator import get_bot_coordinator
                    get_bot_coordinator().report_cycle(f"dorothy:{self.config.symbol}")
                except Exception:
                    pass
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._last_error = sanitize_log_message(str(e))
                self._error_streak += 1
                # Recreate client on failures so transient socket/session faults can self-heal.
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
                self._emit("ERROR", f"bot:error {self._last_error}", {"error": self._last_error})
                self._emit(
                    "WARNING",
                    f"bot:retry_in {sleep_sec:.0f}s (streak={self._error_streak})",
                    {"retry_sec": sleep_sec, "streak": self._error_streak},
                )
            # Add coordinator jitter to prevent cycle collisions
            try:
                from runtime.core.bot_coordinator import get_bot_coordinator
                jitter = get_bot_coordinator().compute_jitter(f"dorothy:{self.config.symbol}")
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
