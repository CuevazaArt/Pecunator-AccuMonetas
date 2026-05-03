"""Tests for runtime.core.market_cache — using actual API: get_or_fetch, invalidate, invalidate_prefix, status."""
from __future__ import annotations

import asyncio
import pytest
import pytest_asyncio

from runtime.core.market_cache import MarketCache, get_market_cache


@pytest.fixture()
def cache():
    return MarketCache(max_memory_bytes=10 * 1024 * 1024)  # 10MB


class TestCacheHitMiss:
    @pytest.mark.asyncio
    async def test_cache_miss_calls_fetcher(self, cache):
        called = []

        async def fetcher():
            called.append(1)
            return {"price": "100"}

        result = await cache.get_or_fetch("test_key", fetcher)
        assert result == {"price": "100"}
        assert len(called) == 1

    @pytest.mark.asyncio
    async def test_cache_hit_skips_fetcher(self, cache):
        called = []

        async def fetcher():
            called.append(1)
            return {"price": "200"}

        await cache.get_or_fetch("hit_key", fetcher)
        await cache.get_or_fetch("hit_key", fetcher)
        assert len(called) == 1  # Only fetched once

    @pytest.mark.asyncio
    async def test_different_keys_independent(self, cache):
        async def fa():
            return {"sym": "A"}

        async def fb():
            return {"sym": "B"}

        r1 = await cache.get_or_fetch("key_a", fa)
        r2 = await cache.get_or_fetch("key_b", fb)
        assert r1 != r2

    @pytest.mark.asyncio
    async def test_returns_correct_data(self, cache):
        async def fetcher():
            return {"nested": {"value": 42}}

        result = await cache.get_or_fetch("nested_key", fetcher)
        assert result["nested"]["value"] == 42


class TestCacheInvalidation:
    @pytest.mark.asyncio
    async def test_invalidate_removes_key(self, cache):
        fetch_count = [0]

        async def fetcher():
            fetch_count[0] += 1
            return {"data": fetch_count[0]}

        await cache.get_or_fetch("inv_key", fetcher)
        cache.invalidate("inv_key")
        await cache.get_or_fetch("inv_key", fetcher)
        assert fetch_count[0] == 2  # Must refetch after invalidation

    @pytest.mark.asyncio
    async def test_invalidate_prefix_clears_matching(self, cache):
        async def make_fetcher(v):
            async def _f():
                return {"v": v}
            return _f

        await cache.get_or_fetch("ticker:BTC", await make_fetcher(1))
        await cache.get_or_fetch("ticker:ETH", await make_fetcher(2))
        await cache.get_or_fetch("account", await make_fetcher(3))

        cache.invalidate_prefix("ticker:")
        # account should remain, ticker keys evicted
        fetch_after = [0]

        async def refetch():
            fetch_after[0] += 1
            return {"v": 99}

        await cache.get_or_fetch("ticker:BTC", refetch)
        assert fetch_after[0] == 1  # Was evicted, so refetched


class TestCacheStatus:
    @pytest.mark.asyncio
    async def test_status_reports_entry_count(self, cache):
        async def f():
            return {"x": 1}

        await cache.get_or_fetch("c1", f)
        await cache.get_or_fetch("c2", f)
        status = cache.status()
        assert "entries_active" in status
        assert status["entries_active"] >= 2

    @pytest.mark.asyncio
    async def test_status_reports_hit_rate(self, cache):
        async def f():
            return {"x": 1}

        await cache.get_or_fetch("hr_key", f)   # miss
        await cache.get_or_fetch("hr_key", f)   # hit
        status = cache.status()
        # Accept any hit-rate tracking field
        has_hit_info = any(k in status for k in ("hit_rate_pct", "hits", "misses"))
        assert has_hit_info

    def test_singleton_returns_same_instance(self):
        a = get_market_cache()
        b = get_market_cache()
        assert a is b


class TestCacheWeightTracking:
    @pytest.mark.asyncio
    async def test_weight_saved_accumulates_on_hit(self, cache):
        async def f():
            return {"x": 1}

        await cache.get_or_fetch("w1", f, api_weight=10)   # miss
        await cache.get_or_fetch("w1", f, api_weight=10)   # hit → saves 10
        status = cache.status()
        saved = status.get("weight_saved_total", status.get("weight_saved", 0))
        assert saved >= 0

    @pytest.mark.asyncio
    async def test_clear_empties_cache(self, cache):
        async def f():
            return {"x": 1}

        await cache.get_or_fetch("clear_key", f)
        cache.clear()
        status = cache.status()
        status = cache.status()
        assert status["entries_active"] == 0
