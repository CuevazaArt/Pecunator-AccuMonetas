"""NiceGUI dashboard: compact centered layout, dark theme, no page scroll."""

from __future__ import annotations

import os
import traceback
from typing import Any

from nicegui import ui

from runtime.app import AppContext
from runtime.connectors.binance_gateway import BinanceGateway, normalize_binance_spot_symbol
from runtime.core.security_util import sanitize_log_message
from runtime.core.settings import binance_credentials_from_env
from runtime.ui.terminal import run_command

# Fixed counts so the UI fits common 1080p heights without scrolling.
_OB_LEVELS = 5
_BAL_MAX = 8
_ORD_MAX = 6
_TRD_MAX = 6
_RT_PUBLIC = 6
_TERM_MAX_CHARS = 1600


def _mono_block(lines: list[str]) -> str:
    if not lines:
        return "—"
    return "\n".join(lines)


def mount(ctx: AppContext) -> None:
    ui.add_head_html(
        "<style>html,body{height:100%;margin:0;overflow:hidden!important;}"
        ".pec-fill{min-height:0;}</style>",
        shared=True,
    )

    @ui.page("/", title="PecunatorCore", dark=True)
    def page() -> None:
        _dr = os.environ.get("PECUNATOR_DARK", "1").strip().lower()
        if _dr in ("0", "false", "no", "off", "light"):
            ui.dark_mode().disable()
        elif _dr in ("auto",):
            ui.dark_mode().auto()
        else:
            ui.dark_mode().enable()

        def strip_term(s: str) -> str:
            if len(s) <= _TERM_MAX_CHARS:
                return s
            return "…\n" + s[-(_TERM_MAX_CHARS - 2) :]

        setup_status_ref: dict[str, Any] = {}

        with ui.dialog() as vault_dialog, ui.card().classes("w-full max-w-sm"):
            ui.label("Erase vault?").classes("text-weight-bold")
            ui.label("Deletes credentials.enc and salt.bin.").classes("text-caption")

            async def wipe_vault() -> None:
                if ctx.gateway:
                    await ctx.gateway.stop()
                    ctx.gateway = None
                    ctx.state.connected = False
                ctx.config.clear_credentials()
                vault_dialog.close()
                lbl = setup_status_ref.get("setup")
                if lbl is not None:
                    lbl.set_text("Vault removed.")
                ui.notify("Deleted", type="info")

            with ui.row().classes("q-gutter-sm"):
                ui.button("Cancel", on_click=vault_dialog.close)
                ui.button("Erase", on_click=wipe_vault, color="negative")

        with ui.dialog() as setup_dialog, ui.card().classes("w-full max-w-lg"):
            ui.label("Setup & security").classes("text-h6")
            ui.markdown(
                "- Bind: `PECUNATOR_HOST` / `PORT` (default loopback).\n"
                "- Never share API keys. Prefer **encrypted vault** over env vars.\n"
                "- **REST**: official `binance-connector` · **streams**: asyncio WebSockets."
            ).classes("text-caption")

            master_pwd = (
                ui.input("Master password (>=12 chars to save)", password=True)
                .props("outlined dense")
                .classes("w-full")
            )
            api_key = ui.input("API Key").props("outlined dense").classes("w-full")
            api_secret = (
                ui.input("Secret Key", password=True).props("outlined dense").classes("w-full")
            )
            setup_status = ui.label("Unlock or save credentials.").classes("text-caption")
            setup_status_ref["setup"] = setup_status

            async def do_test() -> None:
                ak = api_key.value
                sec = api_secret.value
                if not ak or not sec:
                    ui.notify("Need API key + secret", type="warning")
                    return
                try:
                    g = BinanceGateway(ak.strip(), sec.strip(), ctx.bus, ctx.state, ctx.log_line)
                    await g.test_connection()
                    setup_status.set_text("REST OK (binance-connector Spot.account).")
                    ui.notify("OK", type="positive")
                except Exception as e:
                    setup_status.set_text(f"Test failed: {sanitize_log_message(str(e))}")
                    ui.notify("Failed", type="negative")

            async def do_save() -> None:
                mp = master_pwd.value or ""
                if not mp:
                    ui.notify("Master password required", type="warning")
                    return
                ak = api_key.value
                sec = api_secret.value
                if not ak or not sec:
                    ui.notify("Keys required", type="warning")
                    return
                try:
                    ctx.config.save_credentials(ak.strip(), sec.strip(), mp)
                    api_key.value = ""
                    api_secret.value = ""
                    setup_status.set_text("Saved (encrypted).")
                    ui.notify("Saved", type="positive")
                except ValueError as e:
                    setup_status.set_text(str(e))
                    ui.notify(str(e), type="warning")
                except Exception as e:
                    setup_status.set_text(sanitize_log_message(str(e)))
                    ui.notify("Save failed", type="negative")

            async def do_start() -> None:
                mp = master_pwd.value or ""
                if not mp:
                    ui.notify("Master password required", type="warning")
                    return
                creds = ctx.config.load_credentials(mp)
                if not creds:
                    ui.notify("Decrypt failed", type="negative")
                    return
                ak, sec = creds
                if ctx.gateway:
                    await ctx.gateway.stop()
                ctx.gateway = BinanceGateway(ak, sec, ctx.bus, ctx.state, ctx.log_line)
                try:
                    await ctx.gateway.start()
                    setup_status.set_text("Runtime online.")
                    ui.notify("Started", type="positive")
                except Exception as e:
                    ctx.gateway = None
                    setup_status.set_text(sanitize_log_message(str(e)))
                    ui.notify("Start failed", type="negative")

            async def do_start_env() -> None:
                creds = binance_credentials_from_env()
                if not creds:
                    ui.notify("Set PECUNATOR_BINANCE_API_KEY / _SECRET", type="warning")
                    return
                ak, sec = creds
                if ctx.gateway:
                    await ctx.gateway.stop()
                ctx.gateway = BinanceGateway(ak, sec, ctx.bus, ctx.state, ctx.log_line)
                try:
                    await ctx.gateway.start()
                    setup_status.set_text("Online (env keys).")
                    ui.notify("Started", type="positive")
                except Exception as e:
                    ctx.gateway = None
                    setup_status.set_text(sanitize_log_message(str(e)))
                    ui.notify("Failed", type="negative")

            async def do_stop() -> None:
                if ctx.gateway:
                    await ctx.gateway.stop()
                    ctx.gateway = None
                    ctx.state.connected = False
                    setup_status.set_text("Stopped.")
                    ui.notify("Stopped", type="info")

            with ui.row().classes("flex-wrap q-gutter-xs"):
                ui.button("Test", on_click=do_test).props("dense")
                ui.button("Save", on_click=do_save).props("dense")
                ui.button("Start", on_click=do_start, color="primary").props("dense")
                ui.button("Env start", on_click=do_start_env).props("dense")
                ui.button("Stop", on_click=do_stop).props("dense flat")
                ui.button("Erase vault…", on_click=vault_dialog.open, color="warning").props(
                    "dense flat"
                )

            ui.button("Close", on_click=setup_dialog.close).props("dense flat")

        with ui.column().classes(
            "w-full h-screen overflow-hidden items-center pec-fill bg-grey-10 q-pa-sm"
        ):
            with ui.column().classes(
                "w-full max-w-6xl h-full max-h-full overflow-hidden pec-fill flex flex-col q-gutter-xs"
            ):
                with ui.row().classes("w-full shrink-0 items-center justify-between no-wrap"):
                    ui.label("PecunatorCore · Binance Spot").classes(
                        "text-subtitle1 text-weight-bold text-grey-1"
                    )
                    with ui.row().classes("items-center q-gutter-xs shrink-0"):
                        conn_lbl = ui.label("WS: —").classes("text-caption text-grey-4")
                        ui.button(icon="settings", on_click=setup_dialog.open).props(
                            "flat round dense"
                        ).tooltip("Credentials & control")

                status_line = ui.label().classes("text-caption text-grey-4 shrink-0 truncate w-full")

                with ui.row().classes("w-full flex-1 min-h-0 pec-fill no-wrap q-gutter-sm"):
                    with ui.column().classes(
                        "flex-1 min-w-0 min-h-0 pec-fill overflow-hidden q-gutter-xs"
                    ):
                        ui.label("Market").classes("text-caption text-weight-bold text-grey-3 shrink-0")
                        with ui.row().classes("items-center q-gutter-xs shrink-0"):
                            sym_input = ui.input(placeholder="Symbol").props("dense outlined dark").classes(
                                "grow"
                            )
                            sym_input.value = ctx.state.selected_symbol

                            async def apply_symbol() -> None:
                                if not ctx.gateway:
                                    ui.notify("Start runtime from Setup first", type="warning")
                                    return
                                try:
                                    s = normalize_binance_spot_symbol(sym_input.value or "")
                                except ValueError:
                                    ui.notify("Invalid symbol", type="negative")
                                    return
                                ctx.state.selected_symbol = s
                                try:
                                    await ctx.gateway.restart_market_stream()
                                    ui.notify(s, type="positive")
                                except Exception as e:
                                    ui.notify(sanitize_log_message(str(e)), type="negative")

                            ui.button("Apply", on_click=apply_symbol).props("dense unelevated color=primary")

                        price_lbl = ui.label("Last —").classes("text-h6 text-amber-5 shrink-0")
                        spread_lbl = ui.label("Spread —").classes("text-caption text-grey-3 shrink-0")

                        ob_lbl = ui.label().classes(
                            "text-caption text-grey-2 pec-fill overflow-hidden"
                        ).style(
                            "font-family: ui-monospace, monospace; font-size: 11px; white-space: pre;"
                            "line-height: 1.15; max-height: 9rem;"
                        )

                        ui.label("Trades").classes("text-caption text-weight-bold text-grey-3 shrink-0")
                        trades_lbl = ui.label().classes("text-caption text-grey-2 shrink-0").style(
                            "font-family: ui-monospace, monospace; font-size: 11px; white-space: pre;"
                            "line-height: 1.15; max-height: 3.6rem;"
                        )

                    with ui.column().classes(
                        "flex-1 min-w-0 min-h-0 pec-fill overflow-hidden q-gutter-xs"
                    ):
                        ui.label("Account").classes("text-caption text-weight-bold text-grey-3 shrink-0")
                        bal_lbl = ui.label().classes("text-caption text-grey-2 pec-fill overflow-hidden").style(
                            "font-family: ui-monospace, monospace; font-size: 11px; white-space: pre;"
                            "line-height: 1.15; max-height: 7rem;"
                        )
                        oo_lbl = ui.label().classes("text-caption text-grey-2 pec-fill overflow-hidden").style(
                            "font-family: ui-monospace, monospace; font-size: 11px; white-space: pre;"
                            "line-height: 1.15; max-height: 5rem;"
                        )
                        mt_lbl = ui.label().classes("text-caption text-grey-2 pec-fill overflow-hidden").style(
                            "font-family: ui-monospace, monospace; font-size: 11px; white-space: pre;"
                            "line-height: 1.15; max-height: 5rem;"
                        )

                ui.label("Console").classes("text-caption text-weight-bold text-grey-3 shrink-0")
                term_out = (
                    ui.textarea()
                    .props("readonly filled dark dense")
                    .classes("w-full shrink-0 text-grey-2")
                    .style(
                        "height: 5.5rem; max-height: 5.5rem; overflow: hidden; "
                        "font-family: ui-monospace, monospace; font-size: 11px;"
                    )
                )
                with ui.row().classes("w-full shrink-0 items-center q-gutter-xs no-wrap"):
                    cmd_in = (
                        ui.input(placeholder="balances · orderbook · price BTCUSDT …")
                        .props("dense outlined dark")
                        .classes("flex-1 min-w-0")
                    )

                    async def send_cmd() -> None:
                        line = (cmd_in.value or "").strip()
                        if not line:
                            return
                        cmd_in.value = ""
                        block = (term_out.value or "") + f"\n> {line}\n"
                        try:
                            out = await run_command(line, ctx.terminal_ctx)
                        except Exception:
                            out = traceback.format_exc()
                        term_out.value = strip_term(block + out + "\n")

                    ui.button("Run", on_click=send_cmd).props("dense color=primary unelevated")

                async def on_enter(_: Any) -> None:
                    await send_cmd()

                cmd_in.on("keydown.enter", on_enter)

                def refresh() -> None:
                    base = "Online" if ctx.gateway else "Offline"
                    err = (ctx.state.last_error or "").strip()
                    if err:
                        status_line.set_text(f"{base} · {sanitize_log_message(err)[:96]}")
                    else:
                        status_line.set_text(base)

                    t = ctx.state.ticker
                    if t and t.get("b") and t.get("a"):
                        try:
                            sp_tick = float(t["a"]) - float(t["b"])
                        except (TypeError, ValueError):
                            sp_tick = None
                        price_lbl.set_text(f'Last {t.get("c", "—")}')
                        spread_lbl.set_text(
                            f"Spread {sp_tick:.8f}" if sp_tick is not None else "Spread —"
                        )
                    else:
                        price_lbl.set_text("Last —")
                        spread_lbl.set_text("Spread —")

                    sp = ctx.state.spread()
                    if sp is not None:
                        spread_lbl.set_text(f"Spread(book) {sp:.8f}")

                    conn_lbl.set_text(f"WS: {'on' if ctx.state.connected else 'off'}")

                    bids = (ctx.state.orderbook.get("bids") or [])[:_OB_LEVELS]
                    asks = (ctx.state.orderbook.get("asks") or [])[:_OB_LEVELS]
                    ob_lines = ["ASKS"]
                    for p, q in reversed(asks):
                        ob_lines.append(f"{p:>12} {q}")
                    ob_lines.append("BIDS")
                    for p, q in bids:
                        ob_lines.append(f"{p:>12} {q}")
                    ob_lbl.set_text(_mono_block(ob_lines))

                    rt = list(ctx.state.recent_trades)[:_RT_PUBLIC]
                    trades_lbl.set_text(
                        _mono_block([f'{x.get("p", "")} x {x.get("q", "")}' for x in rt])
                    )

                    rows = [
                        f'{b.get("asset", "?"):>5} {b.get("free", 0):>12} {b.get("locked", 0):>12}'
                        for b in ctx.state.balances[:_BAL_MAX]
                    ]
                    bal_lbl.set_text(_mono_block(rows))

                    oor = []
                    for o in ctx.state.open_orders[:_ORD_MAX]:
                        oor.append(
                            f'{o.get("symbol", "")} {o.get("side", "")} '
                            f'{o.get("origQty", "")} @ {o.get("price", "")}'
                        )
                    oo_lbl.set_text(_mono_block(oor))

                    mtr = []
                    for x in ctx.state.my_trades[-_TRD_MAX:]:
                        side = "B" if x.get("isBuyer") else "S"
                        mtr.append(f'{side} {x.get("qty", "")} @ {x.get("price", "")}')
                    mt_lbl.set_text(_mono_block(mtr))

                ui.timer(0.35, refresh)
