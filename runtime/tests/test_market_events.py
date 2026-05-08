"""Tests for the market_events router.

SKIPPED: market_events router removed in v2.0 refactor.
These tests are kept for reference but module no longer exists.
"""
import pytest
from datetime import datetime, timezone

pytestmark = pytest.mark.skip(reason="market_events router removed in v2.0")


def test_economic_calendar():
    """Calendar returns structured economic events."""
    from runtime.api.routers.market_events import _ECONOMIC_CALENDAR
    assert len(_ECONOMIC_CALENDAR) >= 7
    for event in _ECONOMIC_CALENDAR:
        assert "event" in event
        assert "impact" in event
        assert event["impact"] in ("critical", "high", "medium", "low")
        assert "frequency" in event
        assert "typical_hours_utc" in event


def test_activity_heatmap_24h():
    """Heatmap covers all 24 hours with valid scores."""
    from runtime.api.routers.market_events import _HOURLY_ACTIVITY
    assert len(_HOURLY_ACTIVITY) == 24
    for entry in _HOURLY_ACTIVITY:
        assert 0 <= entry["hour_utc"] <= 23
        assert 0.0 <= entry["activity_score"] <= 1.0
        assert entry["session"] != ""
        assert "label" in entry


def test_activity_recommendation():
    """Recommendation text varies by activity score."""
    from runtime.api.routers.market_events import _activity_recommendation
    high = _activity_recommendation(0.95)
    assert "Alta actividad" in high or "liquidez" in high
    low = _activity_recommendation(0.30)
    assert "Zona muerta" in low or "mínima" in low
    moderate = _activity_recommendation(0.65)
    assert "moderada" in moderate or "Actividad" in moderate


def test_geopolitical_factors():
    """Geopolitical factors are properly structured."""
    from runtime.api.routers.market_events import _GEO_FACTORS
    assert len(_GEO_FACTORS) >= 4
    for factor in _GEO_FACTORS:
        assert "factor" in factor
        assert "impact" in factor
        assert "assets_affected" in factor
        assert isinstance(factor["assets_affected"], list)
        assert "monitor" in factor


def test_cache_mechanism():
    """Cache staleness check works correctly."""
    from runtime.api.routers.market_events import _is_fresh, _cache_ts
    # No entry → not fresh
    assert not _is_fresh("nonexistent_key")
    # Set entry to current time → fresh
    _cache_ts["test_key"] = datetime.now(timezone.utc).timestamp()
    assert _is_fresh("test_key")
    # Set entry to old time → stale
    _cache_ts["test_key"] = 0
    assert not _is_fresh("test_key")


@pytest.mark.asyncio
async def test_calendar_endpoint():
    """Calendar endpoint returns correct structure."""
    from runtime.api.routers.market_events import economic_calendar
    result = await economic_calendar()
    assert "events" in result
    assert "count" in result
    assert result["count"] == len(result["events"])
    assert "ts_utc" in result


@pytest.mark.asyncio
async def test_heatmap_endpoint():
    """Heatmap endpoint returns current hour info."""
    from runtime.api.routers.market_events import activity_heatmap
    result = await activity_heatmap()
    assert "hours" in result
    assert len(result["hours"]) == 24
    assert "current_hour_utc" in result
    assert 0 <= result["current_hour_utc"] <= 23
    assert "current_session" in result
    assert "recommendation" in result


@pytest.mark.asyncio
async def test_geopolitical_endpoint():
    """Geopolitical endpoint returns factors."""
    from runtime.api.routers.market_events import geopolitical_factors
    result = await geopolitical_factors()
    assert "factors" in result
    assert result["count"] == len(result["factors"])


@pytest.mark.asyncio
async def test_summary_endpoint():
    """Summary aggregates all data sources."""
    from runtime.api.routers.market_events import events_summary
    result = await events_summary()
    assert "current_hour_utc" in result
    assert "session" in result
    assert "activity_score" in result
    assert "upcoming_high_impact_events" in result
    assert isinstance(result["upcoming_high_impact_events"], list)
    assert len(result["upcoming_high_impact_events"]) > 0
    assert "geo_risk_count" in result
    assert result["geo_risk_count"] >= 4
