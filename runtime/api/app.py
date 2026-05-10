"""FastAPI application: credential vault, gateway lifecycle, and operations API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from runtime.api.auth import verify_token
from runtime.api.lifespan import lifespan
from runtime.api.routers import system as _system_router
from runtime.api.routers import vault as _vault_router
from runtime.api.routers import ops as _ops_router
from runtime.api.routers import dorothy as _dorothy_router
from runtime.api.routers import gateway as _gateway_router
from runtime.api.routers import prospector as _prospector_router
from runtime.api.routers import elphaba as _elphaba_router
from runtime.api.routers import symmetric as _symmetric_router

from runtime.core.settings import api_bind_host_for_cors_regex

def create_app() -> FastAPI:
    app = FastAPI(
        title="PecunatorCore Engine API",
        description="Local HTTP API for the Flutter shell. Bind loopback only unless you know the risk.",
        version="0.4.0",
        lifespan=lifespan,
        dependencies=[],  # auth injected per-router below
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=api_bind_host_for_cors_regex(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers (all protected by bearer token) ──────────────────────
    app.include_router(_system_router.router)
    app.include_router(_vault_router.router)
    app.include_router(_ops_router.router)
    app.include_router(_dorothy_router.router)
    app.include_router(_gateway_router.router)
    app.include_router(_prospector_router.router)
    app.include_router(_elphaba_router.router)
    app.include_router(_symmetric_router.router)

    return app

