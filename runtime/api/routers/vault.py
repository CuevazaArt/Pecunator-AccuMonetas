"""Vault and credential management routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from runtime.api import deps
from runtime.api._helpers import mask_pk, pk_last4
from runtime.api.schemas import (
    ActiveCredentialOut,
    VaultCredentialLabelBody,
    VaultCredentialUpsertBody,
    VaultStatusOut,
)
from runtime.app import AppContext
from runtime.core.settings import binance_credentials_from_env

router = APIRouter(prefix="/api/v1", tags=["vault"])


@router.get("/vault/status", response_model=VaultStatusOut)
async def vault_status(ctx: AppContext = Depends(deps.get_ctx)) -> Any:
    pubs = ctx.config.list_public_credentials()
    return VaultStatusOut(
        vault_file_exists=ctx.config.exists(),
        credential_rows=len(pubs),
        active_credential_id=ctx.config.get_active_credential_id(),
    )


@router.get("/vault/credentials")
async def vault_credentials(
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, list[dict[str, str]]]:
    return {
        "items": [
            {
                "id": p["id"],
                "public_key": p["public_key"],
                "public_key_short": mask_pk(p["public_key"]),
                "label": p.get("label", ""),
            }
            for p in ctx.config.list_public_credentials()
        ]
    }


@router.post("/vault/credentials")
async def vault_credentials_add(
    body: VaultCredentialUpsertBody,
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    try:
        cid, updated = ctx.config.add_credential(
            body.api_key,
            body.api_secret,
            label=body.label or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from None
    pubs = ctx.config.list_public_credentials()
    row = next((p for p in pubs if p.get("id") == cid), None)
    ctx.active_api_key_hint = mask_pk(body.api_key)
    ctx.active_api_key_last4 = pk_last4(body.api_key)
    ctx.active_api_key_source = "vault"
    return {
        "id": cid,
        "updated_existing": bool(updated),
        "label": (row or {}).get("label", body.label or ""),
    }


@router.patch("/vault/credentials/{credential_id}")
async def vault_credentials_update_label(
    credential_id: str,
    body: VaultCredentialLabelBody,
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    ok = ctx.config.update_credential_label(credential_id, body.label or "")
    if not ok:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"updated": True}


@router.delete("/vault/credentials/{credential_id}")
async def vault_credentials_delete(
    credential_id: str,
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    prev_active = ctx.config.get_active_credential_id()
    try:
        ok = ctx.config.remove_credential(credential_id)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from None
    if not ok:
        raise HTTPException(status_code=404, detail="Credential not found")
    if prev_active == credential_id:
        ctx.active_api_key_hint = None
        ctx.active_api_key_last4 = None
        ctx.active_api_key_source = None
    return {"deleted": True}


@router.post("/vault/credentials/{credential_id}/delete")
async def vault_credentials_delete_compat(
    credential_id: str,
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    return await vault_credentials_delete(credential_id, ctx)


@router.get("/credentials/active", response_model=ActiveCredentialOut)
async def active_credential(ctx: AppContext = Depends(deps.get_ctx)) -> Any:
    active_id = ctx.config.get_active_credential_id()
    pubs = ctx.config.list_public_credentials()
    active_pub = next((p for p in pubs if p.get("id") == active_id), None)
    active_label = (active_pub or {}).get("label", "") or None
    if (
        ctx.active_api_key_source == "vault"
        and active_id
        and active_pub is None
    ):
        ctx.active_api_key_hint = None
        ctx.active_api_key_last4 = None
        ctx.active_api_key_source = None
    if ctx.active_api_key_hint:
        return ActiveCredentialOut(
            source=ctx.active_api_key_source or "runtime",
            public_key_hint=ctx.active_api_key_hint,
            public_key_last4=ctx.active_api_key_last4 or pk_last4(ctx.active_api_key_hint),
            active_credential_id=active_id,
            label=active_label,
        )
    env_pair = binance_credentials_from_env()
    if env_pair:
        return ActiveCredentialOut(
            source="env",
            public_key_hint=mask_pk(env_pair[0]),
            public_key_last4=pk_last4(env_pair[0]),
            active_credential_id=active_id,
            label=active_label,
        )
    try:
        pair = ctx.config.get_pair_for_active()
    except ValueError:
        pair = None
    if pair:
        return ActiveCredentialOut(
            source="vault",
            public_key_hint=mask_pk(pair[0]),
            public_key_last4=pk_last4(pair[0]),
            active_credential_id=active_id,
            label=active_label,
        )
    return ActiveCredentialOut(
        source="none",
        public_key_hint="-",
        public_key_last4="-",
        active_credential_id=active_id,
        label=active_label,
    )
