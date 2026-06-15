"""``louise engine`` — start the Pecunator engine."""

from __future__ import annotations

import click


@click.command("start")
def engine_start() -> None:
    """Start the Pecunator engine (FastAPI + uvicorn).

    This launches the HTTP API server at http://127.0.0.1:8000 (configurable
    via PECUNATOR_API_HOST / PECUNATOR_API_PORT environment variables).

    The engine must be running before any other CLI command can operate.
    """
    click.echo("  Starting Pecunator engine...\n")
    from runtime.main import main
    main()


@click.group("engine")
def engine_group() -> None:
    """Engine lifecycle management."""


engine_group.add_command(engine_start)
