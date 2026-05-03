"""Binance Spot: REST via python-binance; public streams via asyncio websockets."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

import websockets
from binance.client import Client
from binance.exceptions import BinanceAPIException

from runtime.connectors.account_info import summarize_binance_account_rest
from runtime.core.equity import (
    EquityRollingWindow,
    build_ticker_price_map,
    compute_spot_equity_in_base,
)
from runtime.core.event_bus import EventBus
from runtime.core.security_util import sanitize_log_message
from runtime.core.rest_usage_log import RestUsageLog, get_rest_usage_log
from runtime.core.settings import (
    account_poll_interval_sec,
    equity_avg_window_samples,
    equity_base_asset,
    equity_poll_stride,
)
from runtime.core.state_store import StateStore

WS_BASE = "wss://stream.binance.com:9443/stream"
LOG_TOPIC = "runtime.log"

_LOG = logging.getLogger("pecunator.binance.rest")

T = TypeVar("T")


def normalize_binance_spot_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if not s.isalnum() or len(s) < 5 or len(s) > 32:
        raise ValueError("Invalid spot symbol format")
    return s


class BinanceGateway:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        bus: EventBus,
        state: StateStore,
        log: Callable[[str], None],
        data_dir: Path | None = None,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.bus = bus
        self.state = state
        self._log = log
        self._client: Optional[Client] = None
        self._ws_task: Optional[asyncio.Task[Any]] = None
        self._poll_task: Optional[asyncio.Task[Any]] = None
        self._user_data_task: Optional[asyncio.Task[Any]] = None
        self._listen_key: Optional[str] = None
        self._stop = asyncio.Event()
        self._poll_cycle = 0
        self._last_time_sync_monotonic = 0.0
        self._time_sync_interval_sec = 300.0  # 5 min (sweet spot for DCA)
        self._logged_account_rest_snapshot = False
        self._ticker_prices: dict[str, Decimal] = {}
        self._equity_rolling = EquityRollingWindow(sample_window=equity_avg_window_samples())
        self._rest_usage_log: Optional[RestUsageLog] = (
            get_rest_usage_log(data_dir) if data_dir else None
        )

    def _capture_rest_weight_from_client(
        self,
        *,
        action: str,
        note: str | None = None,
    ) -> None:
        """Read X-MBX-USED-WEIGHT-1M from python-binance last response.
        Also feeds the API Fuse to trigger emergency shutdown if weight is too high."""
        from runtime.core.api_fuse import get_api_fuse
        if self._client is None:
            return
        try:
            resp = getattr(self._client, "response", None)
            if resp is None:
                return
            headers = getattr(resp, "headers", None) or {}
            raw = None
            for k, v in headers.items():
                if str(k).upper() == "X-MBX-USED-WEIGHT-1M":
                    raw = v
                    break
            if raw is not None:
                used = int(float(raw))
                self.state.api_weight_used_1m = used
                if self._rest_usage_log is not None:
                    self._rest_usage_log.record_event(
                        source="gateway",
                        action=action,
                        used_weight_1m=used,
                        note=note,
                    )
                # Feed the API Fuse — trips if weight exceeds threshold.
                fuse = get_api_fuse()
                fuse.check_weight(used)
        except (TypeError, ValueError, AttributeError):
            pass

    def _emit_log(self, msg: str) -> None:
        self._log(msg)
        self.bus.publish(LOG_TOPIC, msg)

    @staticmethod
    async def _to_thread(fn: Callable[[], T]) -> T:
        return await asyncio.to_thread(fn)

    @staticmethod
    def _api_error_summary(e: BinanceAPIException) -> str:
        code = getattr(e, "code", "") or ""
        msg = getattr(e, "message", str(e)) or ""
        status = getattr(e, "status_code", "") or ""
        raw = f"{status} {code} {msg}".strip()
        return sanitize_log_message(raw)

    async def test_connection(self) -> None:
        def probe() -> None:
            client = Client(
                self.api_key,
                self.api_secret,
                requests_params={"timeout": 30},
            )
            try:
                client.get_account()
            finally:
                client.session.close()

        try:
            await self._to_thread(probe)
        except BinanceAPIException as e:
            raise RuntimeError(self._api_error_summary(e)) from None
        except Exception as e:
            raise RuntimeError(sanitize_log_message(str(e))) from None

    async def fetch_account(self) -> None:
        if self._client is None:
            return
        try:
            data = await self._to_thread(lambda: self._client.get_account())
        except BinanceAPIException as e:
            self.state.last_error = self._api_error_summary(e)
            self._emit_log(f"account: {self.state.last_error}")
            # Feed fuse on error code.
            from runtime.core.api_fuse import get_api_fuse
            code = getattr(e, 'code', 0) or 0
            get_api_fuse().on_error_code(int(code), str(getattr(e, 'message', '')))
            return
        except OSError as e:
            self._emit_log(f"account: {sanitize_log_message(str(e))}")
            return

        summ = summarize_binance_account_rest(data)
        self.state.account_summary = summ
        raw_bal = data.get("balances", [])
        if not isinstance(raw_bal, list):
            raw_bal = []
        self.state.balances_total_assets_in_response = len(raw_bal)
        self.state.balances = [
            b
            for b in raw_bal
            if float(b.get("free", 0) or 0) > 0 or float(b.get("locked", 0) or 0) > 0
        ]
        self.bus.publish("account.balances", self.state.balances)
        self.state.last_error = None
        self._capture_rest_weight_from_client(action="fetch_account:get_account")

        _msg = (
            "GET /api/v3/account: "
            f"accountType={summ['accountType']} "
            f"canTrade={summ['canTrade']} "
            f"canWithdraw={summ['canWithdraw']} "
            f"canDeposit={summ['canDeposit']} "
            f"maker={summ['makerCommission']} "
            f"taker={summ['takerCommission']} "
            f"updateTime={summ['updateTime']} "
            f"balancesWithFunds={len(self.state.balances)}"
        )
        if not self._logged_account_rest_snapshot:
            _LOG.info("Binance REST connected; %s", _msg)
            self._emit_log(f"REST OK: {_msg}")
            self._logged_account_rest_snapshot = True
        else:
            _LOG.debug("%s", _msg)

    async def refresh_rest_weight(self) -> None:
        """Deprecated: avoid extra ping calls for weight reads."""
        return

    async def refresh_equity(self, *, force_tickers: bool = False, base_asset: str | None = None) -> None:
        if self._client is None:
            return
        if force_tickers or not self._ticker_prices:
            try:
                raw_tickers = await self._to_thread(lambda: self._client.get_all_tickers())
                self._ticker_prices = build_ticker_price_map(raw_tickers)
                self._capture_rest_weight_from_client(action="refresh_equity:get_all_tickers")
            except BinanceAPIException as e:
                self._emit_log(f"equity:ticker {self._api_error_summary(e)}")
                return
            except OSError as e:
                self._emit_log(f"equity:ticker {sanitize_log_message(str(e))}")
                return
            except Exception as e:
                self._emit_log(f"equity:ticker {sanitize_log_message(str(e))}")
                return

        base = (base_asset or equity_base_asset()).strip().upper() or "USDT"
        snap = compute_spot_equity_in_base(self.state.balances, self._ticker_prices, base_asset=base)
        roll = self._equity_rolling.update(base_asset=base, current=Decimal(snap["current"]))
        self.state.account_equity = {
            **snap,
            "avg": roll["avg"],
            "high_avg": roll["high_avg"],
            "samples": int(roll["samples"]),
            "sample_window": int(roll["sample_window"]),
            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        self.bus.publish("account.equity", dict(self.state.account_equity))

    async def sync_time(self) -> Dict[str, Any]:
        if self._client is None:
            raise RuntimeError("Gateway client not started")
        data = await self._to_thread(lambda: self._client.get_server_time())
        server_ms = int(data.get("serverTime", 0) or 0)
        local_ms = int(time.time() * 1000)
        offset_ms = server_ms - local_ms
        try:
            self._client.timestamp_offset = offset_ms
        except Exception:
            pass
        self.state.binance_server_time_ms = server_ms
        self.state.binance_local_time_ms_at_sync = local_ms
        self.state.binance_offset_ms = offset_ms
        self.state.binance_time_synced_at_utc = dt.datetime.now(
            dt.timezone.utc
        ).isoformat()
        msg = (
            f"time sync: local={local_ms} server={server_ms} offset_ms={offset_ms}"
        )
        self._emit_log(msg)
        self._capture_rest_weight_from_client(action="sync_time:get_server_time")
        return {
            "local_time_ms": local_ms,
            "server_time_ms": server_ms,
            "offset_ms": offset_ms,
            "source": "gateway",
        }

    async def fetch_open_orders(self) -> None:
        if self._client is None:
            return
        try:
            orders = await self._to_thread(lambda: self._client.get_open_orders())
        except BinanceAPIException as e:
            self.state.last_error = self._api_error_summary(e)
            self._emit_log(f"openOrders: {self.state.last_error}")
            return
        except OSError as e:
            self._emit_log(f"openOrders: {sanitize_log_message(str(e))}")
            return
        if not isinstance(orders, list):
            orders = []
        self.state.open_orders = orders
        self.bus.publish("account.open_orders", self.state.open_orders)
        self.state.last_error = None
        self._capture_rest_weight_from_client(action="fetch_open_orders:get_open_orders")

    async def fetch_my_trades(self, symbol: str, limit: int = 20) -> None:
        if self._client is None:
            return
        try:
            sym = normalize_binance_spot_symbol(symbol)
        except ValueError:
            self.state.last_error = "Invalid symbol for myTrades"
            self._emit_log(self.state.last_error)
            return
        try:
            raw = await self._to_thread(
                lambda: self._client.get_my_trades(symbol=sym, limit=limit)
            )
        except BinanceAPIException as e:
            self.state.last_error = self._api_error_summary(e)
            self._emit_log(f"myTrades: {self.state.last_error}")
            return
        except OSError as e:
            self._emit_log(f"myTrades: {sanitize_log_message(str(e))}")
            return
        self.state.my_trades = list(reversed(raw if isinstance(raw, list) else []))
        self.bus.publish("account.my_trades", self.state.my_trades)
        self.state.last_error = None
        self._capture_rest_weight_from_client(
            action=f"fetch_my_trades:get_my_trades:{sym}"
        )

    async def fetch_book_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        if self._client is None:
            return None
        try:
            sym = normalize_binance_spot_symbol(symbol)
        except ValueError:
            return None
        try:
            out = await self._to_thread(lambda: self._client.get_orderbook_ticker(symbol=sym))
            self._capture_rest_weight_from_client(
                action=f"fetch_book_ticker:get_orderbook_ticker:{sym}"
            )
            return out
        except (BinanceAPIException, OSError):
            return None

    def stream_url(self, symbol: str) -> str:
        s = symbol.lower()
        streams = f"{s}@ticker/{s}@depth20@100ms/{s}@trade"
        return f"{WS_BASE}?streams={streams}"

    async def _websocket_loop(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                sym = normalize_binance_spot_symbol(self.state.selected_symbol)
            except ValueError:
                self._emit_log("Invalid symbol in state; set a valid Spot pair (e.g. BTCUSDT)")
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass
                continue
            url = self.stream_url(sym)
            self._emit_log(f"WebSocket connecting: {sym}")
            try:
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                ) as ws:
                    backoff = 1.0
                    self.state.connected = True
                    async for raw in ws:
                        if self._stop.is_set():
                            break
                        msg = json.loads(raw)
                        stream = msg.get("stream", "")
                        data = msg.get("data", msg)
                        if stream.endswith("@ticker"):
                            self._on_ticker(data)
                        elif "@depth" in stream:
                            self._on_depth(data)
                        elif stream.endswith("@trade"):
                            self._on_trade(data)
            except asyncio.CancelledError:
                self.state.connected = False
                raise
            except Exception as e:
                self.state.connected = False
                self._emit_log(
                    f"WebSocket error ({type(e).__name__}: {sanitize_log_message(str(e))}), "
                    f"retry in {backoff:.0f}s"
                )
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, 60.0)
        self._emit_log("WebSocket stopped")

    def _on_ticker(self, data: Dict[str, Any]) -> None:
        self.state.ticker = data
        self.bus.publish(f"market.ticker.{data.get('s', '')}", data)

    def _on_depth(self, data: Dict[str, Any]) -> None:
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        self.state.orderbook = {"bids": bids[:10], "asks": asks[:10]}
        sym = self.state.selected_symbol
        self.bus.publish(f"market.orderbook.{sym}", self.state.orderbook)

    def _on_trade(self, data: Dict[str, Any]) -> None:
        self.state.recent_trades.appendleft(data)
        sym = data.get("s", self.state.selected_symbol)
        self.bus.publish(f"market.trades.{sym}", data)

    # ── User Data Stream (ZERO weight for balance/order updates) ──────

    async def _obtain_listen_key(self) -> Optional[str]:
        """POST /api/v3/userDataStream → listenKey (1 weight point)."""
        if self._client is None:
            return None
        try:
            data = await self._to_thread(lambda: self._client.stream_get_listen_key())
            self._capture_rest_weight_from_client(action="user_data:stream_get_listen_key")
            self._emit_log(f"User Data Stream: listenKey obtained")
            return data
        except BinanceAPIException as e:
            self._emit_log(f"User Data Stream: listenKey error: {self._api_error_summary(e)}")
            from runtime.core.api_fuse import get_api_fuse
            code = getattr(e, 'code', 0) or 0
            get_api_fuse().on_error_code(int(code), str(getattr(e, 'message', '')))
            return None
        except Exception as e:
            self._emit_log(f"User Data Stream: listenKey error: {sanitize_log_message(str(e))}")
            return None

    async def _keepalive_listen_key(self) -> bool:
        """PUT /api/v3/userDataStream — keepalive (1 weight point). Must be called < 60 min."""
        if self._client is None or not self._listen_key:
            return False
        try:
            await self._to_thread(lambda: self._client.stream_keepalive(self._listen_key))
            self._capture_rest_weight_from_client(action="user_data:stream_keepalive")
            return True
        except Exception as e:
            self._emit_log(f"User Data Stream keepalive failed: {sanitize_log_message(str(e))}")
            return False

    def _on_user_data(self, data: Dict[str, Any]) -> None:
        """Process User Data Stream events (ZERO weight — pure WebSocket)."""
        event_type = data.get("e", "")

        if event_type == "outboundAccountPosition":
            # Balance update — replaces get_account() polling.
            balances_raw = data.get("B", [])
            if isinstance(balances_raw, list):
                for b in balances_raw:
                    asset = str(b.get("a", "")).upper()
                    free = b.get("f", "0")
                    locked = b.get("l", "0")
                    # Update in-place in state.balances
                    found = False
                    for existing in self.state.balances:
                        if isinstance(existing, dict) and str(existing.get("asset", "")).upper() == asset:
                            existing["free"] = free
                            existing["locked"] = locked
                            found = True
                            break
                    if not found and (float(free) > 0 or float(locked) > 0):
                        self.state.balances.append({"asset": asset, "free": free, "locked": locked})
                self.bus.publish("account.balances", self.state.balances)
                _LOG.debug("User Data Stream: balances updated (%d assets)", len(balances_raw))

        elif event_type == "executionReport":
            # Order update — replaces get_open_orders() and get_my_trades() polling.
            order_status = str(data.get("X", "")).upper()  # NEW, FILLED, CANCELED, etc.
            symbol = str(data.get("s", "")).upper()
            order_id = data.get("i")
            side = str(data.get("S", "")).upper()
            order_type = str(data.get("o", "")).upper()
            qty = data.get("q", "0")
            price = data.get("p", "0")
            exec_qty = data.get("l", "0")  # last executed qty
            exec_price = data.get("L", "0")  # last executed price

            self._emit_log(
                f"WS executionReport: {symbol} {side} {order_type} "
                f"status={order_status} orderId={order_id} qty={qty} price={price}"
            )
            self.bus.publish("account.execution_report", data)

            # If order is NEW or PARTIALLY_FILLED, add/update open_orders
            if order_status in ("NEW", "PARTIALLY_FILLED"):
                order_dict = {
                    "symbol": symbol, "orderId": order_id, "side": side,
                    "type": order_type, "origQty": qty, "price": price,
                    "status": order_status,
                }
                existing = [o for o in self.state.open_orders if o.get("orderId") == order_id]
                if existing:
                    existing[0].update(order_dict)
                else:
                    self.state.open_orders.append(order_dict)
            elif order_status in ("FILLED", "CANCELED", "EXPIRED", "REJECTED"):
                self.state.open_orders = [
                    o for o in self.state.open_orders if o.get("orderId") != order_id
                ]
            self.bus.publish("account.open_orders", self.state.open_orders)

            # Track as a trade if filled
            if order_status == "FILLED" or (order_status == "PARTIALLY_FILLED" and float(exec_qty) > 0):
                trade = {
                    "symbol": symbol, "orderId": order_id, "side": side,
                    "price": exec_price, "qty": exec_qty,
                    "time": data.get("T"),
                    "isBuyer": side == "BUY",
                }
                self.state.my_trades.append(trade)
                if len(self.state.my_trades) > 100:
                    self.state.my_trades = self.state.my_trades[-100:]
                self.bus.publish("account.my_trades", self.state.my_trades)

        elif event_type == "balanceUpdate":
            # Deposit/withdrawal — not common but good to capture.
            asset = str(data.get("a", "")).upper()
            delta = data.get("d", "0")
            self._emit_log(f"WS balanceUpdate: {asset} delta={delta}")

    async def _user_data_ws_loop(self) -> None:
        """WebSocket loop for User Data Stream (balances + orders in real-time, ZERO weight)."""
        backoff = 2.0
        keepalive_sec = 1800.0  # 30 min (Binance requires < 60 min)
        while not self._stop.is_set():
            self._listen_key = await self._obtain_listen_key()
            if not self._listen_key:
                self._emit_log("User Data Stream: no listenKey, retry in 30s")
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=30.0)
                except asyncio.TimeoutError:
                    pass
                continue
            url = f"wss://stream.binance.com:9443/ws/{self._listen_key}"
            self._emit_log(f"User Data Stream: connecting...")
            try:
                async with websockets.connect(
                    url, ping_interval=20, ping_timeout=20, close_timeout=5,
                ) as ws:
                    backoff = 2.0
                    self._emit_log("User Data Stream: connected ✅ (balances+orders in real-time, 0 weight)")
                    last_keepalive = time.monotonic()
                    while not self._stop.is_set():
                        # Keepalive check
                        if (time.monotonic() - last_keepalive) >= keepalive_sec:
                            ok = await self._keepalive_listen_key()
                            if ok:
                                last_keepalive = time.monotonic()
                                self._emit_log("User Data Stream: keepalive OK (1 pt)")
                            else:
                                self._emit_log("User Data Stream: keepalive failed, reconnecting...")
                                break
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=60.0)
                        except asyncio.TimeoutError:
                            continue  # No events, just loop for keepalive check
                        msg = json.loads(raw)
                        self._on_user_data(msg)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._emit_log(
                    f"User Data Stream error ({type(e).__name__}: "
                    f"{sanitize_log_message(str(e))}), retry in {backoff:.0f}s"
                )
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, 60.0)

    # ── Lightweight REST poll (only time_sync + equity) ──────────────

    async def _poll_account_loop(self, interval: float) -> None:
        """Minimal REST loop: only time_sync and equity refresh.
        Balances and orders are handled by User Data Stream (ZERO weight).
        """
        from runtime.core.api_fuse import get_api_fuse
        eq_stride = equity_poll_stride()
        while not self._stop.is_set():
            # ── API FUSE CHECK ──────────────────────────────────
            fuse = get_api_fuse()
            if fuse.is_tripped():
                remaining = fuse.remaining_cooldown_sec()
                self._emit_log(
                    f"🚨 API FUSE ACTIVO: REST bloqueado por {remaining:.0f}s más"
                )
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=min(30.0, remaining))
                except asyncio.TimeoutError:
                    pass
                continue
            # ── Lightweight polling (time_sync + equity only) ───
            try:
                # Time sync (1 weight point)
                now_mono = time.monotonic()
                if (
                    self._last_time_sync_monotonic <= 0
                    or (now_mono - self._last_time_sync_monotonic)
                    >= self._time_sync_interval_sec
                ):
                    try:
                        await self.sync_time()
                    except Exception as e:
                        self._emit_log(
                            f"time sync: {sanitize_log_message(str(e))}"
                        )
                    self._last_time_sync_monotonic = now_mono

                # Equity refresh (2 weight points for get_all_tickers)
                self._poll_cycle += 1
                if eq_stride <= 1 or (self._poll_cycle % eq_stride == 0):
                    await self.refresh_equity(force_tickers=True)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._emit_log(f"poll light: {sanitize_log_message(str(e))}")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def start(self) -> None:
        self._stop.clear()
        self._poll_cycle = 0
        self._last_time_sync_monotonic = 0.0
        self._logged_account_rest_snapshot = False
        self._ticker_prices = {}
        poll_sec = account_poll_interval_sec()
        self._client = Client(
            self.api_key,
            self.api_secret,
            requests_params={"timeout": 30},
        )
        _LOG.info(
            "BinanceGateway starting: WS-First architecture "
            "(User Data Stream + Market WS + light REST poll %.2fs, symbol=%s)",
            poll_sec,
            self.state.selected_symbol,
        )
        # 1. Market data stream (ticker, depth, trades) — ZERO weight
        self._ws_task = asyncio.create_task(self._websocket_loop())
        # 2. User Data Stream (balances, orders) — ZERO weight after listenKey
        self._user_data_task = asyncio.create_task(self._user_data_ws_loop())
        # 3. Light REST poll (only time_sync + equity) — ~3 pts per cycle
        self._poll_task = asyncio.create_task(self._poll_account_loop(poll_sec))
        self._emit_log(
            f"WS-First: Market WS + User Data Stream + REST poll {poll_sec:.0f}s "
            f"(equity stride {equity_poll_stride()}, base={equity_base_asset()})"
        )

    async def restart_market_stream(self) -> None:
        self.state.reset_market()
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        if not self._stop.is_set():
            self._ws_task = asyncio.create_task(self._websocket_loop())

    async def stop(self) -> None:
        self._stop.set()
        tasks: List[asyncio.Task[Any]] = [
            t for t in (self._ws_task, self._poll_task, self._user_data_task) if t
        ]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._ws_task = None
        self._poll_task = None
        self._user_data_task = None
        # Close listenKey
        if self._client and self._listen_key:
            try:
                await self._to_thread(lambda: self._client.stream_close(self._listen_key))
            except Exception:
                pass
        self._listen_key = None
        if self._client is not None:
            try:
                self._client.session.close()
            except Exception:
                pass
            self._client = None
        self.state.connected = False
