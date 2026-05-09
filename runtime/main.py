"""CLI entry: optional HTTP API (FastAPI + Uvicorn) for the Flutter shell."""

from __future__ import annotations

import logging
import os
import sys


def _configure_logging() -> None:
    level_name = os.environ.get("PECUNATOR_LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = os.environ.get(
        "PECUNATOR_LOG_FMT",
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    datefmt = os.environ.get("PECUNATOR_LOG_DATEFMT", "%Y-%m-%d %H:%M:%S")

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    # M1: Log rotation — 5MB × 3 backups = 15MB ceiling
    try:
        from logging.handlers import RotatingFileHandler
        log_path = os.path.join(os.path.dirname(__file__), "..", "backend.log")
        log_path = os.path.abspath(log_path)
        rh = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        rh.setLevel(level)
        rh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
        handlers.append(rh)
    except Exception:
        pass  # File handler optional — stdout always works

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
        force=True,
    )

    # M1.1: Silence polling noise
    if os.environ.get("PECUNATOR_ACCESS_LOGS") != "1":
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

def main() -> None:
    _configure_logging()
    lo = logging.getLogger("pecunator.engine")

    # ── AutoPilot mode: full autonomous operation ──
    if "--autopilot" in sys.argv or os.environ.get("PECUNATOR_AUTOPILOT", "").strip().lower() in ("1", "true"):
        lo.info("Starting in AUTOPILOT mode (full autonomous)")
        from runtime.core.autopilot import run_autopilot
        run_autopilot()
        return

    if os.environ.get("PECUNATOR_ENGINE_STUB", "").strip().lower() in ("1", "true", "yes"):
        lo.info(
            "PECUNATOR_ENGINE_STUB set: engine exits without HTTP API. "
            "Unset to start the API (default host 127.0.0.1:8000).",
        )
        return
    import uvicorn

    from runtime.api.app import create_app
    from runtime.core.settings import api_bind_host, api_bind_port

    host = api_bind_host()
    port = api_bind_port()
    lo.info("Starting engine HTTP API at http://%s:%s (docs /docs)", host, port)
    uvicorn.run(
        create_app(),
        host=host,
        port=port,
        log_level=os.environ.get("UVICORN_LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
