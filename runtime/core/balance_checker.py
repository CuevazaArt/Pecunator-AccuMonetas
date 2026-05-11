"""
Balance Verification Module for Louise Bot Hub

Provides proactive account balance checking and equity metrics refresh.
Prevents wasted API calls on failed buys when insufficient funds.
Opportunistically refreshes account metrics for UI dashboard.

Key Features:
- Minimum balance verification ($8 USDT free required)
- Fresh equity calculation (cash + position values)
- Metrics caching for fast UI access
- Graceful pause when funds insufficient
- Single API call architecture (Account endpoint only)
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from decimal import Decimal

from binance.exceptions import BinanceAPIException

logger = logging.getLogger(__name__)


@dataclass
class AccountBalance:
    """Snapshot of account financial state at a point in time."""

    free_balance: float
    """USDT available for trading (not locked in orders)."""

    locked_balance: float
    """USDT locked in open orders."""

    total_balance: float
    """free_balance + locked_balance."""

    equity_usdt: float
    """Total account equity: cash + position values."""

    margin_level: float
    """Margin level percentage (e.g., 500 = 5x leverage). 0 if spot only."""

    timestamp: datetime
    """When this snapshot was captured."""

    @property
    def can_trade(self) -> bool:
        """Whether account has minimum balance to execute Louise buy."""
        return self.free_balance >= 8.0

    @property
    def insufficient_amount(self) -> float:
        """Amount needed to reach minimum balance."""
        shortfall = 8.0 - self.free_balance
        return max(0.0, shortfall)

    @property
    def age_seconds(self) -> int:
        """How old this snapshot is (in seconds)."""
        return int((datetime.utcnow() - self.timestamp).total_seconds())


class BalanceChecker:
    """
    Lightweight balance verification for Louise bot execution.

    Responsibilities:
    - Pre-execution balance check (prevents failed buys)
    - Fresh equity metrics retrieval (for UI dashboard)
    - Account health monitoring

    Design:
    - Single API call per check (Account endpoint)
    - Caching layer to avoid redundant calls within 5 seconds
    - Graceful degradation on API failure
    """

    def __init__(
        self,
        binance_gateway,
        min_free_balance: float = 8.0,
        cache_ttl_seconds: int = 5,
        stale_threshold_seconds: int = 30
    ):
        """
        Initialize balance checker.

        Args:
            binance_gateway: AsyncClient wrapper for Binance API
            min_free_balance: Minimum USDT required to attempt buy (default: $8)
            cache_ttl_seconds: Cache valid for this duration (default: 5s)
            stale_threshold_seconds: Alert if data older than this (default: 30s)
        """
        self.gateway = binance_gateway
        self.min_free_balance = min_free_balance
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self.stale_threshold = timedelta(seconds=stale_threshold_seconds)

        # Cache: (timestamp, balance) to avoid redundant API calls
        self._cache: Optional[AccountBalance] = None
        self._cache_expires_at: Optional[datetime] = None

    async def check_and_refresh(self, symbol: str) -> AccountBalance:
        """
        Check account balance and refresh equity metrics.

        This is the main method Louise bot calls before each buy attempt.
        It combines balance verification with metrics refresh to:
        1. Determine if we have minimum funds to trade
        2. Fetch fresh equity data for UI dashboard

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")

        Returns:
            AccountBalance: Current account state snapshot

        Raises:
            BinanceAPIException: If Account endpoint fails
        """
        # Check cache first (avoid redundant API calls within 5 seconds)
        if self._cache and self._cache_expires_at and datetime.utcnow() < self._cache_expires_at:
            logger.debug(f"Using cached balance (age: {self._cache.age_seconds}s)")
            return self._cache

        try:
            # Single API call to get account info
            account = await self.gateway.get_account_async()

            # Extract USDT balance
            usdt_balance = self._extract_asset_balance(account, "USDT")
            free_balance = usdt_balance["free"]
            locked_balance = usdt_balance["locked"]

            # Calculate total equity (cash + positions)
            equity = await self._calculate_equity(account, symbol)

            # Extract margin level if applicable
            margin_level = self._extract_margin_level(account)

            # Create snapshot
            balance = AccountBalance(
                free_balance=free_balance,
                locked_balance=locked_balance,
                total_balance=free_balance + locked_balance,
                equity_usdt=equity,
                margin_level=margin_level,
                timestamp=datetime.utcnow()
            )

            # Update cache
            self._cache = balance
            self._cache_expires_at = datetime.utcnow() + self.cache_ttl

            logger.info(
                f"Balance check: free=${free_balance:.2f}, "
                f"equity=${equity:.2f}, can_trade={balance.can_trade}"
            )

            return balance

        except BinanceAPIException as e:
            logger.error(f"Balance check API error: {e}")

            # Graceful degradation: return cached value if available
            if self._cache:
                logger.warning(f"Using stale cache (age: {self._cache.age_seconds}s)")
                return self._cache

            # If no cache, must raise
            raise

    async def has_minimum_balance(self, symbol: str) -> bool:
        """
        Quick check: does account have enough to trade?

        Returns:
            bool: True if free_balance >= min_free_balance
        """
        balance = await self.check_and_refresh(symbol)
        return balance.can_trade

    async def verify_before_buy(self, symbol: str, buy_amount_usdt: float) -> tuple[bool, Optional[str]]:
        """
        Comprehensive pre-buy verification.

        Args:
            symbol: Trading pair
            buy_amount_usdt: Amount about to buy

        Returns:
            (can_buy, reason_if_not): Tuple of (allowed, error_message)
        """
        balance = await self.check_and_refresh(symbol)

        # Check 1: Minimum balance requirement
        if not balance.can_trade:
            return (
                False,
                f"Insufficient balance: ${balance.free_balance:.2f} < ${self.min_free_balance:.2f}"
            )

        # Check 2: Specific buy amount
        if balance.free_balance < buy_amount_usdt:
            return (
                False,
                f"Not enough for buy: ${balance.free_balance:.2f} < ${buy_amount_usdt:.2f}"
            )

        # Check 3: Data freshness (warn if stale)
        if balance.age_seconds > self.stale_threshold.total_seconds():
            logger.warning(f"Balance data is stale: {balance.age_seconds}s old")

        return (True, None)

    def _extract_asset_balance(self, account: Dict[str, Any], asset: str) -> Dict[str, float]:
        """Extract free and locked balance for an asset."""
        for balance in account.get("balances", []):
            if balance.get("asset") == asset:
                return {
                    "free": float(balance.get("free", 0)),
                    "locked": float(balance.get("locked", 0))
                }

        # Asset not found (e.g., USDT on fresh account)
        return {"free": 0.0, "locked": 0.0}

    async def _calculate_equity(self, account: Dict[str, Any], symbol: str) -> float:
        """
        Calculate total account equity in USDT.

        Includes:
        - USDT cash balance
        - Position value in symbol's asset (current price * quantity)

        Args:
            account: Account info from Binance API
            symbol: Trading pair (e.g., "BTCUSDT")

        Returns:
            float: Total equity in USDT
        """
        # Get USDT cash
        usdt_balance = self._extract_asset_balance(account, "USDT")
        cash_value = usdt_balance["free"] + usdt_balance["locked"]

        # Get position in symbol's asset
        base_asset = symbol.replace("USDT", "").replace("/", "")
        asset_balance = self._extract_asset_balance(account, base_asset)
        position_quantity = asset_balance["free"] + asset_balance["locked"]

        # If no position, equity = cash
        if position_quantity <= 0:
            return cash_value

        # Fetch current price and calculate position value
        try:
            current_price = await self.gateway.get_symbol_price_async(symbol)
            position_value = position_quantity * current_price

            logger.debug(
                f"Equity calc: cash=${cash_value:.2f}, "
                f"position={position_quantity:.8f} @ ${current_price:.2f} = ${position_value:.2f}"
            )

            return cash_value + position_value

        except Exception as e:
            logger.warning(f"Could not fetch current price for {symbol}: {e}")
            # Fallback to cash only
            return cash_value

    def _extract_margin_level(self, account: Dict[str, Any]) -> float:
        """Extract margin level if account has margin enabled."""
        # Binance returns marginLevel as string percentage
        margin_level_str = account.get("marginLevel")

        if margin_level_str:
            try:
                return float(margin_level_str)
            except (ValueError, TypeError):
                pass

        return 0.0  # No margin or spot account

    def get_cached_balance(self) -> Optional[AccountBalance]:
        """
        Get last cached balance without API call.

        Used by UI for fast access to metrics.
        Returns None if cache expired.
        """
        if (
            self._cache
            and self._cache_expires_at
            and datetime.utcnow() < self._cache_expires_at
        ):
            return self._cache

        return None


class BalanceMonitor:
    """
    Continuous monitor for account balance health.

    Tracks:
    - Balance trends over time
    - Alerts for low balance
    - Equity curve updates

    Used by UI dashboard for historical equity charts.
    """

    def __init__(self, balance_checker: BalanceChecker, max_history: int = 288):
        """
        Initialize balance monitor.

        Args:
            balance_checker: BalanceChecker instance
            max_history: Keep last N balance snapshots (default: 288 = 24h @ 5min polls)
        """
        self.checker = balance_checker
        self.max_history = max_history
        self.history: list[AccountBalance] = []

    async def record_balance(self, symbol: str) -> AccountBalance:
        """
        Record current balance and return it.

        Args:
            symbol: Trading pair

        Returns:
            AccountBalance: Current snapshot
        """
        balance = await self.checker.check_and_refresh(symbol)

        # Add to history
        self.history.append(balance)

        # Trim if too long
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        logger.debug(f"Recorded balance: {balance.equity_usdt:.2f} USDT")

        return balance

    def get_equity_trend(self) -> list[Dict[str, Any]]:
        """
        Get equity history for UI charts.

        Returns:
            List of (timestamp, equity_usdt) tuples for charting
        """
        return [
            {
                "timestamp": b.timestamp.isoformat(),
                "equity": round(b.equity_usdt, 2),
                "free_balance": round(b.free_balance, 2)
            }
            for b in self.history
        ]

    def get_statistics(self) -> Dict[str, float]:
        """
        Calculate equity statistics from history.

        Returns:
            Dict with min, max, avg, latest equity
        """
        if not self.history:
            return {}

        equities = [b.equity_usdt for b in self.history]

        return {
            "current": equities[-1],
            "min": min(equities),
            "max": max(equities),
            "avg": sum(equities) / len(equities),
            "change_24h": equities[-1] - (equities[0] if equities else 0)
        }
