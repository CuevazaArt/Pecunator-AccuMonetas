"""Prometheus metrics endpoint for monitoring Louise and API health."""

import logging
from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

_LOG = logging.getLogger("pecunator.api.routers.metrics")

router = APIRouter(prefix="/metrics", tags=["monitoring"])

# ── Louise Bot Metrics ───────────────────────────────────────────────
louise_bots_active = Gauge(
    "louise_bots_active",
    "Number of active Louise bots",
)

louise_epochs_completed_total = Counter(
    "louise_epochs_completed_total",
    "Total completed epochs across all bots",
)

louise_orders_filled_total = Counter(
    "louise_orders_filled_total",
    "Total orders filled across all epochs",
    labelnames=["symbol"],
)

louise_fill_latency_seconds = Histogram(
    "louise_fill_latency_seconds",
    "Order fill latency in seconds",
    buckets=(0.5, 1, 2, 5, 10, 30, 60),
)

louise_pnl_total = Gauge(
    "louise_pnl_total",
    "Total PNL (profit/loss) in USDT across all epochs",
)

# ── API Metrics ──────────────────────────────────────────────────────
api_requests_total = Counter(
    "api_requests_total",
    "Total API requests",
    labelnames=["method", "endpoint", "status"],
)

api_request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "API request duration in seconds",
    labelnames=["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# ── Gateway & WebSocket Metrics ──────────────────────────────────────
websocket_reconnects_total = Counter(
    "websocket_reconnects_total",
    "Total WebSocket reconnection attempts",
)

gateway_uptime_seconds = Gauge(
    "gateway_uptime_seconds",
    "Gateway connection uptime in seconds",
)

# ── Database Metrics ────────────────────────────────────────────────
database_query_duration_seconds = Histogram(
    "database_query_duration_seconds",
    "Database query duration in seconds",
    labelnames=["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1),
)

database_queries_total = Counter(
    "database_queries_total",
    "Total database queries",
    labelnames=["operation", "status"],
)

# ── Risk Control Metrics ────────────────────────────────────────────
api_fuse_trips_total = Counter(
    "api_fuse_trips_total",
    "Total circuit breaker trips",
    labelnames=["reason"],
)

weight_governor_blocks_total = Counter(
    "weight_governor_blocks_total",
    "Total requests blocked by weight governor",
    labelnames=["zone"],
)

budget_guard_blocks_total = Counter(
    "budget_guard_blocks_total",
    "Total orders blocked by budget guard",
    labelnames=["bot_id"],
)

# ── Alerts & Events ─────────────────────────────────────────────────
alert_dispatches_total = Counter(
    "alert_dispatches_total",
    "Total alerts dispatched",
    labelnames=["level", "code"],
)


@router.get("")
async def get_metrics():
    """
    Expose Prometheus metrics in text format.
    No authentication required.
    """
    metrics = generate_latest()
    return Response(content=metrics, media_type=CONTENT_TYPE_LATEST)
