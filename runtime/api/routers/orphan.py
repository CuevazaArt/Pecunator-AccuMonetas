"""API router for orphan order detection and reconciliation."""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, Depends

from runtime.api.deps import get_ctx
from runtime.app import AppContext
from runtime.tools.orphan_reconciler import OrphanReconciler

_LOG = logging.getLogger("pecunator.api.routers.orphan")

router = APIRouter(prefix="/api/louise/orphans", tags=["louise"])


@router.get("/scan", tags=["louise"])
async def scan_orphans(symbol: str = "BTCUSDT", ctx: AppContext = Depends(get_ctx)):
    """
    Scan for orphaned orders (exist in Binance but not in Louise DB).
    Returns list of orphaned orders with details.
    """
    if not ctx.gateway or not ctx.gateway._client:
        raise HTTPException(
            status_code=503,
            detail="Gateway not connected",
        )

    try:
        reconciler = OrphanReconciler(ctx.db, ctx.gateway)
        orphans = await reconciler.scan_orphans(symbol=symbol)

        return {
            "symbol": symbol,
            "orphan_count": len(orphans),
            "orphans": [o.to_dict() for o in orphans],
        }
    except Exception as e:
        _LOG.error("Orphan scan failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Orphan scan failed: {str(e)}",
        )


@router.post("/adopt", tags=["louise"])
async def adopt_orphan(
    order_id: str,
    bot_id: str,
    epoch_id: str,
    ctx: AppContext = Depends(get_ctx),
):
    """
    Adopt an orphaned order by inserting it into Louise DB.
    Associates the order with a specific bot and epoch.
    """
    if not ctx.gateway or not ctx.gateway._client:
        raise HTTPException(
            status_code=503,
            detail="Gateway not connected",
        )

    try:
        reconciler = OrphanReconciler(ctx.db, ctx.gateway)

        # Find the orphan by order_id (re-scan to get fresh data)
        symbol = "BTCUSDT"  # TODO: parameterize symbol
        orphans = await reconciler.scan_orphans(symbol=symbol)
        orphan = next((o for o in orphans if o.order_id == order_id), None)

        if not orphan:
            raise HTTPException(
                status_code=404,
                detail=f"Orphan order {order_id} not found",
            )

        success = await reconciler.adopt_orphan(orphan, bot_id, epoch_id)
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to adopt order {order_id}",
            )

        return {
            "status": "adopted",
            "order_id": order_id,
            "bot_id": bot_id,
            "epoch_id": epoch_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        _LOG.error("Adoption failed for order %s: %s", order_id, e)
        raise HTTPException(
            status_code=500,
            detail=f"Adoption failed: {str(e)}",
        )


@router.post("/cancel", tags=["louise"])
async def cancel_orphan(
    order_id: str,
    symbol: str = "BTCUSDT",
    ctx: AppContext = Depends(get_ctx),
):
    """
    Cancel an orphaned order on Binance (if still open).
    Does not affect Louise DB.
    """
    if not ctx.gateway or not ctx.gateway._client:
        raise HTTPException(
            status_code=503,
            detail="Gateway not connected",
        )

    try:
        reconciler = OrphanReconciler(ctx.db, ctx.gateway)

        # Find the orphan to get full details
        orphans = await reconciler.scan_orphans(symbol=symbol)
        orphan = next((o for o in orphans if o.order_id == order_id), None)

        if not orphan:
            raise HTTPException(
                status_code=404,
                detail=f"Orphan order {order_id} not found",
            )

        success = await reconciler.cancel_orphan(orphan)
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to cancel order {order_id}",
            )

        return {
            "status": "cancelled",
            "order_id": order_id,
            "symbol": symbol,
        }
    except HTTPException:
        raise
    except Exception as e:
        _LOG.error("Cancel failed for order %s: %s", order_id, e)
        raise HTTPException(
            status_code=500,
            detail=f"Cancel failed: {str(e)}",
        )
