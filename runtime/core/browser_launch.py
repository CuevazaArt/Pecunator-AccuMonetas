"""Print dashboard URL and open the default browser in a reliable way."""

from __future__ import annotations

import os
import sys
import time
import webbrowser

from nicegui import helpers


def public_browser_host(bind_host: str) -> str:
    """Host shown in URLs when the server binds on all interfaces."""
    if bind_host in ("0.0.0.0", "::", "0::0"):
        return "127.0.0.1"
    return bind_host


def dashboard_url(bind_host: str, port: int) -> str:
    h = public_browser_host(bind_host)
    return f"http://{h}:{port}/"


def print_dashboard_banner(bind_host: str, port: int) -> None:
    url = dashboard_url(bind_host, port)
    line = "=" * 58
    print(f"\n{line}", flush=True)
    print("  PecunatorCore - Abre esta URL en el navegador:", flush=True)
    print(f"    {url}", flush=True)
    if public_browser_host(bind_host) == "127.0.0.1":
        print(f"    http://localhost:{port}/   (equivale a la de arriba)", flush=True)
    print("  Copia y pega la linea si el enlace de la terminal no abre.", flush=True)
    print(f"{line}\n", flush=True)


def open_dashboard_browser(bind_host: str, port: int) -> None:
    """Open default browser after the server accepts connections."""
    url = dashboard_url(bind_host, port)
    check_host = public_browser_host(bind_host)
    for _ in range(300):
        if helpers.is_port_open(check_host, port):
            break
        time.sleep(0.1)
    if sys.platform == "win32":
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return
        except OSError:
            pass
    webbrowser.open(url)


def should_auto_open_browser() -> bool:
    return os.environ.get("PECUNATOR_AUTO_OPEN_BROWSER", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
