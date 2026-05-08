"""Thusnelda — volatile basket strategy runner — LIVE mode only.

Operating Model (L0 Basket):
  - Maintains a fixed basket of 5 mid-cap volatile altcoins from sectors
    NOT overlapping with Dorothy (trend-following) or Masha (DCA range).
  - Buys the entire basket on activation (market dip opportunity).
  - Harvests when total basket equity rises >= target (6% default).
  - Symbols: PEPE, SUI, NEAR, INJ, FET (Meme/L1/AI/DeFi sectors).
  - This bot does NOT operate BTC, ETH, SOL, or BNB (those belong
    to Dorothy and Masha respectively).
"""

from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Any, Callable, Optional

from binance.client import Client

from runtime.bot._base_runner import BaseStrategyRunner
from runtime.bot._decimal_utils import dec as _dec, quantize as _q

from runtime.connectors.binance_gateway import normalize_binance_spot_symbol
from runtime.core.security_util import sanitize_log_message


# _dec and _q imported from runtime.bot._decimal_utils


# L0 Profit Floor for Thusnelda (basket requires higher margin due to
# multi-symbol exposure and the intent to capture sector-wide moves).
THUSNELDA_PROFIT_FLOOR: Decimal = Decimal("0.06")  # 6% per cycle


@dataclass
class ThusneldaConfig:
    preset_id: str = "T1"
    # Volatile basket: non-overlapping with Dorothy/Masha blue-chips.
    # Sectors: Meme (PEPE), L1/Move (SUI), AI/Infra (NEAR),
    #          DeFi/Cosmos (INJ), AI/Agents (FET)
    symbols_csv: str = "PEPEUSDT,SUIUSDT"  # Reduced basket for 100 USDT test
    loop_interval_sec: int = 600
    between_symbol_sec: int = 3
    quote_order_qty_modulo: Decimal = Decimal("6")   # L0 micro-operation
    # factor_multiplication: buy when current < avg * factor.
    # 0.94 = buy when price is 6% below average (matches profit target).
    factor_multiplication: Decimal = Decimal("0.94")
    # meta_equity_usdt: liquidate (harvest) when equity >= this target.
    # Computed at activation as: initial_equity * (1 + profit_target).
    # Default 0 = use profit_target_pct instead.
    meta_equity_usdt: Decimal = Decimal("0")
    # L0 basket profit target: 6% minimum per cycle.
    profit_target_pct: Decimal = Decimal("0.06")
    reference_ts_iso: str = ""
    qty_decimals: int = 8
    note: str = ""
    # Wider risk tolerance for volatile mid-cap basket.
    max_drawdown_pct: Decimal = Decimal("0.30")
    stop_loss_pct: Decimal = Decimal("0.30")  # Wide for volatile mid-caps
    metrics_interval_cycles: int = 3
    # T0.1: Hard ceiling on DCA rungs PER SYMBOL in the basket.
    # buys_after_ref count >= max_rungs → BLOCKED.
    # Critical for volatile mid-caps where averaging-down is most dangerous.
    max_rungs_per_symbol: int = 2  # Conservative: 2 rungs × 6 USDT × 2 symbols = 24 USDT max
    # DEPRECATED: simulated mode removed. Field kept for DB/API compat.
    # Use trading_enabled as the sole on/off switch.
    simulated: bool = False
    trading_enabled: bool = True

    # Symbols already operated by Dorothy/Masha — Thusnelda must NOT touch.
    _RESERVED_SYMBOLS: frozenset[str] = frozenset({
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    })

    def normalize(self) -> None:
        # simulated mode permanently disabled — always LIVE.
        self.simulated = False
        symbols = []
        for raw in (self.symbols_csv or "").split(","):
            s = raw.strip().upper()
            if not s:
                continue
            try:
                sym = normalize_binance_spot_symbol(s)
                # Warn but don't block if symbol overlaps with Dorothy/Masha
                if sym in self._RESERVED_SYMBOLS:
                    import logging
                    logging.getLogger("pecunator.thusnelda").warning(
                        "Symbol %s is reserved for Dorothy/Masha — "
                        "removing from Thusnelda basket", sym,
                    )
                    continue
                symbols.append(sym)
            except Exception:
                continue
        if not symbols:
            symbols = ["PEPEUSDT", "SUIUSDT", "NEARUSDT", "INJUSDT", "FETUSDT"]
        self.symbols_csv = ",".join(symbols)
        self.loop_interval_sec = max(1, min(int(self.loop_interval_sec), 86_400))
        self.between_symbol_sec = max(0, min(int(self.between_symbol_sec), 600))
        self.quote_order_qty_modulo = max(_dec(self.quote_order_qty_modulo, "0.0001"), Decimal("0.0001"))
        self.factor_multiplication = max(_dec(self.factor_multiplication, "0.0001"), Decimal("0.0001"))
        self.meta_equity_usdt = _dec(self.meta_equity_usdt, "0")
        # L0 floor: 6% minimum profit target for volatile basket
        self.profit_target_pct = max(
            _dec(self.profit_target_pct, "0.06"), THUSNELDA_PROFIT_FLOOR,
        )
        self.qty_decimals = max(0, min(int(self.qty_decimals), 18))
        self.note = (self.note or "").strip()[:20]
        self.max_drawdown_pct = max(_dec(self.max_drawdown_pct), Decimal("0"))
        self.stop_loss_pct = max(_dec(self.stop_loss_pct), Decimal("0"))
        self.metrics_interval_cycles = max(1, min(int(self.metrics_interval_cycles), 10_000))
        self.max_rungs_per_symbol = max(1, min(int(self.max_rungs_per_symbol), 100))
        if not self.reference_ts_iso:
            self.reference_ts_iso = dt.datetime.now().isoformat()

    def symbols(self) -> list[str]:
        return [s for s in self.symbols_csv.split(",") if s]

    def reference_dt(self) -> dt.datetime:
        try:
            parsed = dt.datetime.fromisoformat(self.reference_ts_iso)
            return parsed
        except Exception:
            return dt.datetime.now()

    def as_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["quote_order_qty_modulo"] = str(self.quote_order_qty_modulo)
        d["factor_multiplication"] = str(self.factor_multiplication)
        d["meta_equity_usdt"] = str(self.meta_equity_usdt)
        d["profit_target_pct"] = str(self.profit_target_pct)
        d["max_drawdown_pct"] = str(self.max_drawdown_pct)
        d["stop_loss_pct"] = str(self.stop_loss_pct)
        d["symbols"] = self.symbols()
        d["mode"] = "LIVE"
        # Remove internal frozenset from serialization
        d.pop("_RESERVED_SYMBOLS", None)
        return d


class ThusneldaRunner(BaseStrategyRunner):

    BOT_TYPE = "thusnelda"

    def __init__(
        self,
        log: Callable[[str], None],
        event_log: Optional[Callable[[str, str, Optional[dict[str, Any]]], None]] = None,
    ) -> None:
        super().__init__(log, event_log)
        self.config = ThusneldaConfig()
        self.config.normalize()

    def apply_config(self, cfg: ThusneldaConfig) -> None:
        cfg.normalize()
        self.config = cfg

    def _bot_key(self) -> str:
        return f"thusnelda:{self.config.symbols_csv}"

    def _loop_log_summary(self, report: dict[str, Any]) -> str:
        return f"thusnelda:cycle symbols={len(report.get('symbols', []))}"

    async def _qty_for_market_sell(self, client: Client, symbol: str, qty: Decimal) -> Decimal | None:
        try:
            info = await self._to_thread(lambda: client.get_symbol_info(symbol))
        except Exception:
            info = None
        if not isinstance(info, dict):
            return _q(qty, self.config.qty_decimals)
        filters = info.get("filters")
        if not isinstance(filters, list):
            return _q(qty, self.config.qty_decimals)
        min_qty = Decimal("0")
        step = Decimal("0")
        for f in filters:
            if not isinstance(f, dict):
                continue
            if str(f.get("filterType", "")).upper() == "LOT_SIZE":
                min_qty = _dec(f.get("minQty", "0"), "0")
                step = _dec(f.get("stepSize", "0"), "0")
                break
        if step <= 0:
            return _q(qty, self.config.qty_decimals)
        q = (qty / step).to_integral_value(rounding=ROUND_DOWN) * step
        if q < min_qty or q <= 0:
            return None
        return q

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
            raise RuntimeError("LIVE mode requires trading_enabled=true (explicit switch).")
        client = self._ensure_client()
        await self._sync_time_for_signed(client)
        ref_dt = c.reference_dt()
        symbols = c.symbols()
        decisions: list[dict[str, Any]] = []

        for idx, symbol in enumerate(symbols):
            item: dict[str, Any] = {"symbol": symbol}
            try:
                trades = await self._signed_call(
                    client,
                    lambda s=symbol: client.get_my_trades(symbol=s, fromId=0),
                )
                if not isinstance(trades, list):
                    trades = []
                self._emit("INFO", "binance:get_my_trades", {"symbol": symbol, "response": trades})
                buys_after_ref = []
                for tr in trades:
                    if not isinstance(tr, dict):
                        continue
                    if tr.get("isBuyer") is not True:
                        continue
                    t_ms = int(tr.get("time", 0) or 0)
                    tr_dt = dt.datetime.fromtimestamp(t_ms / 1000)
                    if tr_dt > ref_dt:
                        buys_after_ref.append(tr)

                if not buys_after_ref:
                    # BUY_INITIAL_REFERENCE is qty=0 — no real spend.
                    # Budget guard only gates actual BUY_MARKET/DCA rungs.
                    item["decision"] = "BUY_INITIAL_REFERENCE"
                    _ledger_id = None
                    try:
                        from runtime.core.order_ledger import get_order_ledger
                        _ledger_id = get_order_ledger().record(
                            bot_id=getattr(self, '_bot_id', 'thusnelda'),
                            bot_type="thusnelda", symbol=symbol, side="BUY", order_type="MARKET",
                            qty="0", quote_order_qty=str(c.quote_order_qty_modulo),
                            reason="BUY_INITIAL_REFERENCE", drawdown_pct="0",
                            active_rungs=0, max_rungs=c.max_rungs_per_symbol, execution_mode="LIVE",
                        )
                    except Exception as e:
                        self._emit("ERROR", f"order_ledger:record_failed:{e}")
                    
                    order = await self._signed_call(
                        client,
                        lambda s=symbol: client.create_order(
                            symbol=s,
                            side=client.SIDE_BUY,
                            type=client.ORDER_TYPE_MARKET,
                            quoteOrderQty=str(c.quote_order_qty_modulo),
                        ),
                    )
                    if _ledger_id:
                        try:
                            from runtime.core.order_ledger import get_order_ledger
                            get_order_ledger().update_binance_response(_ledger_id, str((order or {}).get("orderId", "")), str((order or {}).get("status", "")))
                        except Exception: pass
                    self._emit("INFO", "binance:create_order_buy_initial", {"symbol": symbol, "response": order})
                    item["execution"] = "LIVE"
                    item["order_id"] = order.get("orderId") if isinstance(order, dict) else None
                    decisions.append(item)
                else:
                    prices = [_dec(tr.get("price", "0"), "0") for tr in buys_after_ref[-30:]]
                    if not prices:
                        item["decision"] = "WAIT_NO_PRICE_DATA"
                        decisions.append(item)
                    else:
                        avg_price = sum(prices, Decimal("0")) / Decimal(len(prices))
                        try:
                            from runtime.core.market_cache import get_market_cache
                            _cache = get_market_cache()
                            ticker = await _cache.get_or_fetch(
                                f"symbol_ticker:{symbol}",
                                lambda s=symbol: self._to_thread(
                                    lambda: client.get_symbol_ticker(symbol=s)
                                ),
                            )
                        except Exception:
                            ticker = await self._to_thread(
                                lambda s=symbol: client.get_symbol_ticker(symbol=s)
                            )
                        current = _dec((ticker or {}).get("price", "0"), "0")
                        limit_price = avg_price * c.factor_multiplication
                        item["avg_buy_price"] = str(avg_price)
                        item["current_price"] = str(current)
                        item["limit_price"] = str(limit_price)
                        item["active_rungs"] = len(buys_after_ref)
                        item["max_rungs"] = c.max_rungs_per_symbol
                        # T0.1: Block if rung ceiling reached
                        if len(buys_after_ref) >= c.max_rungs_per_symbol:
                            item["decision"] = "BLOCKED_MAX_RUNGS"
                            self._emit(
                                "WARNING",
                                f"thusnelda:max_rungs_reached {symbol} {len(buys_after_ref)}/{c.max_rungs_per_symbol}",
                                {"item": item},
                            )
                            decisions.append(item)
                            continue
                        # Regime filter removed in v2.0 — will be rebuilt from scratch
                        if current < limit_price:
                            try:
                                from runtime.core.budget_guard import get_budget_guard
                                bg = get_budget_guard()
                                if not bg.try_reserve(self._bot_key(), symbol, c.quote_order_qty_modulo):
                                    item["decision"] = "BLOCKED_BUDGET"
                                    decisions.append(item)
                                    continue
                            except Exception as e:
                                item["decision"] = "BLOCKED_BUDGET"
                                item["error"] = f"FAIL_CLOSED {e}"
                                decisions.append(item)
                                continue

                            item["decision"] = "BUY_MARKET"
                            _ledger_id = None
                            try:
                                from runtime.core.order_ledger import get_order_ledger
                                _ledger_id = get_order_ledger().record(
                                    bot_id=getattr(self, '_bot_id', 'thusnelda'),
                                    bot_type="thusnelda", symbol=symbol, side="BUY", order_type="MARKET",
                                    qty="0", quote_order_qty=str(c.quote_order_qty_modulo),
                                    reason="BUY_DCA_RUNG", drawdown_pct="0",
                                    active_rungs=len(buys_after_ref), max_rungs=c.max_rungs_per_symbol, execution_mode="LIVE",
                                )
                            except Exception as e:
                                self._emit("ERROR", f"order_ledger:record_failed:{e}")

                            order = await self._signed_call(
                                client,
                                lambda s=symbol: client.create_order(
                                    symbol=s,
                                    side=client.SIDE_BUY,
                                    type=client.ORDER_TYPE_MARKET,
                                    quoteOrderQty=str(c.quote_order_qty_modulo),
                                ),
                            )
                            if _ledger_id:
                                try:
                                    from runtime.core.order_ledger import get_order_ledger
                                    get_order_ledger().update_binance_response(_ledger_id, str((order or {}).get("orderId", "")), str((order or {}).get("status", "")))
                                except Exception: pass
                            self._emit("INFO", "binance:create_order_buy_market", {"symbol": symbol, "response": order})
                            item["execution"] = "LIVE"
                            item["order_id"] = order.get("orderId") if isinstance(order, dict) else None
                        else:
                            item["decision"] = "WAIT_PRICE_NOT_BELOW_LIMIT"
                        decisions.append(item)
            except Exception as e:
                item["decision"] = "ERROR"
                item["error"] = sanitize_log_message(str(e))
                decisions.append(item)
                self._emit("ERROR", f"thusnelda:symbol_error {symbol} {item['error']}", {"symbol": symbol, "error": item["error"]})

            if idx < len(symbols) - 1 and c.between_symbol_sec > 0:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=float(c.between_symbol_sec))
                    if self._stop.is_set():
                        break
                except asyncio.TimeoutError:
                    pass

        try:
            from runtime.core.market_cache import get_market_cache, MarketCache
            _cache = get_market_cache()
            account = await _cache.get_or_fetch(
                MarketCache.scoped_key("account", self._api_key),
                lambda: self._signed_call(client, client.get_account),
            )
            tickers = await _cache.get_or_fetch(
                "tickers",
                lambda: self._to_thread(client.get_all_tickers),
            )
        except Exception:
            account = await self._signed_call(client, client.get_account)
            tickers = await self._to_thread(client.get_all_tickers)
        self._emit("INFO", "binance:get_account", {"response": account})
        ticker_map = {}
        if isinstance(tickers, list):
            for row in tickers:
                if isinstance(row, dict):
                    ticker_map[str(row.get("symbol", "")).upper()] = _dec(row.get("price", "0"), "0")
        usdt_free = Decimal("0")
        non_usdt_equity = Decimal("0")
        balances = account.get("balances", []) if isinstance(account, dict) else []
        if isinstance(balances, list):
            for b in balances:
                if not isinstance(b, dict):
                    continue
                asset = str(b.get("asset", "")).upper()
                total = _dec(b.get("free", "0"), "0") + _dec(b.get("locked", "0"), "0")
                if total <= 0:
                    continue
                if asset == "USDT":
                    usdt_free = _dec(b.get("free", "0"), "0")
                    continue
                sym = f"{asset}USDT"
                px = ticker_map.get(sym)
                if px and px > 0:
                    non_usdt_equity += total * px
        total_equity = non_usdt_equity + usdt_free
        drawdown, trading_blocked = self._register_equity(total_equity)
        prev_eq = self._last_equity_usdt
        self._last_equity_usdt = total_equity
        self._record_return(prev_eq, total_equity)
        self._emit(
            "SYSTEM",
            "thusnelda:equity_snapshot",
            {
                "equity_usdt": str(total_equity),
                "capital_usdt": str(usdt_free),
                "peak_equity_usdt": str(self._peak_equity_usdt or total_equity),
                "drawdown_pct": str(drawdown),
                "trading_blocked": trading_blocked,
            },
        )
        # ── Harvest Decision ──────────────────────────────────────
        if c.meta_equity_usdt > 0:
            harvest_target = c.meta_equity_usdt
        else:
            if self._peak_equity_usdt and self._peak_equity_usdt > 0:
                harvest_target = self._peak_equity_usdt * (Decimal("1") + c.profit_target_pct)
            else:
                harvest_target = Decimal("0")

        should_liquidate = harvest_target > 0 and total_equity >= harvest_target
        liquidations: list[dict[str, Any]] = []
        if should_liquidate:
            if isinstance(balances, list):
                for b in balances:
                    if not isinstance(b, dict):
                        continue
                    asset = str(b.get("asset", "")).upper()
                    free = _dec(b.get("free", "0"), "0")
                    if free <= 0 or asset == "USDT":
                        continue
                    sym = f"{asset}USDT"
                    q = await self._qty_for_market_sell(client, sym, free)
                    rec: dict[str, Any] = {"asset": asset, "symbol": sym, "free": str(free)}
                    if q is None or q <= 0:
                        rec["decision"] = "SKIP_INVALID_QTY"
                    else:
                        _ledger_id = None
                        try:
                            from runtime.core.order_ledger import get_order_ledger
                            _ledger_id = get_order_ledger().record(
                                bot_id=getattr(self, '_bot_id', 'thusnelda'),
                                bot_type="thusnelda", symbol=sym, side="SELL", order_type="MARKET",
                                qty=str(q), quote_order_qty="0",
                                reason="HARVEST_BASKET", drawdown_pct=str(drawdown),
                                active_rungs=0, max_rungs=c.max_rungs_per_symbol, execution_mode="LIVE",
                            )
                        except Exception: pass
                        try:
                            order = await self._signed_call(
                                client,
                                lambda s=sym, qty=q: client.order_market_sell(symbol=s, quantity=str(qty)),
                            )
                            if _ledger_id:
                                try:
                                    from runtime.core.order_ledger import get_order_ledger
                                    get_order_ledger().update_binance_response(_ledger_id, str((order or {}).get("orderId", "")), str((order or {}).get("status", "")))
                                except Exception: pass
                            self._emit("INFO", "binance:order_market_sell", {"symbol": sym, "response": order})
                            rec["decision"] = "SELL_MARKET"
                            rec["execution"] = "LIVE"
                            rec["quantity"] = str(q)
                            rec["order_id"] = order.get("orderId") if isinstance(order, dict) else None
                        except Exception as e:
                            rec["decision"] = "ERROR_SELL"
                            rec["error"] = sanitize_log_message(str(e))
                    liquidations.append(rec)

        report = {
            "preset_id": c.preset_id,
            "symbols": symbols,
            "simulated": c.simulated,
            "trading_enabled": c.trading_enabled,
            "reference_ts_iso": c.reference_ts_iso,
            "quote_order_qty_modulo": str(c.quote_order_qty_modulo),
            "factor_multiplication": str(c.factor_multiplication),
            "meta_equity_usdt": str(c.meta_equity_usdt),
            "usdt_free": str(usdt_free),
            "non_usdt_equity": str(non_usdt_equity),
            "total_equity": str(total_equity),
            "meta_reached": bool(total_equity >= c.meta_equity_usdt) if c.meta_equity_usdt > 0 else False,
            "liquidation_triggered": should_liquidate,
            "trading_blocked": trading_blocked,
            "drawdown_pct": str(drawdown),
            "decisions": decisions,
            "liquidations": liquidations,
        }
        if trading_blocked:
            report["decision"] = "WAIT_DRAWDOWN_GUARD"
        if c.stop_loss_pct > 0:
            for item in decisions:
                avg_raw = item.get("avg_buy_price")
                cur_raw = item.get("current_price")
                sym = str(item.get("symbol", ""))
                if avg_raw is None or cur_raw is None or not sym:
                    continue
                avg = _dec(avg_raw, "0")
                cur = _dec(cur_raw, "0")
                stop_price = avg * (Decimal("1") - c.stop_loss_pct)
                if avg > 0 and cur <= stop_price:
                    liq_rec: dict[str, Any] = {
                        "symbol": sym,
                        "decision": "STOP_LOSS",
                        "avg_buy_price": str(avg),
                        "market_price": str(cur),
                        "stop_price": str(stop_price),
                    }
                    base_asset = sym.replace("USDT", "")
                    bal = await self._signed_call(client, lambda a=base_asset: client.get_asset_balance(asset=a))
                    free = _dec((bal or {}).get("free", "0"), "0")
                    q = await self._qty_for_market_sell(client, sym, free)
                    if q and q > 0:
                        _ledger_id = None
                        try:
                            from runtime.core.order_ledger import get_order_ledger
                            _ledger_id = get_order_ledger().record(
                                bot_id=getattr(self, '_bot_id', 'thusnelda'),
                                bot_type="thusnelda", symbol=sym, side="SELL", order_type="MARKET",
                                qty=str(q), quote_order_qty="0",
                                reason="STOP_LOSS", drawdown_pct=str(drawdown),
                                active_rungs=0, max_rungs=c.max_rungs_per_symbol, execution_mode="LIVE",
                            )
                        except Exception: pass
                        order = await self._signed_call(
                            client,
                            lambda s=sym, qty=q: client.order_market_sell(symbol=s, quantity=str(qty)),
                        )
                        if _ledger_id:
                            try:
                                from runtime.core.order_ledger import get_order_ledger
                                get_order_ledger().update_binance_response(_ledger_id, str((order or {}).get("orderId", "")), str((order or {}).get("status", "")))
                            except Exception: pass
                        self._emit("INFO", "binance:order_market_sell_stop_loss", {"symbol": sym, "response": order})
                        liq_rec["execution"] = "LIVE"
                        liq_rec["quantity"] = str(q)
                        liq_rec["order_id"] = order.get("orderId") if isinstance(order, dict) else None
                    liquidations.append(liq_rec)
                    self._emit("WARNING", "thusnelda:stop_loss_triggered", liq_rec)
        self._emit("INFO", "thusnelda:decision", {"report": report})

        self._maybe_emit_metrics()
        return report
