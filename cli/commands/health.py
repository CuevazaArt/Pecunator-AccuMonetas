"""``louise health``, ``louise metrics``, ``louise weight`` — engine observability."""

from __future__ import annotations

import click

from cli.client import LouiseClient, EngineError
from cli.display import (
    bold,
    dim,
    fmt_pnl,
    fmt_status,
    fmt_usdt,
    fmt_zone,
    green,
    print_banner,
    print_json,
    print_table,
)


def _get_client(ctx: click.Context) -> LouiseClient:
    return ctx.obj["client"]


def _is_json(ctx: click.Context) -> bool:
    return ctx.obj.get("json", False)


# ── health ───────────────────────────────────────────────────────────

@click.command("health")
@click.pass_context
def health_cmd(ctx: click.Context) -> None:
    """Show Louise hub health status."""
    client = _get_client(ctx)
    try:
        result = client.health()
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(result)
        return

    status = result.get("status", "unknown")
    status_str = green("HEALTHY") if status == "healthy" else fmt_status(status)

    items = {
        "Status": status_str,
        "Active bots": str(result.get("active_bots", 0)),
        "Paused bots": str(result.get("paused_bots", 0)),
        "Total bots": str(result.get("total_bots", 0)),
        "Weight zone": fmt_zone(result.get("weight_zone", "UNKNOWN")),
        "Last check": result.get("last_check", "?"),
    }
    print_banner("Louise Hub Health", items)


# ── metrics ──────────────────────────────────────────────────────────

@click.command("metrics")
@click.pass_context
def metrics_cmd(ctx: click.Context) -> None:
    """Show aggregated hub metrics (portfolio, PnL, epochs)."""
    client = _get_client(ctx)
    try:
        result = client.metrics()
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(result)
        return

    items = {
        "Active bots": str(result.get("active_bots", 0)),
        "Portfolio value": fmt_usdt(result.get("total_portfolio", 0)) + " USDT",
        "Free balance": fmt_usdt(result.get("total_free_balance", 0)) + " USDT",
        "Unrealized PnL": fmt_pnl(result.get("total_unrealized_pnl", 0)) + " USDT",
        "Hub PnL %": f"{result.get('hub_pnl_percent', 0):.2f}%",
        "Completed epochs": str(result.get("completed_epochs", 0)),
    }
    print_banner("Hub Metrics", items)


# ── weight ───────────────────────────────────────────────────────────

@click.command("weight")
@click.pass_context
def weight_cmd(ctx: click.Context) -> None:
    """Show API weight governor status."""
    client = _get_client(ctx)
    try:
        result = client.weight_status()
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(result)
        return

    if "error" in result:
        click.echo(f"\n  ⚠ {result.get('message', result['error'])}\n")
        return

    weight = result.get("current_weight", "?")
    limit = result.get("weight_limit", "?")
    zone = result.get("weight_zone", "UNKNOWN")
    msg = result.get("status_message", "")

    items = {
        "Zone": fmt_zone(zone),
        "Weight": f"{weight} / {limit}",
        "Message": msg,
        "Timestamp": result.get("timestamp", "?"),
    }
    print_banner("API Weight Governor", items)


# ── hub pnl ──────────────────────────────────────────────────────────

@click.group("hub")
def hub_group() -> None:
    """Hub-wide aggregate views."""


@hub_group.command("pnl")
@click.option("--limit", type=int, default=4000, show_default=True, help="Max snapshots")
@click.pass_context
def hub_pnl(ctx: click.Context, limit: int) -> None:
    """Show combined P&L across all bots."""
    client = _get_client(ctx)
    try:
        result = client.hub_combined_pnl(limit=limit)
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(result)
        return

    totals = result.get("totals", {})
    items = {
        "Realized PnL": fmt_pnl(totals.get("cumulative_realized_pnl_usdt", 0)) + " USDT",
        "Unrealized PnL": fmt_pnl(totals.get("unrealized_pnl_usdt", 0)) + " USDT",
        "Net position": fmt_pnl(totals.get("net_position_usdt", 0)) + " USDT",
        "Snapshots": str(result.get("count", 0)),
    }
    print_banner("Hub Combined P&L", items)


@hub_group.command("state")
@click.pass_context
def hub_state(ctx: click.Context) -> None:
    """Show current state of all bots (dual-state snapshot)."""
    client = _get_client(ctx)
    try:
        result = client.hub_dual_state()
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(result)
        return

    bots = result.get("bots", [])
    if not bots:
        click.echo("\n  No bots in hub.\n")
        return

    headers = ["ID", "Type", "Symbol", "Status", "Entries", "Last Entry", "Current", "Unreal."]
    rows = []
    for b in bots:
        epoch = b.get("active_epoch") or {}
        snap = b.get("latest_snapshot") or {}
        rows.append([
            b.get("bot_id", "?"),
            b.get("bot_type", "louise"),
            b.get("symbol", "?"),
            fmt_status(b.get("status", "?")),
            str(epoch.get("num_purchases", 0)),
            fmt_usdt(b.get("last_entry_price", 0)) if b.get("last_entry_price") else dim("—"),
            fmt_usdt(b.get("current_price", 0)) if b.get("current_price") else dim("—"),
            fmt_pnl(snap.get("unrealized_pnl_usdt", 0)),
        ])

    totals = result.get("totals", {})

    click.echo(f"\n  {bold('Hub State')}  ({result.get('ts_utc', '')})")
    print_table(headers, rows)
    click.echo(f"\n  Net position: {fmt_pnl(totals.get('net_position_usdt', 0))} USDT")
    click.echo()


# ── notify ───────────────────────────────────────────────────────────

@click.command("notify")
@click.pass_context
def notify_cmd(ctx: click.Context) -> None:
    """Send immediate status and balance report via Telegram."""
    client = _get_client(ctx)
    try:
        result = client.hub_notify()
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(result)
        return

    click.echo(f"\n  ✓ {result.get('message', 'Report sent to Telegram')}\n")
