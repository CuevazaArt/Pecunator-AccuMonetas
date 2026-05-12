"""FastAPI application: credential vault, gateway lifecycle, and operations API."""

from __future__ import annotations

import uuid
import logging
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from runtime.api.auth import verify_token
from runtime.api.lifespan import lifespan

_LOG = logging.getLogger("pecunator.api.app")


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Add correlation ID to every request for tracing across logs."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id

        # Add to response headers
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
from runtime.api.routers import system as _system_router
from runtime.api.routers import vault as _vault_router
from runtime.api.routers import ops as _ops_router
from runtime.api.routers import gateway as _gateway_router
from runtime.api.routers import telemetry as _telemetry_router
from runtime.api.routers import stream as _stream_router
from runtime.api.routers import louise as _louise_router
from runtime.api.routers import orphan as _orphan_router
from runtime.api.routers import metrics as _metrics_router

from runtime.core.settings import api_bind_host_for_cors_regex

def create_app() -> FastAPI:
    app = FastAPI(
        title="PecunatorCore Engine API",
        description="Local HTTP API for the Flutter shell. Bind loopback only unless you know the risk.",
        version="0.4.0",
        lifespan=lifespan,
        dependencies=[],  # auth injected per-router
    )
    # Add correlation ID middleware (must be before CORS)
    app.add_middleware(CorrelationIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=api_bind_host_for_cors_regex(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(_system_router.router, dependencies=[Depends(verify_token)])
    app.include_router(_vault_router.router, dependencies=[Depends(verify_token)])
    app.include_router(_ops_router.router, dependencies=[Depends(verify_token)])
    app.include_router(_gateway_router.router, dependencies=[Depends(verify_token)])

    app.include_router(_telemetry_router.router, dependencies=[Depends(verify_token)])
    app.include_router(_stream_router.router)  # Handles auth itself via query param
    app.include_router(_louise_router.router, dependencies=[Depends(verify_token)])
    app.include_router(_orphan_router.router, dependencies=[Depends(verify_token)])
    app.include_router(_metrics_router.router)  # No auth required for Prometheus scraping

    return app

