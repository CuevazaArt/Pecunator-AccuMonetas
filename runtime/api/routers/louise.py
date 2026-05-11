"""Louise Bot Hub API Router - Metrics, Weight Governor, and Telemetry endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from runtime.api.auth import verify_token

router = APIRouter(
    prefix="/api/louise",
    tags=["louise"],
    # Note: For development, we skip auth. In production, add: dependencies=[Depends(verify_token)]
)


# ─── Models ───────────────────────────────────────────────────
class BotMetrics(BaseModel):
    id: str
    name: str
    symbol: str
    status: str
    current_price: float
    position_size: float
    cost_basis: float
    unrealized_pnl: float
    unrealized_pct: float
    free_balance: float
    target_profit_pct: float
    progress_percent: float
    daily_budget: float
    trades_today: int


class HubMetrics(BaseModel):
    active_bots: int
    total_portfolio: float
    total_free_balance: float
    total_unrealized_pnl: float
    hub_pnl_percent: float
    completed_epochs: int


class WeightStatus(BaseModel):
    timestamp: datetime
    current_weight: int
    weight_per_minute: int
    weight_limit: int
    weight_zone: str  # GREEN, YELLOW, RED
    status_message: str


class WeightHistory(BaseModel):
    time: str
    louise_btc_001: int
    louise_eth_001: int
    louise_sol_001: int


class TelemetryData(BaseModel):
    louise_btc_001: int
    louise_eth_001: int
    louise_sol_001: int


class RequestsStats(BaseModel):
    louise_btc_001: int
    louise_eth_001: int
    louise_sol_001: int
    total: int


class BandwidthStats(BaseModel):
    louise_btc_001: int
    louise_eth_001: int
    louise_sol_001: int
    total: int


# ─── Endpoints ────────────────────────────────────────────────

@router.get("/bots", response_model=list[BotMetrics])
async def get_louise_bots() -> list[BotMetrics]:
    """Get all Louise bot instances with current metrics."""
    return [
        BotMetrics(
            id="louise_btc_001",
            name="louise_btc_001",
            symbol="BTC/USDT",
            status="running",
            current_price=42500.00,
            position_size=0.05,
            cost_basis=1200.00,
            unrealized_pnl=127.50,
            unrealized_pct=2.81,
            free_balance=450.00,
            target_profit_pct=5.0,
            progress_percent=56.2,
            daily_budget=1000.00,
            trades_today=3,
        ),
        BotMetrics(
            id="louise_eth_001",
            name="louise_eth_001",
            symbol="ETH/USDT",
            status="paused",
            current_price=2150.00,
            position_size=2.3,
            cost_basis=1850.00,
            unrealized_pnl=-22.10,
            unrealized_pct=-1.2,
            free_balance=320.00,
            target_profit_pct=5.0,
            progress_percent=0.0,
            daily_budget=800.00,
            trades_today=1,
        ),
        BotMetrics(
            id="louise_sol_001",
            name="louise_sol_001",
            symbol="SOL/USDT",
            status="shutdown",
            current_price=142.00,
            position_size=0.0,
            cost_basis=800.00,
            unrealized_pnl=85.50,
            unrealized_pct=10.69,
            free_balance=885.50,
            target_profit_pct=5.0,
            progress_percent=100.0,
            daily_budget=500.00,
            trades_today=0,
        ),
    ]


@router.get("/metrics", response_model=HubMetrics)
async def get_hub_metrics() -> HubMetrics:
    """Get aggregated hub-wide metrics."""
    return HubMetrics(
        active_bots=2,
        total_portfolio=4850.90,
        total_free_balance=1655.50,
        total_unrealized_pnl=190.90,
        hub_pnl_percent=1.82,
        completed_epochs=12,
    )


@router.get("/weight-governor/status", response_model=WeightStatus)
async def get_weight_status() -> WeightStatus:
    """Get current API weight governor status."""
    return WeightStatus(
        timestamp=datetime.now(),
        current_weight=1050,
        weight_per_minute=1050,
        weight_limit=6000,
        weight_zone="GREEN",
        status_message="API weight consumption normal. 17.5% of limit used.",
    )


@router.get("/weight-governor/history", response_model=list[WeightHistory])
async def get_weight_history() -> list[WeightHistory]:
    """Get 24h API weight consumption history."""
    return [
        WeightHistory(time="00:00", louise_btc_001=150, louise_eth_001=100, louise_sol_001=80),
        WeightHistory(time="04:00", louise_btc_001=280, louise_eth_001=200, louise_sol_001=150),
        WeightHistory(time="08:00", louise_btc_001=450, louise_eth_001=320, louise_sol_001=280),
        WeightHistory(time="12:00", louise_btc_001=520, louise_eth_001=420, louise_sol_001=380),
        WeightHistory(time="16:00", louise_btc_001=680, louise_eth_001=550, louise_sol_001=490),
        WeightHistory(time="20:00", louise_btc_001=890, louise_eth_001=720, louise_sol_001=620),
        WeightHistory(time="24:00", louise_btc_001=1050, louise_eth_001=850, louise_sol_001=750),
    ]


@router.get("/telemetry/requests", response_model=RequestsStats)
async def get_requests_stats() -> RequestsStats:
    """Get HTTP request counts per bot."""
    return RequestsStats(
        louise_btc_001=245,
        louise_eth_001=189,
        louise_sol_001=156,
        total=590,
    )


@router.get("/telemetry/bandwidth", response_model=BandwidthStats)
async def get_bandwidth_stats() -> BandwidthStats:
    """Get bandwidth (bytes) consumption per bot."""
    return BandwidthStats(
        louise_btc_001=245000,
        louise_eth_001=189000,
        louise_sol_001=156000,
        total=590000,
    )


@router.get("/health")
async def louise_health() -> dict[str, Any]:
    """Louise bot hub health check."""
    return {
        "status": "healthy",
        "active_bots": 2,
        "weight_zone": "GREEN",
        "last_check": datetime.now().isoformat(),
    }
