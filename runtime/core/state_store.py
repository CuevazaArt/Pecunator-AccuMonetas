"""In-memory aggregated state for the MVP (SQLite reserved for a later phase)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional


@dataclass
class StateStore:
    selected_symbol: str = "BTCUSDT"
    ticker: Dict[str, Any] = field(default_factory=dict)
    # bids / asks: list of [price, qty] strings, best first
    orderbook: Dict[str, List[List[str]]] = field(
        default_factory=lambda: {"bids": [], "asks": []}
    )
    recent_trades: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=50))
    # Spot /api/v3/account total balance rows Binance returned (before non-zero filter).
    balances: List[Dict[str, Any]] = field(default_factory=list)
    balances_total_assets_in_response: int = 0
    open_orders: List[Dict[str, Any]] = field(default_factory=list)
    my_trades: List[Dict[str, Any]] = field(default_factory=list)
    # REST account summary excluding raw balances row list (commission / flags / etc.).
    account_summary: Dict[str, Any] = field(default_factory=dict)
    # Rolling spot equity monitor (converted to base asset).
    account_equity: Dict[str, Any] = field(default_factory=dict)
    last_error: Optional[str] = None
    connected: bool = False
    # Last X-MBX-USED-WEIGHT-1M from python-binance after a REST call (IP-scoped).
    api_weight_used_1m: Optional[int] = None
    # Last X-MBX-ORDER-COUNT-10S and 1M from Binance (UID-scoped order rate limits).
    order_count_10s: Optional[int] = None
    order_count_1m: Optional[int] = None
    # Last Binance clock sync values (for UI display/diagnostics).
    binance_server_time_ms: Optional[int] = None
    binance_local_time_ms_at_sync: Optional[int] = None
    binance_offset_ms: Optional[int] = None
    binance_time_synced_at_utc: Optional[str] = None

    def reset_market(self) -> None:
        self.ticker = {}
        self.orderbook = {"bids": [], "asks": []}
        self.recent_trades.clear()

    def spread(self) -> Optional[float]:
        bids = self.orderbook.get("bids") or []
        asks = self.orderbook.get("asks") or []
        if not bids or not asks:
            b = self.ticker.get("b")
            a = self.ticker.get("a")
            if b and a:
                try:
                    return float(a) - float(b)
                except (TypeError, ValueError):
                    return None
            return None
        try:
            return float(asks[0][0]) - float(bids[0][0])
        except (TypeError, ValueError, IndexError):
            return None

    def mid_price(self) -> Optional[float]:
        bids = self.orderbook.get("bids") or []
        asks = self.orderbook.get("asks") or []
        if bids and asks:
            try:
                return (float(bids[0][0]) + float(asks[0][0])) / 2
            except (TypeError, ValueError, IndexError):
                pass
        c = self.ticker.get("c")
        if c is not None:
            try:
                return float(c)
            except (TypeError, ValueError):
                pass
        return None
