"""Binance Spot: REST via official binance-connector; public streams via asyncio websockets."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, TypeVar

import websockets
from binance.error import ClientError, ServerError
from binance.spot import Spot

from runtime.core.event_bus import EventBus
from runtime.core.security_util import sanitize_log_message
from runtime.core.state_store import StateStore

WS_BASE = "wss://stream.binance.com:9443/stream"
LOG_TOPIC = "runtime.log"

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
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.bus = bus
        self.state = state
        self._log = log
        self._spot: Optional[Spot] = None
        self._ws_task: Optional[asyncio.Task[Any]] = None
        self._poll_task: Optional[asyncio.Task[Any]] = None
        self._stop = asyncio.Event()

    def _emit_log(self, msg: str) -> None:
        self._log(msg)
        self.bus.publish(LOG_TOPIC, msg)

    @staticmethod
    async def _to_thread(fn: Callable[[], T]) -> T:
        return await asyncio.to_thread(fn)

    def _client_error_summary(self, e: ClientError) -> str:
        msg = f"{e.status_code} {getattr(e, 'error_code', '')} {getattr(e, 'error_message', '')}"
        return sanitize_log_message(msg)

    async def test_connection(self) -> None:
        def probe() -> None:
            client = Spot(self.api_key, self.api_secret, timeout=30)
            try:
                client.account()
            finally:
                client.session.close()

        try:
            await self._to_thread(probe)
        except (ClientError, ServerError) as e:
            raise RuntimeError(sanitize_log_message(str(e))) from None

    async def fetch_account(self) -> None:
        if self._spot is None:
            return
        try:
            data = await self._to_thread(lambda: self._spot.account())
        except ClientError as e:
            self.state.last_error = self._client_error_summary(e)
            self._emit_log(f"account: {self.state.last_error}")
            return
        except (ServerError, OSError) as e:
            self._emit_log(f"account: {sanitize_log_message(str(e))}")
            return
        self.state.balances = [
            b
            for b in data.get("balances", [])
            if float(b.get("free", 0) or 0) > 0 or float(b.get("locked", 0) or 0) > 0
        ]
        self.bus.publish("account.balances", self.state.balances)
        self.state.last_error = None

    async def fetch_open_orders(self) -> None:
        if self._spot is None:
            return
        try:
            orders = await self._to_thread(lambda: self._spot.get_open_orders())
        except ClientError as e:
            self.state.last_error = self._client_error_summary(e)
            self._emit_log(f"openOrders: {self.state.last_error}")
            return
        except (ServerError, OSError) as e:
            self._emit_log(f"openOrders: {sanitize_log_message(str(e))}")
            return
        if not isinstance(orders, list):
            orders = []
        self.state.open_orders = orders
        self.bus.publish("account.open_orders", self.state.open_orders)
        self.state.last_error = None

    async def fetch_my_trades(self, symbol: str, limit: int = 20) -> None:
        if self._spot is None:
            return
        try:
            sym = normalize_binance_spot_symbol(symbol)
        except ValueError:
            self.state.last_error = "Invalid symbol for myTrades"
            self._emit_log(self.state.last_error)
            return
        try:
            raw = await self._to_thread(
                lambda: self._spot.my_trades(symbol=sym, limit=limit)
            )
        except ClientError as e:
            self.state.last_error = self._client_error_summary(e)
            self._emit_log(f"myTrades: {self.state.last_error}")
            return
        except (ServerError, OSError) as e:
            self._emit_log(f"myTrades: {sanitize_log_message(str(e))}")
            return
        self.state.my_trades = list(reversed(raw if isinstance(raw, list) else []))
        self.bus.publish("account.my_trades", self.state.my_trades)
        self.state.last_error = None

    async def fetch_book_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        if self._spot is None:
            return None
        try:
            sym = normalize_binance_spot_symbol(symbol)
        except ValueError:
            return None
        try:
            return await self._to_thread(lambda: self._spot.book_ticker(symbol=sym))
        except (ClientError, ServerError, OSError):
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

    async def _poll_account_loop(self, interval: float = 3.0) -> None:
        while not self._stop.is_set():
            try:
                await self.fetch_account()
                await self.fetch_open_orders()
                await self.fetch_my_trades(self.state.selected_symbol)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._emit_log(f"poll account: {sanitize_log_message(str(e))}")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def start(self) -> None:
        self._stop.clear()
        self._spot = Spot(self.api_key, self.api_secret, timeout=30)
        self._ws_task = asyncio.create_task(self._websocket_loop())
        self._poll_task = asyncio.create_task(self._poll_account_loop())

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
        tasks: List[asyncio.Task[Any]] = [t for t in (self._ws_task, self._poll_task) if t]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._ws_task = None
        self._poll_task = None
        if self._spot is not None:
            try:
                self._spot.session.close()
            except Exception:
                pass
            self._spot = None
        self.state.connected = False
