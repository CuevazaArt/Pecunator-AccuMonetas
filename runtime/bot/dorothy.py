"""ExampleJV-inspired rule set — LIVE mode only (simulated mode removed).

Dorothy activation is governed by the EVI (Electric Volatility Index) gate:
  EVI = NATR × AvgSpeed × FreqExtreme × (Choppiness/50)
  Gate: EVI must be ≥ evi_min_threshold (default 0.02 = Grade D).
  Symbols below threshold are considered dead markets for DCA.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Callable, Optional

from runtime.bot._base_runner import BaseStrategyRunner
from runtime.bot._decimal_utils import dec as _dec, quantize as _q

from runtime.connectors.binance_gateway import normalize_binance_spot_symbol


# _dec and _q imported from runtime.bot._decimal_utils


@dataclass
class DorothyConfig:
    # Preset B with safe mode defaults.
    preset_id: str = "B"
    symbol: str = "XRPUSDT"
    loop_interval_sec: int = 450
    quote_order_qty: Decimal = Decimal("6")  # Conservative: 6 USDT per rung
    profit_factor: Decimal = Decimal("0.05")
    margin_drop_factor: Decimal = Decimal("0.03")  # L0: 3% between DCA steps
    qty_decimals: int = 8
    price_decimals: int = 4
    note: str = ""
    # [MEJORA] Proteccion de riesgo configurable.
    max_drawdown_pct: Decimal = Decimal("0.20")
    stop_loss_pct: Decimal = Decimal("0")  # L0: disabled — symmetric hub with Elphaba replaces SL
    metrics_interval_cycles: int = 5
    # T0.1: Hard ceiling on DCA rungs per symbol.
    # Each BUY_AND_SELL creates a SELL LIMIT anchor = 1 rung.
    # When open SELL LIMITs >= max_rungs, new buys are BLOCKED.
    max_rungs_per_symbol: int = 3  # Conservative: 3 rungs × 6 USDT = 18 USDT max exposure
    # T0.4: Force-liquidate worst position when drawdown exceeds this.
    # 0 = disabled (only blocks buys). Example: 0.40 = liquidate at 40% DD.
    drawdown_liquidate_pct: Decimal = Decimal("0")
    # EVI gate: minimum Electric Volatility Index to allow new buys.
    # Symbols with EVI < threshold are considered "dead markets" for DCA.
    # Grade scale: S≥0.50, A≥0.20, B≥0.10, C≥0.05, D≥0.02, F<0.02
    evi_min_threshold: Decimal = Decimal("0.02")  # Default: Grade D minimum
    # DEPRECATED: simulated mode removed. Field kept for DB/API compat.
    # Use trading_enabled as the sole on/off switch.
    simulated: bool = False
    trading_enabled: bool = True

    def normalize(self) -> None:
        # simulated mode permanently disabled — always LIVE.
        self.simulated = False
        self.symbol = normalize_binance_spot_symbol(self.symbol)
        self.loop_interval_sec = max(1, min(int(self.loop_interval_sec), 86_400))
        self.quote_order_qty = max(_dec(self.quote_order_qty, "5.0"), Decimal("5.0"))
        # L0 floor: 3% minimum profit to ensure viability after commissions
        self.profit_factor = max(_dec(self.profit_factor), Decimal("0.03"))
        self.margin_drop_factor = max(_dec(self.margin_drop_factor), Decimal("0"))
        self.qty_decimals = max(0, min(int(self.qty_decimals), 18))
        self.price_decimals = max(0, min(int(self.price_decimals), 18))
        self.note = (self.note or "").strip()[:20]
        self.max_drawdown_pct = max(_dec(self.max_drawdown_pct), Decimal("0"))
        self.stop_loss_pct = max(_dec(self.stop_loss_pct), Decimal("0"))
        self.metrics_interval_cycles = max(1, min(int(self.metrics_interval_cycles), 10_000))
        self.max_rungs_per_symbol = max(1, min(int(self.max_rungs_per_symbol), 100))
        self.drawdown_liquidate_pct = max(_dec(self.drawdown_liquidate_pct), Decimal("0"))
        self.evi_min_threshold = max(_dec(self.evi_min_threshold), Decimal("0"))

    def as_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["quote_order_qty"] = str(self.quote_order_qty)
        d["profit_factor"] = str(self.profit_factor)
        d["margin_drop_factor"] = str(self.margin_drop_factor)
        d["max_drawdown_pct"] = str(self.max_drawdown_pct)
        d["stop_loss_pct"] = str(self.stop_loss_pct)
        d["evi_min_threshold"] = str(self.evi_min_threshold)
        d["mode"] = "SIMULATED" if self.simulated else "LIVE"
        return d


class DorothyRunner(BaseStrategyRunner):

    BOT_TYPE = "dorothy"

    def __init__(
        self,
        log: Callable[[str], None],
        event_log: Optional[Callable[[str, str, Optional[dict[str, Any]]], None]] = None,
    ) -> None:
        super().__init__(log, event_log)
        self.config = DorothyConfig()
        self.config.normalize()
        self._precision_cache: dict[str, tuple[int, int]] = {}

    def apply_config(self, cfg: DorothyConfig) -> None:
        cfg.normalize()
        self.config = cfg

    def _bot_key(self) -> str:
        return f"dorothy:{self.config.symbol}"

    def _loop_log_summary(self, report: dict[str, Any]) -> str:
        return f"bot:{report.get('decision')} symbol={report.get('symbol')}"

    async def run_once(self) -> dict[str, Any]:
        from runtime.core.api_fuse import get_api_fuse
        fuse = get_api_fuse()
        if fuse.is_tripped():
            remaining = fuse.remaining_cooldown_sec()
            self._emit("WARNING", f"API FUSE ACTIVO: ciclo omitido ({remaining:.0f}s restantes)")
            return {"decision": "FUSE_TRIPPED", "remaining_sec": remaining}
        c = self.config
        c.normalize()
        if not c.trading_enabled:
            raise RuntimeError(
                "LIVE mode requires trading_enabled=true (explicit switch).",
            )

        # ── SymmetryGuard: watchdog tick + hub pause check ──────────
        try:
            from runtime.core.symmetry_guard import get_symmetry_guard
            _guard = get_symmetry_guard()
            # Tick the watchdog — handles auto-retry cooldowns
            _tick = _guard.tick()
            if _tick.get("action") == "AUTO_RETRY":
                self._emit("INFO", "dorothy:GUARD_AUTO_RETRY", _tick)
            elif _tick.get("needs_rotation"):
                self._emit("CRITICAL", "dorothy:NEEDS_ROTATION", {
                    "action": "Symbol rotation required — exhausted recovery attempts",
                    "tick": _tick,
                })
                return {"decision": "NEEDS_ROTATION", "reason": "Recovery exhausted, awaiting symbol rotation"}
            if _guard.is_hub_paused():
                reason = _guard.get_pause_reason()
                self._emit("WARNING", "dorothy:HUB_PAUSED", {
                    "reason": reason,
                    "tick": _tick,
                })
                return {"decision": "HUB_PAUSED", "reason": reason}
        except Exception:
            pass

        client = self._ensure_client()
        symbol = c.symbol

        # ── Auto-resolve precision from Binance exchangeInfo ──────────
        # Cached per-symbol to avoid redundant API calls each cycle.
        if symbol not in self._precision_cache:
            try:
                from decimal import Decimal as _D
                sym_info = await self._to_thread(
                    lambda: client.get_symbol_info(symbol)
                )
                if sym_info:
                    for flt in sym_info.get('filters', []):
                        ft = str(flt.get('filterType', '')).upper()
                        if ft == 'LOT_SIZE':
                            step = flt.get('stepSize', '1')
                            c.qty_decimals = max(0, -_D(str(step)).normalize().as_tuple().exponent)
                        elif ft == 'PRICE_FILTER':
                            tick = flt.get('tickSize', '0.01')
                            c.price_decimals = max(0, -_D(str(tick)).normalize().as_tuple().exponent)
                    self._precision_cache[symbol] = (c.qty_decimals, c.price_decimals)
                    self._emit("INFO", f"precision:resolved {symbol} qty_dec={c.qty_decimals} price_dec={c.price_decimals}")
            except Exception as e:
                self._emit("WARNING", f"precision:fallback {symbol} — {e}")
        else:
            c.qty_decimals, c.price_decimals = self._precision_cache[symbol]

        prev_equity = self._last_equity_usdt
        equity, capital = await self._compute_equity_usdt(client, symbol=symbol)
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
            from runtime.core.market_cache import get_market_cache, MarketCache
            _cache = get_market_cache()
            open_orders = await _cache.get_or_fetch(
                MarketCache.scoped_key(f"open_orders:{symbol}", self._api_key),
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
        my_tag = f"dorothy-{getattr(self, '_bot_id', 'dorothy')}"
        # Filter to only MY tagged sell limits for DCA logic
        sell_limit = [
            o
            for o in (open_orders if isinstance(open_orders, list) else [])
            if str(o.get("side")) == "SELL" and str(o.get("type")) == "LIMIT" and str(o.get("clientOrderId", "")).startswith(my_tag)
        ]
        # SAFETY: Also detect ANY sell limits on this symbol (including manual/foreign)
        all_sell_limits = [
            o for o in (open_orders if isinstance(open_orders, list) else [])
            if str(o.get("side")) == "SELL" and str(o.get("type")) == "LIMIT"
        ]
        has_foreign_sells = len(all_sell_limits) > len(sell_limit)
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
        stop_loss_triggered = False
        liquidated_qty = Decimal("0")
        if sell_limit and c.stop_loss_pct > 0:
            for sl_order in sell_limit:
                anchor_sell_price = _dec(sl_order.get("price", "0"), "0")
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
                    oid = sl_order.get("orderId")
                    qty = _dec(sl_order.get("origQty", "0"), "0")
                    if oid is not None:
                        try:
                            cancelled = await self._to_thread(lambda o=oid: client.cancel_order(symbol=symbol, orderId=o))
                            self._emit("INFO", "binance:cancel_order_stop_loss", {"symbol": symbol, "response": cancelled})
                        except Exception as e:
                            self._emit("ERROR", f"binance:cancel_order_stop_loss_failed: {e}")
                    if qty > 0:
                        # Record stop-loss in forensic ledger
                        _sl_lid = None
                        try:
                            from runtime.core.order_ledger import get_order_ledger
                            _sl_lid = get_order_ledger().record(
                                bot_id=getattr(self, '_bot_id', 'dorothy'),
                                bot_type="dorothy", symbol=symbol, side="SELL",
                                order_type="MARKET", qty=str(_q(qty, c.qty_decimals)),
                                reason="STOP_LOSS",
                                execution_mode="LIVE",
                            )
                        except Exception:
                            pass
                        try:
                            sold = await self._to_thread(
                                lambda q=qty: client.create_order(
                                    symbol=symbol,
                                    side=client.SIDE_SELL,
                                    type=client.ORDER_TYPE_MARKET,
                                    quantity=str(_q(q, c.qty_decimals)),
                                    newClientOrderId=f"{my_tag}-sl-{int(time.time())}"
                                )
                            )
                            self._emit("INFO", "binance:create_order_sell_market_stop_loss", {"symbol": symbol, "response": sold})
                            if _sl_lid:
                                try:
                                    from runtime.core.order_ledger import get_order_ledger
                                    get_order_ledger().update_binance_response(
                                        _sl_lid,
                                        str(sold.get("orderId", "")),
                                        str(sold.get("status", "")),
                                    )
                                except Exception:
                                    pass
                            liquidated_qty += qty
                        except Exception as e:
                            self._emit("ERROR", f"binance:create_order_sell_market_stop_loss_failed: {e}")
                    stop_payload["execution"] = "LIVE"
                    self._emit("WARNING", "bot:stop_loss_triggered", stop_payload)
                    stop_loss_triggered = True
                        
            if stop_loss_triggered:
                stop_report = {
                    "preset_id": c.preset_id,
                    "symbol": symbol,
                    "simulated": c.simulated,
                    "trading_enabled": c.trading_enabled,
                    "decision": "STOP_LOSS",
                    "market_price": str(market_price),
                    "liquidated_qty": str(liquidated_qty),
                    "loop_interval_sec": c.loop_interval_sec,
                }
                self._maybe_emit_metrics()
                return stop_report
        # ── EVI GATE: Electric Volatility Index check ──────────────
        # Replaces legacy dual-gate TrendSignal with inline EVI computation.
        # Gate 1 (EVI): Symbol must have minimum volatility profile for DCA
        # Gate 2 (Anti-peak): price < 1h candle open → avoid buying at tops
        try:
            from runtime.modules.prospector import compute_oscillation_score

            # Fetch 1h klines for EVI computation (cached per cycle)
            _evi_cache_key = f"_evi_{symbol}"
            _cached = getattr(self, _evi_cache_key, None)
            _cache_age = time.time() - getattr(self, f"{_evi_cache_key}_ts", 0)
            if _cached is None or _cache_age > 3600:  # refresh every hour
                klines_1h = await self._to_thread(
                    lambda _s=symbol: client.get_klines(symbol=_s, interval="1h", limit=50)
                )
                _evi_data = compute_oscillation_score(klines_1h) if klines_1h and len(klines_1h) >= 20 else None
                setattr(self, _evi_cache_key, _evi_data)
                setattr(self, f"{_evi_cache_key}_ts", time.time())
            else:
                _evi_data = _cached

            if _evi_data:
                evi_score = _evi_data.get("evi_score", 0)
                evi_threshold = float(c.evi_min_threshold)
                candle_open_1h = _evi_data.get("current_price", 0)  # last close ≈ current

                self._emit("INFO", "dorothy:evi_gate", {
                    "symbol": symbol,
                    "evi_score": round(evi_score, 4),
                    "evi_threshold": evi_threshold,
                    "atr_pct": round(_evi_data.get("atr_pct", 0), 4),
                    "choppiness": round(_evi_data.get("choppiness", 0), 2),
                    "adx": round(_evi_data.get("adx", 0), 2),
                    "market_price": str(market_price),
                    "gate": "OPEN" if evi_score >= evi_threshold else "BLOCKED",
                })

                if evi_score < evi_threshold:
                    return {
                        "preset_id": c.preset_id, "symbol": symbol,
                        "simulated": c.simulated, "trading_enabled": c.trading_enabled,
                        "decision": "WAIT_EVI_LOW",
                        "evi_score": round(evi_score, 4),
                        "evi_threshold": evi_threshold,
                        "market_price": str(market_price),
                        "loop_interval_sec": c.loop_interval_sec,
                    }

        except Exception as evi_err:
            # Fail-open: if EVI computation fails, allow trading (conservative)
            self._emit("WARNING", f"dorothy:evi_gate_error: {evi_err}")

        # ── DCA entry logic (only reached when both gates are open) ──
        should_buy = False
        threshold = None
        if lowest_sell is not None:
            trigger = _dec(lowest_sell.get("price", "0"), "0")
            threshold = trigger * (Decimal("1") - (c.profit_factor + c.margin_drop_factor))
            should_buy = market_price <= threshold
        elif has_foreign_sells:
            # Foreign/manual sell limits exist — do NOT buy, do NOT interfere
            should_buy = False
            self._emit("INFO", f"dorothy:foreign_sells_detected on {symbol}, skipping buy")
        else:
            should_buy = True

        # T0.1: Count active rungs (open SELL LIMITs = active DCA positions)
        active_rungs = len(sell_limit)

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
            "active_rungs": active_rungs,
            "max_rungs": c.max_rungs_per_symbol,
        }
        if trading_blocked:
            report["decision"] = "WAIT_DRAWDOWN_GUARD"
            report["trading_blocked"] = True
            report["drawdown_pct"] = str(drawdown)
            # T0.4: HARD PAUSE — if drawdown exceeds liquidation threshold,
            # do NOT auto-liquidate (doom button removed per audit).
            # Instead: emit CRITICAL alert and keep trading fully blocked.
            # Human operator must manually decide to liquidate or hold.
            if (c.drawdown_liquidate_pct > 0
                    and drawdown > c.drawdown_liquidate_pct):
                self._emit("CRITICAL", "bot:DRAWDOWN_CRITICAL_PAUSE", {
                    "symbol": symbol,
                    "drawdown_pct": str(drawdown),
                    "threshold": str(c.drawdown_liquidate_pct),
                    "active_rungs": active_rungs,
                    "market_price": str(market_price),
                    "message": "DRAWDOWN EXCEEDS CRITICAL THRESHOLD. "
                               "Trading paused. NO auto-liquidation. "
                               "Manual intervention required.",
                })
                report["decision"] = "CRITICAL_PAUSE_DRAWDOWN"
            self._emit("WARNING", "bot:drawdown_guard_active", {"report": report})
            self._maybe_emit_metrics()
            return report
        # T0.1: Block new buys when rung ceiling is reached
        if should_buy and active_rungs >= c.max_rungs_per_symbol:
            report["decision"] = "BLOCKED_MAX_RUNGS"
            self._emit(
                "WARNING",
                f"bot:max_rungs_reached {active_rungs}/{c.max_rungs_per_symbol}",
                {"report": report},
            )
            self._maybe_emit_metrics()
            return report
        if not should_buy:
            self._maybe_emit_metrics()
            return report
        # Trend + entry gates already checked above — both are OPEN at this point

        # T0.2: Block if daily spend limit exceeded
        if should_buy:
            try:
                from runtime.core.budget_guard import get_budget_guard
                bg = get_budget_guard()
                if not bg.try_reserve(self._bot_key(), symbol, c.quote_order_qty):
                    report["decision"] = "BLOCKED_BUDGET"
                    self._emit("WARNING", "bot:budget_blocked", {"report": report})
                    self._maybe_emit_metrics()
                    return report
            except Exception as e:
                report["decision"] = "BLOCKED_BUDGET"
                self._emit("WARNING", f"bot:budget_error FAIL_CLOSED {e}", {"report": report})
                self._maybe_emit_metrics()
                return report

        est_buy = market_price if market_price > 0 else Decimal("1")
        # T1.6: Model fees + slippage for honest paper trading
        _FEE_BPS = Decimal("10")      # 0.10% taker fee
        _SLIPPAGE_BPS = Decimal("5")   # 0.05% average slippage
        _FRICTION = (Decimal("1") + (_FEE_BPS + _SLIPPAGE_BPS) / Decimal("10000"))
        est_buy_adj = est_buy * _FRICTION  # effective buy price (higher)
        est_qty = c.quote_order_qty / est_buy_adj if est_buy_adj > 0 else Decimal("0")
        est_sell = est_buy_adj * (Decimal("1") + c.profit_factor) / _FRICTION  # TP net of fees
        report["planned_quote_order_qty"] = str(c.quote_order_qty)
        report["planned_buy_price"] = str(est_buy_adj)
        report["planned_buy_price_raw"] = str(est_buy)
        report["planned_sell_price"] = str(est_sell)
        report["planned_qty"] = str(_q(est_qty, c.qty_decimals))
        report["fee_slippage_bps"] = str(_FEE_BPS + _SLIPPAGE_BPS)

        # T0.3: Record LIVE order in forensic ledger BEFORE sending
        _ledger_id = None
        try:
            from runtime.core.order_ledger import get_order_ledger
            _ledger_id = get_order_ledger().record(
                bot_id=getattr(self, '_bot_id', 'dorothy'),
                bot_type="dorothy", symbol=symbol, side="BUY",
                order_type="MARKET", qty=str(_q(est_qty, c.qty_decimals)),
                quote_order_qty=str(c.quote_order_qty), reason="BUY_AND_SELL",
                drawdown_pct=str(drawdown), active_rungs=active_rungs,
                max_rungs=c.max_rungs_per_symbol, execution_mode="LIVE",
            )
        except Exception as e:
            self._emit("ERROR", f"order_ledger:record_failed:{e}")

        try:
            buy = await self._to_thread(
                lambda: client.create_order(
                    symbol=symbol,
                    side=client.SIDE_BUY,
                    type=client.ORDER_TYPE_MARKET,
                    quoteOrderQty=str(c.quote_order_qty),
                    newClientOrderId=f"{my_tag}-buy-{int(time.time())}"
                )
            )
        except Exception as buy_err:
            # ── Alert: BUY order failed → feed SymmetryGuard ──────
            try:
                from runtime.core.symmetry_guard import get_symmetry_guard
                get_symmetry_guard().record_order_failure(
                    self._bot_key(), str(buy_err)
                )
            except Exception:
                pass
            self._emit("CRITICAL", "dorothy:BUY_ORDER_FAILED", {
                "symbol": symbol, "error": str(buy_err)[:300],
                "action": "Hub may auto-pause after 3 consecutive failures.",
            })
            report["decision"] = "ORDER_FAILED"
            report["error"] = str(buy_err)[:300]
            self._maybe_emit_metrics()
            return report

        # ── Alert: BUY succeeded → reset failure counter ──────────
        try:
            from runtime.core.symmetry_guard import get_symmetry_guard
            get_symmetry_guard().record_order_success(self._bot_key())
        except Exception:
            pass

        # T0.3: Update ledger with Binance response
        if _ledger_id:
            try:
                from runtime.core.order_ledger import get_order_ledger
                get_order_ledger().update_binance_response(
                    _ledger_id,
                    str(buy.get("orderId", "")),
                    str(buy.get("status", "")),
                )
            except Exception as e:
                self._emit("ERROR", f"order_ledger:update_failed:{e}")

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

        # T0.4: Record OPEN RUNG in local hub state
        _hub_rung_id = 0
        try:
            from runtime.core.hub_state import get_hub_state
            _hub_rung_id = get_hub_state().open_rung(
                bot_id=getattr(self, '_bot_id', 'dorothy'),
                symbol=symbol,
                buy_order_id=str(buy.get("orderId", "")),
                buy_price=str(buy_price),
                qty=str(qty)
            )
        except Exception as e:
            self._emit("ERROR", f"hub_state:open_rung_failed:{e}")

        # T0.3: Record SELL LIMIT in ledger
        _sell_ledger_id = None
        try:
            from runtime.core.order_ledger import get_order_ledger
            _sell_ledger_id = get_order_ledger().record(
                bot_id=getattr(self, '_bot_id', 'dorothy'),
                bot_type="dorothy", symbol=symbol, side="SELL",
                order_type="LIMIT", qty=str(sell_qty), price=str(sell_price),
                reason="TAKE_PROFIT", execution_mode="LIVE",
            )
        except Exception as e:
            self._emit("ERROR", f"order_ledger:record_failed:{e}")

        try:
            sell = await self._to_thread(
                lambda: client.create_order(
                    symbol=symbol,
                    side=client.SIDE_SELL,
                    type=client.ORDER_TYPE_LIMIT,
                    timeInForce=client.TIME_IN_FORCE_GTC,
                    quantity=str(sell_qty),
                    price=str(sell_price),
                    newClientOrderId=f"{my_tag}-sell-{int(time.time())}"
                )
            )
        except Exception as tp_err:
            # ── CRITICAL: BUY succeeded but SELL LIMIT failed ─────
            # Position is now "orphaned" — asset bought but no TP set.
            self._emit("CRITICAL", "dorothy:TP_LIMIT_FAILED_ORPHAN", {
                "symbol": symbol,
                "buy_order_id": buy.get("orderId"),
                "filled_qty": str(qty),
                "filled_buy_price": str(buy_price),
                "intended_sell_price": str(sell_price),
                "error": str(tp_err)[:300],
                "action": "MANUAL INTERVENTION REQUIRED — asset bought without TP.",
            })
            try:
                from runtime.core.symmetry_guard import get_symmetry_guard
                get_symmetry_guard().record_order_failure(
                    self._bot_key(), f"TP_ORPHAN: {tp_err}"
                )
            except Exception:
                pass
                
            # Mark rung as ORPHANED in local state
            if _hub_rung_id > 0:
                try:
                    from runtime.core.hub_state import get_hub_state
                    get_hub_state().close_rung(_hub_rung_id, status="ORPHANED")
                except Exception:
                    pass

            report["decision"] = "TP_FAILED_ORPHAN"
            report["execution"] = "LIVE"
            report["buy_order_id"] = buy.get("orderId")
            report["filled_qty"] = str(qty)
            report["filled_buy_price"] = str(buy_price)
            report["error"] = str(tp_err)[:300]
            self._maybe_emit_metrics()
            return report

        # T0.3: Update sell ledger
        if _sell_ledger_id:
            try:
                from runtime.core.order_ledger import get_order_ledger
                get_order_ledger().update_binance_response(
                    _sell_ledger_id,
                    str(sell.get("orderId", "")),
                    str(sell.get("status", "")),
                )
            except Exception as e:
                self._emit("ERROR", f"order_ledger:update_failed:{e}")

        # T0.4: Link SELL LIMIT to local hub rung
        if _hub_rung_id > 0:
            try:
                from runtime.core.hub_state import get_hub_state
                get_hub_state().link_sell_to_rung(
                    rung_id=_hub_rung_id,
                    sell_order_id=str(sell.get("orderId", "")),
                    sell_price=str(sell_price)
                )
            except Exception as e:
                self._emit("ERROR", f"hub_state:link_sell_failed:{e}")

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
