"""FastAPI lifespan — start/stop bot services and gateway, with graceful shutdown."""

from __future__ import annotations

import asyncio
import logging
import signal
import sqlite3
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException

from runtime.api import deps
from runtime.api._helpers import resolve_pair, resolve_pair_for_bot
from runtime.app import AppContext
from runtime.connectors.binance_gateway import BinanceGateway
from runtime.core.security_util import sanitize_log_message
from runtime.core.alert_dispatcher import get_alert_dispatcher

_LOG = logging.getLogger("pecunator.api")

# Global shutdown flag
_shutdown_requested: bool = False
_shutdown_start_time: Optional[float] = None
_SHUTDOWN_TIMEOUT_SEC = 30


def set_shutdown_flag():
    """Signal handler for SIGTERM/SIGINT — sets graceful shutdown flag."""
    global _shutdown_requested, _shutdown_start_time
    _shutdown_requested = True
    _shutdown_start_time = time.time()
    _LOG.warning("Graceful shutdown initiated (SIGTERM/SIGINT received)")
    try:
        get_alert_dispatcher().warning(
            "SHUTDOWN_INITIATED",
            "Graceful shutdown initiated. Cancelling pending orders and flushing state...",
            silent=False
        )
    except (ImportError, AttributeError, RuntimeError) as e:
        _LOG.debug("Alert dispatcher unavailable during shutdown: %s", type(e).__name__)


def is_shutdown_requested() -> bool:
    """Check if shutdown was requested."""
    return _shutdown_requested


def get_shutdown_elapsed() -> float:
    """Get seconds elapsed since shutdown request."""
    if not _shutdown_start_time:
        return 0
    return time.time() - _shutdown_start_time


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start Dorothy + Elphaba services, optionally autostart gateway, with graceful shutdown."""
    import os
    global _shutdown_requested, _shutdown_start_time

    # Reset shutdown flags on startup
    _shutdown_requested = False
    _shutdown_start_time = None

    if os.environ.get("PECUNATOR_API_AUTH_DISABLED", "").strip() in ("1", "true"):
        _LOG.critical("⚠️ PECUNATOR_API_AUTH_DISABLED is active! The API is exposed without authentication. DO NOT USE IN PRODUCTION.")

    # Register signal handlers for graceful shutdown (not supported on Windows)
    loop = asyncio.get_event_loop()
    try:
        loop.add_signal_handler(signal.SIGTERM, set_shutdown_flag)
        loop.add_signal_handler(signal.SIGINT, set_shutdown_flag)
        _LOG.info("Signal handlers registered (SIGTERM, SIGINT)")
    except NotImplementedError:
        _LOG.info("Signal handlers not supported on this platform (Windows) — graceful shutdown via Ctrl+C only")

    deps.init_context()
    ctx = deps.get_ctx()
    from runtime.core.bot_coordinator import get_bot_coordinator
    coord = get_bot_coordinator()

    # Bot Coordinator now manages Louise bots implicitly or via explicit poll
    coord.start_launcher()

    await autostart_gateway_if_possible(ctx)

    # ── Start centralized telemetry collector ──────────────────────
    try:
        from runtime.core.telemetry_collector import get_telemetry_collector
        _tc = get_telemetry_collector(ctx.config.data_dir)
        await _tc.start(ctx)
    except (ImportError, AttributeError, FileNotFoundError, OSError) as e:
        _LOG.warning("telemetry_collector startup failed (type=%s): %s", type(e).__name__, sanitize_log_message(str(e)))

    # ── Start Louise Immortality ───────────────────────────────────
    from runtime.api.louise_service import get_louise_service
    await get_louise_service().start_immortality()

    yield

    # ── Graceful Shutdown ──────────────────────────────────────────
    _LOG.info("Starting graceful shutdown sequence...")
    shutdown_start = time.time()

    # Step 1: Stop Louise immortality loop (stops creating new bot tasks)
    try:
        from runtime.api.louise_service import get_louise_service
        _LOG.info("Stopping Louise immortality...")
        await get_louise_service().stop_immortality()
    except Exception as e:
        _LOG.error("Louise immortality stop error: %s", e)

    # Step 2: Cancel pending orders in all bot runners
    try:
        from runtime.api.louise_service import get_louise_service
        louise_svc = get_louise_service()
        for bot_id, runner in list(louise_svc.runners.items()):
            if runner.pending_orders:
                _LOG.info("Cancelling %d pending orders for %s", len(runner.pending_orders), bot_id)
                for client_oid, meta in list(runner.pending_orders.items()):
                    try:
                        symbol = runner.config.get("symbol", "UNKNOWN")
                        if runner.gateway and getattr(runner.gateway, "_client", None):
                            # Cancel order on exchange
                            await runner.gateway._client.cancel_order(symbol=symbol, origClientOrderId=client_oid)
                            _LOG.info("Cancelled order %s on %s", client_oid, symbol)
                    except (OSError, TimeoutError, RuntimeError, AttributeError) as e:
                        _LOG.warning("Failed to cancel order %s (type=%s): %s", client_oid, type(e).__name__, sanitize_log_message(str(e)))
    except (ImportError, AttributeError, RuntimeError) as e:
        _LOG.error("Error during pending order cancellation (type=%s): %s", type(e).__name__, sanitize_log_message(str(e)))

    # Step 3: Stop telemetry collector
    try:
        from runtime.core.telemetry_collector import get_telemetry_collector
        _LOG.info("Stopping telemetry collector...")
        await get_telemetry_collector().stop()
    except (ImportError, AttributeError, RuntimeError, OSError) as e:
        _LOG.error("Telemetry stop error (type=%s): %s", type(e).__name__, sanitize_log_message(str(e)))

    # Step 4: Stop gateway
    ctx = deps.peek_ctx()
    if ctx and ctx.gateway:
        try:
            _LOG.info("Stopping gateway...")
            await ctx.gateway.stop()
        except (OSError, RuntimeError, TimeoutError, AttributeError) as e:
            _LOG.warning("Gateway stop error (type=%s): %s", type(e).__name__, sanitize_log_message(str(e)))
        ctx.gateway = None

    # Step 5: Stop bot coordinator
    try:
        from runtime.core.bot_coordinator import get_bot_coordinator
        _LOG.info("Stopping bot coordinator...")
        await get_bot_coordinator().stop_launcher()
    except (ImportError, AttributeError, RuntimeError, OSError) as e:
        _LOG.error("Bot coordinator stop error (type=%s): %s", type(e).__name__, sanitize_log_message(str(e)))

    # Step 6: Flush database state (Louise)
    try:
        from runtime.core.louise_db import LouiseDB
        db = LouiseDB()
        _LOG.info("Flushing Louise database state...")
        # Database context managers auto-commit, no explicit action needed
    except (ImportError, OSError, sqlite3.DatabaseError) as e:
        _LOG.error("Database flush error (type=%s): %s", type(e).__name__, sanitize_log_message(str(e)))

    elapsed = time.time() - shutdown_start
    _LOG.info("Graceful shutdown complete in %.2fs", elapsed)

    if elapsed > _SHUTDOWN_TIMEOUT_SEC:
        _LOG.critical("SHUTDOWN EXCEEDED TIMEOUT (%ds)! Forcing exit.", _SHUTDOWN_TIMEOUT_SEC)
        get_alert_dispatcher().critical(
            "SHUTDOWN_TIMEOUT_EXCEEDED",
            f"Graceful shutdown took {elapsed:.1f}s, exceeding {_SHUTDOWN_TIMEOUT_SEC}s timeout",
            silent=False
        )


async def autostart_gateway_if_possible(ctx: AppContext) -> None:
    """Try to connect the Binance gateway on startup if credentials are available."""
    from runtime.core.settings import gateway_autostart_enabled
    if ctx.gateway is not None:
        return
    if not gateway_autostart_enabled():
        _LOG.info("Gateway auto-start DISABLED (gateway_settings.json autostart_gateway=false)")
        return
    try:
        pair = resolve_pair(ctx)
    except HTTPException:
        pair = None
    except (KeyError, ValueError, AttributeError, OSError) as e:
        _LOG.warning("Gateway auto-start resolve skipped (type=%s): %s", type(e).__name__, sanitize_log_message(str(e)))
        pair = None
    if not pair:
        _LOG.info("Gateway auto-start skipped: no credentials resolved")
        return
    gw = BinanceGateway(pair[0], pair[1], ctx.bus, ctx.state, ctx.log_line, ctx.config.data_dir)
    try:
        await gw.start()
        await gw.sync_time()
        await gw.fetch_account()
        await gw.refresh_equity(force_tickers=True)
        ctx.gateway = gw
        ctx.state.last_error = None
        _LOG.info("Gateway auto-started on API startup")
    except (OSError, TimeoutError, RuntimeError, ConnectionError) as e:
        try:
            await gw.stop()
        except (OSError, RuntimeError, TimeoutError):
            pass
        ctx.state.last_error = sanitize_log_message(str(e))
        _LOG.warning("Gateway auto-start failed (type=%s): %s", type(e).__name__, ctx.state.last_error)
