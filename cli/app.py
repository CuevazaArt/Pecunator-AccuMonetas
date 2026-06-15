"""Louise CLI — root Click application.

Usage::

    python -m cli [OPTIONS] COMMAND [ARGS]...

Global options::

    --json    Output raw JSON instead of formatted tables
    --url     Override engine API URL (default http://127.0.0.1:8000)
"""

from __future__ import annotations

import click

from cli.client import LouiseClient
from cli.commands.bot import bot_group
from cli.commands.engine import engine_group
from cli.commands.gateway import gateway_group
from cli.commands.vault import vault_group
from cli.commands.health import health_cmd, metrics_cmd, weight_cmd, hub_group, notify_cmd


@click.group()
@click.option("--json", "use_json", is_flag=True, default=False, help="Output raw JSON")
@click.option("--url", default=None, help="Engine API URL (default: http://127.0.0.1:8000)")
@click.version_option(version="1.0.0", prog_name="louise")
@click.pass_context
def cli(ctx: click.Context, use_json: bool, url: str | None) -> None:
    """Louise — DCA trading bot CLI for Pecunator-AccuMonetas.

    Manage bots, monitor the engine, and control the Binance gateway
    from the command line.

    \b
    Quick start:
      python -m cli engine start       # Start the engine
      python -m cli bot list            # List all bots
      python -m cli bot create --symbol XRPUSDT
      python -m cli health              # Health check
    """
    ctx.ensure_object(dict)
    ctx.obj["json"] = use_json
    ctx.obj["client"] = LouiseClient(base_url=url)


# Register command groups
cli.add_command(engine_group)
cli.add_command(bot_group)
cli.add_command(gateway_group)
cli.add_command(vault_group)
cli.add_command(hub_group)

# Register top-level commands
cli.add_command(health_cmd)
cli.add_command(metrics_cmd)
cli.add_command(weight_cmd)
cli.add_command(notify_cmd)
