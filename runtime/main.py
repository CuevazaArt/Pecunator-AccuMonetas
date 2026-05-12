"""CLI entry: optional HTTP API (FastAPI + Uvicorn) for the Flutter shell."""

from __future__ import annotations

import logging
import os
import sys


def _configure_logging() -> None:
    level_name = os.environ.get("PECUNATOR_LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    use_json = os.environ.get("PECUNATOR_LOG_JSON", "").strip().lower() in ("1", "true", "yes")

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if use_json:
        try:
            from pythonjsonlogger import jsonlogger

            # JSON formatter for stdout
            json_formatter = jsonlogger.JsonFormatter(
                fmt="%(timestamp)s %(level)s %(name)s %(message)s %(correlation_id)s",
                timestamp=True,
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
            handlers[0].setFormatter(json_formatter)
        except ImportError:
            print("[WARN] python-json-logger not installed, using text format", file=sys.stderr)
            fmt = os.environ.get(
                "PECUNATOR_LOG_FMT",
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            )
            datefmt = os.environ.get("PECUNATOR_LOG_DATEFMT", "%Y-%m-%d %H:%M:%S")
            handlers[0].setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    else:
        fmt = os.environ.get(
            "PECUNATOR_LOG_FMT",
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        datefmt = os.environ.get("PECUNATOR_LOG_DATEFMT", "%Y-%m-%d %H:%M:%S")
        handlers[0].setFormatter(logging.Formatter(fmt, datefmt=datefmt))

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
        if use_json:
            try:
                from pythonjsonlogger import jsonlogger
                json_formatter = jsonlogger.JsonFormatter(
                    fmt="%(timestamp)s %(level)s %(name)s %(message)s %(correlation_id)s",
                    timestamp=True,
                    datefmt="%Y-%m-%dT%H:%M:%S%z",
                )
                rh.setFormatter(json_formatter)
            except ImportError:
                pass
        else:
            rh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
        handlers.append(rh)
    except Exception as exc:
        # Log to stderr so operator is aware file-logging is unavailable
        print(f"[WARN] RotatingFileHandler unavailable ({exc}), using stdout only", file=sys.stderr)

    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True,
    )

    # M1.1: Silence polling noise
    if os.environ.get("PECUNATOR_ACCESS_LOGS") != "1":
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)




def main() -> None:
    _configure_logging()
    lo = logging.getLogger("pecunator.engine")



    # NOTE: --autopilot mode was removed in v3.1.x.
    # Autonomous operation is handled by the Dorothy/Elphaba symmetric hub loop
    # with ApiFuse, SymmetryGuard, and TrendSignal as active governors.

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

    # ── Reload mode: auto-reload on file changes in dev ────────
    use_reload = os.environ.get("PECUNATOR_RELOAD", "").strip().lower() in ("1", "true", "yes")

    lo.info("Starting engine HTTP API at http://%s:%s (docs /docs)%s",
            host, port, " [RELOAD ON]" if use_reload else "")

    if use_reload:
        # Reload mode requires app as import string, not factory
        uvicorn.run(
            "runtime.api.app:create_app",
            factory=True,
            host=host,
            port=port,
            log_level=os.environ.get("UVICORN_LOG_LEVEL", "info").lower(),
            log_config=None,
            reload=True,
            reload_dirs=[os.path.dirname(__file__)],
        )
    else:
        uvicorn.run(
            create_app(),
            host=host,
            port=port,
            log_level=os.environ.get("UVICORN_LOG_LEVEL", "info").lower(),
            log_config=None,
        )

if __name__ == "__main__":
    main()
