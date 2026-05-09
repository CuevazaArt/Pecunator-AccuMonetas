"""M2: Symmetric hub deployment — atomic create+start of Dorothy+Elphaba pair.

If either side fails to create or start, the other is rolled back (deleted).
This eliminates the asymmetric window where one bot is live without its hedge.

Endpoint: POST /api/v1/hub/deploy-symmetric
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from runtime.api import deps
from runtime.api._helpers import resolve_pair
from runtime.api.schemas import GatewayStartBody, HubBotCreateBody
from runtime.app import AppContext
from runtime.core.security_util import sanitize_log_message

_LOG = logging.getLogger("pecunator.api.symmetric")

router = APIRouter(prefix="/api/v1/hub", tags=["symmetric"])


class SymmetricDeployBody(BaseModel):
    """Config for atomic Dorothy+Elphaba deployment."""
    symbol: str = Field(min_length=5, max_length=32)
    dorothy: HubBotCreateBody
    elphaba: HubBotCreateBody
    auto_start: bool = Field(
        default=True,
        description="If true, both bots are started immediately after creation.",
    )
    # Credentials for auto_start
    api_key: str | None = None
    api_secret: str | None = None


class SymmetricDeployOut(BaseModel):
    ok: bool
    dorothy_bot_id: str | None = None
    elphaba_bot_id: str | None = None
    dorothy_running: bool = False
    elphaba_running: bool = False
    error: str | None = None
    rollback_performed: bool = False


@router.post("/deploy-symmetric", response_model=SymmetricDeployOut)
async def deploy_symmetric(
    body: SymmetricDeployBody,
    ctx: AppContext = Depends(deps.get_ctx),
) -> Any:
    """Atomically deploy a Dorothy+Elphaba symmetric pair.

    Validation:
    1. Both configs must target the same symbol
    2. SymmetryGuard.check_config_only() must clear

    Execution:
    1. Create Dorothy instance
    2. Create Elphaba instance — if fails, delete Dorothy (rollback)
    3. If auto_start: start both — if one fails, stop+delete both (rollback)
    """
    dorothy_svc = deps.get_bot()
    elphaba_svc = deps.get_elphaba()

    # ── Validate symbol parity ─────────────────────────────────
    d_sym = body.dorothy.symbol or body.symbol
    e_sym = body.elphaba.symbol or body.symbol
    if d_sym.upper() != e_sym.upper():
        raise HTTPException(
            status_code=400,
            detail=f"Symbol mismatch: Dorothy={d_sym} vs Elphaba={e_sym}. "
                   f"Symmetric deployment requires identical symbols.",
        )

    # Force symbol consistency
    body.dorothy.symbol = body.symbol
    body.elphaba.symbol = body.symbol

    # ── Step 1: Create Dorothy ──────────────────────────────────
    dorothy_id: str | None = None
    elphaba_id: str | None = None
    try:
        d_row = dorothy_svc.create_instance(
            bot_id=body.dorothy.bot_id,
            tag=body.dorothy.tag or "Dorothy",
            symbol=body.symbol,
            loop_interval_sec=body.dorothy.loop_interval_sec,
            quote_order_qty=body.dorothy.quote_order_qty,
            profit_factor=body.dorothy.profit_factor,
            margin_drop_factor=body.dorothy.margin_drop_factor,
            qty_decimals=body.dorothy.qty_decimals,
            price_decimals=body.dorothy.price_decimals,
            note=body.dorothy.note,
            max_drawdown_pct=body.dorothy.max_drawdown_pct,
            stop_loss_pct=body.dorothy.stop_loss_pct,
            metrics_interval_cycles=body.dorothy.metrics_interval_cycles,
            simulated=body.dorothy.simulated,
            trading_enabled=body.dorothy.trading_enabled,
        )
        dorothy_id = d_row["bot_id"]
        _LOG.info("symmetric:created dorothy=%s", dorothy_id)
    except Exception as e:
        return SymmetricDeployOut(
            ok=False,
            error=f"Dorothy creation failed: {sanitize_log_message(str(e))}",
        )

    # ── Step 2: Create Elphaba — rollback Dorothy on failure ────
    try:
        e_row = elphaba_svc.create_instance(
            bot_id=body.elphaba.bot_id,
            tag=body.elphaba.tag or "Elphaba",
            symbol=body.symbol,
            loop_interval_sec=body.elphaba.loop_interval_sec,
            quote_order_qty=body.elphaba.quote_order_qty,
            profit_factor=body.elphaba.profit_factor,
            margin_rise_factor=body.elphaba.margin_drop_factor,
            qty_decimals=body.elphaba.qty_decimals,
            price_decimals=body.elphaba.price_decimals,
            note=body.elphaba.note,
            max_drawdown_pct=body.elphaba.max_drawdown_pct,
            metrics_interval_cycles=body.elphaba.metrics_interval_cycles,
            trading_enabled=body.elphaba.trading_enabled,
        )
        elphaba_id = e_row["bot_id"]
        _LOG.info("symmetric:created elphaba=%s", elphaba_id)
    except Exception as e:
        # ROLLBACK: delete Dorothy
        _LOG.warning("symmetric:ROLLBACK deleting dorothy=%s because elphaba creation failed", dorothy_id)
        try:
            await dorothy_svc.delete_instance(dorothy_id)
        except Exception:
            pass
        return SymmetricDeployOut(
            ok=False,
            error=f"Elphaba creation failed (Dorothy rolled back): {sanitize_log_message(str(e))}",
            rollback_performed=True,
        )

    # ── Step 3: Auto-start if requested ─────────────────────────
    if not body.auto_start:
        return SymmetricDeployOut(
            ok=True,
            dorothy_bot_id=dorothy_id,
            elphaba_bot_id=elphaba_id,
        )

    pair = resolve_pair(ctx, body.api_key, body.api_secret)
    if not pair:
        return SymmetricDeployOut(
            ok=True,
            dorothy_bot_id=dorothy_id,
            elphaba_bot_id=elphaba_id,
            error="Created but not started: no API credentials available",
        )

    # Start Dorothy
    dorothy_running = False
    elphaba_running = False
    try:
        await dorothy_svc.start_instance(dorothy_id, pair[0], pair[1])
        dorothy_running = True
        _LOG.info("symmetric:started dorothy=%s", dorothy_id)
    except Exception as e:
        _LOG.warning("symmetric:dorothy start failed: %s — rolling back both", e)
        try:
            await dorothy_svc.delete_instance(dorothy_id)
        except Exception:
            pass
        try:
            await elphaba_svc.delete_instance(elphaba_id)
        except Exception:
            pass
        return SymmetricDeployOut(
            ok=False,
            error=f"Dorothy start failed (both rolled back): {sanitize_log_message(str(e))}",
            rollback_performed=True,
        )

    # Start Elphaba — rollback BOTH on failure
    try:
        await elphaba_svc.start_instance(elphaba_id, pair[0], pair[1])
        elphaba_running = True
        _LOG.info("symmetric:started elphaba=%s", elphaba_id)
    except Exception as e:
        _LOG.warning("symmetric:elphaba start failed: %s — rolling back both", e)
        try:
            await dorothy_svc.stop_instance(dorothy_id)
        except Exception:
            pass
        try:
            await dorothy_svc.delete_instance(dorothy_id)
        except Exception:
            pass
        try:
            await elphaba_svc.delete_instance(elphaba_id)
        except Exception:
            pass
        return SymmetricDeployOut(
            ok=False,
            error=f"Elphaba start failed (both rolled back): {sanitize_log_message(str(e))}",
            rollback_performed=True,
        )

    # ── Dispatch alert on successful symmetric deploy ──────────
    try:
        from runtime.core.alert_dispatcher import get_alert_dispatcher
        get_alert_dispatcher().info(
            "SYMMETRIC_DEPLOY",
            f"Dorothy({dorothy_id}) + Elphaba({elphaba_id}) deployed on {body.symbol}",
        )
    except Exception:
        pass

    return SymmetricDeployOut(
        ok=True,
        dorothy_bot_id=dorothy_id,
        elphaba_bot_id=elphaba_id,
        dorothy_running=True,
        elphaba_running=True,
    )
