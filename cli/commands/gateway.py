"""``louise gateway`` — Binance gateway lifecycle."""

from __future__ import annotations

import click

from cli.client import LouiseClient, EngineError
from cli.display import bold, dim, fmt_usdt, green, red, yellow, print_banner, print_json


def _get_client(ctx: click.Context) -> LouiseClient:
    return ctx.obj["client"]


def _is_json(ctx: click.Context) -> bool:
    return ctx.obj.get("json", False)


@click.group("gateway")
def gateway_group() -> None:
    """Binance gateway lifecycle (start, stop, status)."""


@gateway_group.command("status")
@click.pass_context
def gateway_status(ctx: click.Context) -> None:
    """Show current gateway snapshot (connection, balances, weight)."""
    client = _get_client(ctx)
    try:
        snap = client.gateway_snapshot()
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(snap)
        return

    running = snap.get("gateway_running", False)
    ws = snap.get("ws_connected", False)
    weight = snap.get("used_weight_1m")
    limit = snap.get("weight_limit_1m", 6000)
    symbol = snap.get("selected_symbol", "?")
    error = snap.get("last_error")

    status_str = green("CONNECTED") if running else red("DISCONNECTED")
    ws_str = green("YES") if ws else red("NO")

    weight_str = "N/A"
    if weight is not None:
        pct = (weight / limit * 100) if limit > 0 else 0
        if pct < 50:
            weight_str = green(f"{weight}/{limit} ({pct:.0f}%)")
        elif pct < 80:
            weight_str = yellow(f"{weight}/{limit} ({pct:.0f}%)")
        else:
            weight_str = red(f"{weight}/{limit} ({pct:.0f}%)")

    items = {
        "Status": status_str,
        "WebSocket": ws_str,
        "Symbol": symbol,
        "API Weight (1m)": weight_str,
    }
    if error:
        items["Last Error"] = red(error)

    # Equity summary
    equity = snap.get("account_equity", {})
    if equity:
        items["Equity"] = fmt_usdt(equity.get("current_usdt", 0)) + " USDT"

    print_banner("Gateway Status", items)

    # Balances with non-zero amounts
    balances = snap.get("balances", [])
    nonzero = [b for b in balances if float(b.get("free", 0)) > 0 or float(b.get("locked", 0)) > 0]
    if nonzero:
        click.echo(f"  {bold('Balances')} ({len(nonzero)} non-zero)")
        click.echo(f"  {'─' * 40}")
        for b in nonzero[:15]:
            asset = b.get("asset", "?")
            free = float(b.get("free", 0))
            locked = float(b.get("locked", 0))
            line = f"  {asset:>8}   free: {free:>12.4f}"
            if locked > 0:
                line += f"   locked: {locked:.4f}"
            click.echo(line)
        if len(nonzero) > 15:
            click.echo(f"  {dim(f'  ... and {len(nonzero) - 15} more')}")
        click.echo()


@gateway_group.command("start")
@click.option("--api-key", default=None, help="One-shot API key (otherwise uses vault)")
@click.option("--api-secret", default=None, help="One-shot API secret (otherwise uses vault)")
@click.pass_context
def gateway_start(ctx: click.Context, api_key: str | None, api_secret: str | None) -> None:
    """Start the Binance gateway connection."""
    client = _get_client(ctx)
    try:
        result = client.gateway_start(api_key, api_secret)
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(result)
        return

    click.echo(f"  ✓ Gateway started")


@gateway_group.command("stop")
@click.pass_context
def gateway_stop(ctx: click.Context) -> None:
    """Stop the Binance gateway connection."""
    client = _get_client(ctx)
    try:
        result = client.gateway_stop()
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(result)
        return

    click.echo(f"  ✓ Gateway stopped")
