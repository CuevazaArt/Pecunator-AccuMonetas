"""``louise vault`` — credential vault management."""

from __future__ import annotations

import click

from cli.client import LouiseClient, EngineError
from cli.display import bold, dim, green, print_banner, print_json, print_table


def _get_client(ctx: click.Context) -> LouiseClient:
    return ctx.obj["client"]


def _is_json(ctx: click.Context) -> bool:
    return ctx.obj.get("json", False)


@click.group("vault")
def vault_group() -> None:
    """Encrypted credential vault management."""


@vault_group.command("status")
@click.pass_context
def vault_status(ctx: click.Context) -> None:
    """Show vault status (file exists, credential count)."""
    client = _get_client(ctx)
    try:
        result = client.vault_status()
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(result)
        return

    exists = result.get("vault_file_exists", False)
    rows = result.get("credential_rows", 0)
    active = result.get("active_credential_id")

    items = {
        "Vault file": green("exists") if exists else "not found",
        "Credentials": str(rows),
        "Active ID": active or dim("none"),
    }
    print_banner("Vault Status", items)


@vault_group.command("list")
@click.pass_context
def vault_list(ctx: click.Context) -> None:
    """List stored credentials (public key hints only)."""
    client = _get_client(ctx)
    try:
        creds = client.vault_credentials()
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(creds)
        return

    if not creds:
        click.echo("\n  No credentials stored. Add one with: louise vault add\n")
        return

    headers = ["ID", "Label", "Key Hint", "Source"]
    rows = []
    for c in creds:
        rows.append([
            c.get("credential_id", c.get("active_credential_id", "?")),
            c.get("label", ""),
            c.get("public_key_hint", c.get("public_key_last4", "?")),
            c.get("source", "vault"),
        ])

    click.echo()
    print_table(headers, rows)
    click.echo()


@vault_group.command("add")
@click.option("--api-key", prompt=True, help="Binance API key")
@click.option("--api-secret", prompt=True, hide_input=True, help="Binance API secret")
@click.option("--label", default=None, help="Optional label for this credential")
@click.pass_context
def vault_add(ctx: click.Context, api_key: str, api_secret: str, label: str | None) -> None:
    """Add a new credential to the encrypted vault."""
    client = _get_client(ctx)
    try:
        result = client.vault_add_credential(api_key, api_secret, label)
    except EngineError as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)

    if _is_json(ctx):
        print_json(result)
        return

    click.echo(f"  ✓ Credential stored in vault")
    if label:
        click.echo(f"    Label: {label}")
