"""Sandbox REST query and curated snapshot routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from runtime.api import deps
from runtime.app import AppContext

router = APIRouter(prefix="/api/v1", tags=["sandbox"])


@router.post("/sandbox/curated/save")
async def sandbox_curated_save(
    payload: dict[str, Any],
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    from runtime.api.app import _sandbox_curated_save
    rec = _sandbox_curated_save(ctx, payload)
    return {"saved": True, "record": rec}


@router.get("/sandbox/curated/list")
async def sandbox_curated_list(
    limit: int = 50,
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    from runtime.api.app import _sandbox_curated_list
    rows = _sandbox_curated_list(ctx, limit=limit)
    return {"items": rows}


@router.get("/sandbox/rest/catalog")
async def sandbox_rest_catalog() -> dict[str, Any]:
    from runtime.api.app import _sandbox_rest_catalog
    return {"items": _sandbox_rest_catalog()}


@router.post("/sandbox/rest/query")
async def sandbox_rest_query(
    body: dict[str, Any],
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    from runtime.api.app import _sandbox_rest_query
    return await _sandbox_rest_query(ctx, body)


# ── Earn ────────────────────────────────────────────────────────────

@router.get("/earn/history/{symbol}")
async def get_earn_history(symbol: str) -> dict[str, Any]:
    earn = deps.get_earn()
    return {"items": earn.get_history(symbol)}


@router.post("/earn/sync")
async def force_earn_sync() -> dict[str, Any]:
    from runtime.api._helpers import resolve_pair
    from binance.client import Client
    earn = deps.get_earn()

    def _client_resolver():
        pk, sk = resolve_pair(deps.get_ctx())
        if pk and sk:
            return Client(pk, sk)
        return None

    res = await earn.force_sync(_client_resolver)
    return res
