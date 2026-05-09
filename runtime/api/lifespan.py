"""FastAPI lifespan — start/stop bot services and gateway."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException

from runtime.api import deps
from runtime.api._helpers import resolve_pair
from runtime.app import AppContext
from runtime.connectors.binance_gateway import BinanceGateway
from runtime.core.security_util import sanitize_log_message

_LOG = logging.getLogger("pecunator.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start Dorothy + Elphaba services, optionally autostart gateway."""
    deps.init_context()
    ctx = deps.get_ctx()
    bot = deps.get_bot()
    elphaba = deps.get_elphaba()
    credential_resolver = lambda: resolve_pair(ctx)  # noqa: E731
    bot.start_immortality(credential_resolver, interval_sec=5.0)
    elphaba.start_immortality(credential_resolver, interval_sec=5.0)
    await autostart_gateway_if_possible(ctx)
    yield
    ctx = deps.peek_ctx()
    bot = deps.get_bot()
    elphaba = deps.get_elphaba()
    await bot.stop_immortality()
    await elphaba.stop_immortality()
    await bot.stop_all()
    await elphaba.stop_all()
    if ctx and ctx.gateway:
        try:
            await ctx.gateway.stop()
        except Exception as e:
            _LOG.warning("gateway stop on shutdown: %s", e)
        ctx.gateway = None


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
    except Exception as e:
        _LOG.warning("Gateway auto-start resolve skipped: %s", sanitize_log_message(str(e)))
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
    except Exception as e:
        try:
            await gw.stop()
        except Exception:
            pass
        ctx.state.last_error = sanitize_log_message(str(e))
        _LOG.warning("Gateway auto-start failed: %s", ctx.state.last_error)
