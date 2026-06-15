"""``louise bot`` — CRUD and control for Louise DCA bots."""

from __future__ import annotations

import click

from cli.client import LouiseClient, EngineError
from cli.display import (
    bold,
    cyan,
    dim,
    fmt_pnl,
    fmt_pnl_pct,
    fmt_status,
    fmt_usdt,
    print_banner,
    print_json,
    print_table,
)


def _get_client(ctx: click.Context) -> LouiseClient:
    return ctx.obj["client"]


def _is_json(ctx: click.Context) -> bool:
    return ctx.obj.get("json", False)


# ── Bot group ────────────────────────────────────────────────────────

@click.group("bot")
def bot_group() -> None:
    """Manage Louise DCA bots (create, list, pause, resume, update, delete)."""


# ── list ─────────────────────────────────────────────────────────────

@bot_group.command("list")
@click.pass_context
def bot_list(ctx: click.Context) -> None:
    """List all Louise bots with current state."""
    client = _get_client(ctx)
    try:
        bots = client.bot_list()
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(bots)
        return

    if not bots:
        click.echo("\n  No bots configured. Create one with: louise bot create\n")
        return

    headers = ["ID", "Symbol", "Status", "Cost Basis", "Unrealized", "PnL %", "Trades", "Target"]
    rows = []
    for b in bots:
        rows.append([
            b["id"],
            b["symbol"],
            fmt_status(b["status"]),
            fmt_usdt(b["cost_basis"]),
            fmt_pnl(b["unrealized_pnl"]),
            fmt_pnl_pct(b["unrealized_pct"]),
            str(b["trades_today"]),
            f"{b['target_profit_pct']:.1f}%",
        ])

    click.echo()
    print_table(headers, rows)
    click.echo()


# ── create ───────────────────────────────────────────────────────────

@bot_group.command("create")
@click.option("--symbol", required=True, help="Trading pair or comma-separated list of pairs (e.g. XRPUSDT or XRPUSDT,ADAUSDT)")
@click.option("--budget", type=float, default=500.0, show_default=True, help="Daily budget in USDT")
@click.option("--target-profit", type=float, default=5.0, show_default=True, help="Take-profit percentage")
@click.option("--buy-volume", type=float, default=10.0, show_default=True, help="USDT per buy order")
@click.option("--poll-interval", type=int, default=60, show_default=True, help="Polling interval in seconds")
@click.option("--subaccount", default="bluechip", show_default=True, help="Subaccount name")
@click.option("--max-position", type=float, default=5000.0, show_default=True, help="Maximum position size in USDT per epoch")
@click.option("--max-purchases", type=int, default=20, show_default=True, help="Maximum number of buy fills per epoch")
@click.pass_context
def bot_create(
    ctx: click.Context,
    symbol: str,
    budget: float,
    target_profit: float,
    buy_volume: float,
    poll_interval: int,
    subaccount: str,
    max_position: float,
    max_purchases: int,
) -> None:
    """Create one or more Louise DCA bots (mono or multi symbol)."""
    client = _get_client(ctx)
    symbols = [s.strip().upper() for s in symbol.split(",") if s.strip()]
    
    results = []
    has_errors = False
    
    for sym in symbols:
        try:
            result = client.bot_create(
                symbol=sym,
                daily_budget=budget,
                target_profit_pct=target_profit,
                buy_volume=buy_volume,
                poll_interval_seconds=poll_interval,
                subaccount=subaccount,
                max_position_size_usdt=max_position,
                max_purchases_per_epoch=max_purchases,
            )
            results.append({"symbol": sym, "ok": True, "data": result})
            
            if not _is_json(ctx):
                bot_id = result.get("bot_id", "?")
                click.echo(f"\n  ✓ Bot created: {bold(bot_id)}")
                click.echo(f"    Symbol:       {sym}")
                click.echo(f"    Budget:       {fmt_usdt(budget)} USDT/day")
                click.echo(f"    Target:       {target_profit:.1f}%")
                click.echo(f"    Buy Vol:      {fmt_usdt(buy_volume)} USDT")
                click.echo(f"    Interval:     {poll_interval}s")
                click.echo(f"    Subaccount:   {subaccount}")
                click.echo(f"    Max Position: {fmt_usdt(max_position)} USDT")
                click.echo(f"    Max Trades:   {max_purchases}")
        except EngineError as e:
            results.append({"symbol": sym, "ok": False, "error": e.detail})
            has_errors = True
            if not _is_json(ctx):
                click.echo(f"\n  ✗ Failed to create bot for {bold(sym)}: {e.detail}", err=True)

    if not _is_json(ctx):
        click.echo()
        if has_errors:
            raise SystemExit(1)
        return

    # JSON output
    if len(symbols) == 1:
        if results[0]["ok"]:
            print_json(results[0]["data"])
        else:
            print_json({"error": results[0]["error"]})
            raise SystemExit(1)
    else:
        print_json(results)
        if has_errors:
            raise SystemExit(1)


# ── pause ────────────────────────────────────────────────────────────

@bot_group.command("pause")
@click.argument("bot_id")
@click.pass_context
def bot_pause(ctx: click.Context, bot_id: str) -> None:
    """Pause a running bot."""
    client = _get_client(ctx)
    try:
        result = client.bot_pause(bot_id)
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(result)
        return

    click.echo(f"  ✓ Bot {bold(bot_id)} paused")


# ── resume ───────────────────────────────────────────────────────────

@bot_group.command("resume")
@click.argument("bot_id")
@click.pass_context
def bot_resume(ctx: click.Context, bot_id: str) -> None:
    """Resume a paused bot."""
    client = _get_client(ctx)
    try:
        result = client.bot_resume(bot_id)
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(result)
        return

    click.echo(f"  ✓ Bot {bold(bot_id)} resumed")


# ── update ───────────────────────────────────────────────────────────

@bot_group.command("update")
@click.argument("bot_id")
@click.option("--budget", type=float, default=None, help="New daily budget in USDT")
@click.option("--target-profit", type=float, default=None, help="New take-profit percentage")
@click.option("--buy-volume", type=float, default=None, help="New USDT per buy order")
@click.option("--poll-interval", type=int, default=None, help="New polling interval in seconds")
@click.option("--symbol", default=None, help="New trading pair")
@click.option("--max-position", type=float, default=None, help="New maximum position size in USDT per epoch")
@click.option("--max-purchases", type=int, default=None, help="New maximum number of buy fills per epoch")
@click.pass_context
def bot_update(
    ctx: click.Context,
    bot_id: str,
    budget: float | None,
    target_profit: float | None,
    buy_volume: float | None,
    poll_interval: int | None,
    symbol: str | None,
    max_position: float | None,
    max_purchases: int | None,
) -> None:
    """Update configuration of an existing bot."""
    client = _get_client(ctx)

    kwargs = {}
    if budget is not None:
        kwargs["daily_budget"] = budget
    if target_profit is not None:
        kwargs["target_profit_pct"] = target_profit
    if buy_volume is not None:
        kwargs["buy_volume"] = buy_volume
    if poll_interval is not None:
        kwargs["poll_interval_seconds"] = poll_interval
    if symbol is not None:
        kwargs["symbol"] = symbol.upper()
    if max_position is not None:
        kwargs["max_position_size_usdt"] = max_position
    if max_purchases is not None:
        kwargs["max_purchases_per_epoch"] = max_purchases

    if not kwargs:
        click.echo("  ✗ No updates specified. Use --budget, --target-profit, etc.", err=True)
        raise SystemExit(1)

    try:
        result = client.bot_update(bot_id, **kwargs)
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(result)
        return

    click.echo(f"  ✓ Bot {bold(bot_id)} updated")
    for k, v in kwargs.items():
        click.echo(f"    {k}: {v}")


# ── delete ───────────────────────────────────────────────────────────

@bot_group.command("delete")
@click.argument("bot_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def bot_delete(ctx: click.Context, bot_id: str, yes: bool) -> None:
    """Shutdown and remove a bot."""
    if not yes:
        click.confirm(f"  Shutdown bot {bot_id}?", abort=True)

    client = _get_client(ctx)
    try:
        result = client.bot_delete(bot_id)
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(result)
        return

    click.echo(f"  ✓ Bot {bold(bot_id)} shut down")


# ── pnl ──────────────────────────────────────────────────────────────

@bot_group.command("pnl")
@click.argument("bot_id")
@click.option("--limit", type=int, default=20, show_default=True, help="Max snapshots to display")
@click.pass_context
def bot_pnl(ctx: click.Context, bot_id: str, limit: int) -> None:
    """Show P&L history for a bot."""
    client = _get_client(ctx)
    try:
        result = client.bot_pnl_history(bot_id, limit=limit)
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(result)
        return

    snapshots = result.get("snapshots", [])
    if not snapshots:
        click.echo(f"\n  No P&L history for {bot_id}\n")
        return

    headers = ["Time", "Price", "Avg Entry", "Entries", "Committed", "Unreal. PnL", "PnL %"]
    rows = []
    for s in snapshots[-limit:]:
        ts = s.get("ts_utc", s.get("recorded_at", "?"))
        if isinstance(ts, str) and len(ts) > 19:
            ts = ts[:19]
        rows.append([
            ts,
            fmt_usdt(s.get("current_price", 0)),
            fmt_usdt(s.get("avg_entry_price_usdt", 0)),
            str(s.get("num_entries", 0)),
            fmt_usdt(s.get("total_committed_usdt", 0)),
            fmt_pnl(s.get("unrealized_pnl_usdt", 0)),
            fmt_pnl_pct(s.get("unrealized_pnl_pct", 0)),
        ])

    click.echo(f"\n  {bold(f'P&L History — {bot_id}')}  ({result.get('count', len(snapshots))} total)")
    print_table(headers, rows)
    click.echo()


# ── purchases ────────────────────────────────────────────────────────

@bot_group.command("purchases")
@click.argument("bot_id")
@click.option("--limit", type=int, default=20, show_default=True, help="Max purchases to display")
@click.pass_context
def bot_purchases(ctx: click.Context, bot_id: str, limit: int) -> None:
    """Show purchase history for a bot."""
    client = _get_client(ctx)
    try:
        result = client.bot_purchases(bot_id, limit=limit)
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(result)
        return

    purchases = result.get("purchases", [])
    if not purchases:
        click.echo(f"\n  No purchases for {bot_id}\n")
        return

    headers = ["Purchase ID", "Price", "Volume", "Cost USDT", "Status"]
    rows = []
    for p in purchases[-limit:]:
        rows.append([
            str(p.get("purchase_id", "?")),
            fmt_usdt(p.get("price_at_buy", 0)),
            f"{float(p.get('volume', 0)):.6f}",
            fmt_usdt(p.get("cost_usdt", 0)),
            p.get("status", "?"),
        ])

    click.echo(f"\n  {bold(f'Purchases — {bot_id}')}  ({result.get('count', len(purchases))} total)")
    print_table(headers, rows)
    click.echo()
