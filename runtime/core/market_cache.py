"""Market Cache — In-memory shared data cache for Pecunator bots.

If 50 bots all trade BTCUSDT, they don't need 50 separate API calls
for the same ticker. One call, cached in RAM, serves all 50.

Architecture:
    - Thread-safe with asyncio.Lock per cache key (single-flight pattern).
    - TTL-based expiration per data type.
    - Max 2GB RAM budget (configurable).
    - Deduplicates: tickers, account info, exchange info, open orders.

Weight savings estimate:
    Without cache (100 bots): 100 × get_account(10w) = 1000 weight
    With cache:               1 × get_account(10w) = 10 weight
    → 100x reduction per shared data point.
"""

from __future__ import annotations

import asyncio
import logging
import time
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

_LOG = logging.getLogger("pecunator.core.market_cache")


@dataclass
class CacheEntry:
    """A single cached value with TTL."""
    data: Any
    fetched_at: float  # time.monotonic()
    ttl_sec: float
    api_weight: int  # weight this fetch would have cost
    size_bytes: int = 0

    @property
    def expired(self) -> bool:
        return (time.monotonic() - self.fetched_at) >= self.ttl_sec


# Default TTL and weight config per cache tier
_TIER_DEFAULTS: dict[str, dict[str, Any]] = {
    "tickers":       {"ttl_sec": 5,    "weight": 2,  "desc": "All symbol tickers"},
    "account":       {"ttl_sec": 10,   "weight": 10, "desc": "Account balances"},
    "open_orders":   {"ttl_sec": 5,    "weight": 3,  "desc": "Open orders (per symbol)"},
    "exchange_info": {"ttl_sec": 3600, "weight": 20, "desc": "Exchange info (symbols, filters)"},
    "symbol_ticker": {"ttl_sec": 3,    "weight": 1,  "desc": "Single symbol ticker"},
    "server_time":   {"ttl_sec": 30,   "weight": 1,  "desc": "Binance server time"},
    "klines":        {"ttl_sec": 60,   "weight": 5,  "desc": "Klines (per symbol/interval)"},
}


class MarketCache:
    """In-memory cache for shared market data.

    Usage:
        cache = get_market_cache()
        tickers = await cache.get_or_fetch(
            "tickers",
            fetcher=lambda: client.get_all_tickers(),
        )
    """

    def __init__(self, max_memory_bytes: int = 2 * 1024 * 1024 * 1024) -> None:
        self._entries: dict[str, CacheEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        self._max_memory = max_memory_bytes
        self._stats = {
            "hits": 0,
            "misses": 0,
            "fetches": 0,
            "weight_saved": 0,
        }

    async def get_or_fetch(
        self,
        key: str,
        fetcher: Callable[[], Coroutine[Any, Any, Any]],
        ttl_sec: Optional[float] = None,
        api_weight: Optional[int] = None,
    ) -> Any:
        """Return cached data or call fetcher (single-flight pattern).

        If multiple bots request the same key simultaneously, only ONE
        fetch is performed. All others wait for the result.

        Args:
            key: Cache key (e.g., "tickers", "account", "open_orders:BTCUSDT")
            fetcher: Async callable that fetches the data from Binance
            ttl_sec: Override TTL. If None, uses tier default.
            api_weight: Override weight. If None, uses tier default.
        """
        # Check for cache hit (no lock needed for read)
        entry = self._entries.get(key)
        if entry is not None and not entry.expired:
            self._stats["hits"] += 1
            weight = api_weight or _TIER_DEFAULTS.get(key.split(":")[0], {}).get("weight", 1)
            self._stats["weight_saved"] += weight
            return entry.data

        # Cache miss — acquire per-key lock for single-flight fetch
        lock = await self._get_lock(key)
        async with lock:
            # Double-check after acquiring lock (another waiter may have filled it)
            entry = self._entries.get(key)
            if entry is not None and not entry.expired:
                self._stats["hits"] += 1
                return entry.data

            # Fetch
            self._stats["misses"] += 1
            self._stats["fetches"] += 1
            try:
                data = await fetcher()
            except Exception:
                # On fetch failure, return stale data if available
                if entry is not None:
                    _LOG.warning("Fetch failed for %s, returning stale data", key)
                    return entry.data
                raise

            # Determine TTL and weight
            tier = key.split(":")[0]
            defaults = _TIER_DEFAULTS.get(tier, {"ttl_sec": 10, "weight": 1})
            actual_ttl = ttl_sec if ttl_sec is not None else defaults["ttl_sec"]
            actual_weight = api_weight if api_weight is not None else defaults["weight"]

            # Estimate size
            try:
                size = sys.getsizeof(data)
            except Exception:
                size = 1024  # fallback estimate

            self._entries[key] = CacheEntry(
                data=data,
                fetched_at=time.monotonic(),
                ttl_sec=actual_ttl,
                api_weight=actual_weight,
                size_bytes=size,
            )

            # Evict if over memory budget
            self._evict_if_needed()

            return data

    def invalidate(self, key: str) -> None:
        """Force-expire a specific cache key."""
        self._entries.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        """Invalidate all keys starting with prefix (e.g., 'open_orders')."""
        keys_to_remove = [k for k in self._entries if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._entries[k]

    def clear(self) -> None:
        """Clear the entire cache."""
        self._entries.clear()

    # ── Status ──────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return cache stats for UI/API consumption."""
        total_size = sum(e.size_bytes for e in self._entries.values())
        active = sum(1 for e in self._entries.values() if not e.expired)
        expired = len(self._entries) - active
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0

        return {
            "entries_total": len(self._entries),
            "entries_active": active,
            "entries_expired": expired,
            "memory_bytes": total_size,
            "memory_mb": round(total_size / 1024 / 1024, 2),
            "max_memory_mb": round(self._max_memory / 1024 / 1024, 0),
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "fetches": self._stats["fetches"],
            "hit_rate_pct": round(hit_rate, 1),
            "weight_saved": self._stats["weight_saved"],
            "tiers": {
                tier: {
                    "ttl_sec": cfg["ttl_sec"],
                    "weight": cfg["weight"],
                    "desc": cfg["desc"],
                }
                for tier, cfg in _TIER_DEFAULTS.items()
            },
        }

    # ── Internal ────────────────────────────────────────────────────

    async def _get_lock(self, key: str) -> asyncio.Lock:
        """Get or create a per-key lock (avoids thundering herd)."""
        async with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    def _evict_if_needed(self) -> None:
        """Evict expired entries first, then LRU if still over budget."""
        # Phase 1: remove expired
        expired_keys = [k for k, v in self._entries.items() if v.expired]
        for k in expired_keys:
            del self._entries[k]
            self._locks.pop(k, None)

        # Phase 2: if still over budget, evict oldest entries
        total_size = sum(e.size_bytes for e in self._entries.values())
        if total_size <= self._max_memory:
            return

        # Sort by fetched_at (oldest first) and evict
        sorted_entries = sorted(
            self._entries.items(),
            key=lambda item: item[1].fetched_at,
        )
        for key, entry in sorted_entries:
            if total_size <= self._max_memory:
                break
            total_size -= entry.size_bytes
            del self._entries[key]
            self._locks.pop(key, None)
            _LOG.info("Evicted cache entry %s (%d bytes) — memory pressure", key, entry.size_bytes)


# ── Singleton ───────────────────────────────────────────────────────

_cache: Optional[MarketCache] = None


def get_market_cache(max_memory_bytes: int = 2 * 1024 * 1024 * 1024) -> MarketCache:
    """Get or create the global MarketCache singleton."""
    global _cache
    if _cache is None:
        _cache = MarketCache(max_memory_bytes=max_memory_bytes)
    return _cache
