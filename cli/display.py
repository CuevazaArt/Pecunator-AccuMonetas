"""Terminal display helpers — tables, colors, and formatting."""

from __future__ import annotations

import json
import sys
from typing import Any


# ── ANSI color codes ──────────────────────────────────────────────────

_COLORS_ENABLED: bool | None = None


def _supports_color() -> bool:
    global _COLORS_ENABLED
    if _COLORS_ENABLED is not None:
        return _COLORS_ENABLED
    # Disable colors if redirected or on dumb terminals
    _COLORS_ENABLED = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return _COLORS_ENABLED


def _c(code: str, text: str) -> str:
    if not _supports_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def green(text: str) -> str:
    return _c("32", text)


def red(text: str) -> str:
    return _c("31", text)


def yellow(text: str) -> str:
    return _c("33", text)


def cyan(text: str) -> str:
    return _c("36", text)


def bold(text: str) -> str:
    return _c("1", text)


def dim(text: str) -> str:
    return _c("2", text)


# ── Value formatters ──────────────────────────────────────────────────

def fmt_usdt(value: float | int | str) -> str:
    """Format a USDT amount with 2 decimals."""
    return f"{float(value):,.2f}"


def fmt_pct(value: float | int | str) -> str:
    """Format a percentage value."""
    return f"{float(value):.2f}%"


def fmt_pnl(value: float | int | str) -> str:
    """Format a P&L value with color (green positive, red negative)."""
    v = float(value)
    text = f"{v:+,.2f}"
    if v > 0:
        return green(text)
    elif v < 0:
        return red(text)
    return text


def fmt_pnl_pct(value: float | int | str) -> str:
    """Format a P&L percentage with color."""
    v = float(value)
    text = f"{v:+.2f}%"
    if v > 0:
        return green(text)
    elif v < 0:
        return red(text)
    return text


def fmt_status(status: str) -> str:
    """Colorize bot status."""
    s = status.upper()
    if s in ("RUNNING", "ACCUMULATING"):
        return green(s)
    elif s == "PAUSED":
        return yellow(s)
    elif s in ("SHUTDOWN", "ERROR"):
        return red(s)
    return s


def fmt_zone(zone: str) -> str:
    """Colorize weight governor zone."""
    z = zone.upper()
    if z == "GREEN":
        return green(z)
    elif z == "YELLOW":
        return yellow(z)
    elif z == "RED":
        return red(z)
    return z


# ── Table rendering ──────────────────────────────────────────────────

def print_table(headers: list[str], rows: list[list[str]], *, min_widths: list[int] | None = None) -> None:
    """Print a simple aligned table to stdout.

    Uses minimum column widths derived from header+data lengths, with
    optional *min_widths* overrides per column.
    """
    if not rows and not headers:
        return

    ncols = len(headers)
    widths = [len(h) for h in headers]

    # Measure raw (un-colored) widths for alignment
    for row in rows:
        for i, cell in enumerate(row[:ncols]):
            raw = _strip_ansi(cell)
            widths[i] = max(widths[i], len(raw))

    if min_widths:
        for i, mw in enumerate(min_widths[:ncols]):
            widths[i] = max(widths[i], mw)

    # Header
    header_line = "  ".join(bold(h.ljust(widths[i])) for i, h in enumerate(headers))
    sep_line = "  ".join("─" * widths[i] for i in range(ncols))
    print(f"  {header_line}")
    print(f"  {sep_line}")

    # Rows
    for row in rows:
        cells = []
        for i in range(ncols):
            cell = row[i] if i < len(row) else ""
            raw_len = len(_strip_ansi(cell))
            # Pad accounting for ANSI escape codes
            padding = widths[i] - raw_len
            cells.append(cell + " " * max(0, padding))
        print(f"  {'  '.join(cells)}")


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences for width calculation."""
    import re
    return re.sub(r"\033\[[0-9;]*m", "", text)


# ── JSON output ──────────────────────────────────────────────────────

def print_json(data: Any) -> None:
    """Pretty-print data as JSON."""
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


# ── Status banner ────────────────────────────────────────────────────

def print_banner(title: str, items: dict[str, str]) -> None:
    """Print a labeled info banner."""
    print(f"\n  {bold(title)}")
    print(f"  {'─' * 50}")
    for label, value in items.items():
        print(f"  {dim(label + ':')}  {value}")
    print()
