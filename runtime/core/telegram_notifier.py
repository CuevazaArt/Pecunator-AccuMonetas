"""Telegram Notifier — Consolidated status and balance notifier via Telegram."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from runtime.core.account_monitor import get_account_monitor
from runtime.core.subaccount_registry import get_subaccount_registry
from runtime.core.louise_db import LouiseDB
from runtime.core.alert_dispatcher import get_alert_dispatcher

_LOG = logging.getLogger("pecunator.core.telegram_notifier")


class TelegramNotifier:
    """Consolidates system status and balances to dispatch reports to Telegram."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._data_dir = data_dir
        self._db = LouiseDB()
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Interval in hours (default 12 hours)
        try:
            self._interval_hours = float(os.environ.get("LOUISE_TELEGRAM_NOTIFY_INTERVAL_HOURS", "12"))
        except ValueError:
            self._interval_hours = 12.0

    async def start(self) -> None:
        """Start the background notification loop."""
        if self._task is not None and not self._task.done():
            return
        
        # Don't start loop if telegram is not configured at all
        alerts = get_alert_dispatcher()
        if not alerts._telegram_token or not alerts._telegram_chat_id:
            _LOG.info("Telegram notifier loop disabled (token or chat_id missing)")
            return

        if self._interval_hours <= 0:
            _LOG.info("Telegram notifier loop disabled (interval set to <= 0)")
            return

        self._running = True
        self._task = asyncio.create_task(self._loop())
        _LOG.info("Telegram notifier loop started (interval=%.1fh)", self._interval_hours)

    async def stop(self) -> None:
        """Stop the background notification loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        _LOG.info("Telegram notifier loop stopped")

    async def _loop(self) -> None:
        interval_sec = self._interval_hours * 3600
        # Wait a bit on startup to let bots and gateway initialize before sending first report
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            return

        while self._running:
            try:
                await self.send_report(force=False)
            except Exception as e:
                _LOG.exception("Error sending scheduled Telegram report: %s", e)

            # F9: Periodically purge old pnl_snapshots to prevent unbounded DB growth
            try:
                deleted = self._db.purge_old_snapshots(days=90)
                if deleted > 0:
                    _LOG.info("DB hygiene: purged %d old pnl snapshots", deleted)
            except Exception as e:
                _LOG.warning("DB purge failed: %s", e)

            try:
                await asyncio.sleep(interval_sec)
            except asyncio.CancelledError:
                break

    async def send_report(self, force: bool = False) -> None:
        """Compile and send a formatted status and balance report to Telegram."""
        alerts = get_alert_dispatcher()
        if not alerts._telegram_token or not alerts._telegram_chat_id:
            _LOG.warning("Cannot send Telegram report: token or chat_id not configured")
            return

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # 1. Collect Balances
        registry = get_subaccount_registry(self._data_dir)
        monitor = get_account_monitor(self._data_dir)
        
        active_accounts = registry.list_active()
        balance_lines = []
        
        for acct in active_accounts:
            snap = monitor.get_latest_snapshot(acct.account_id)
            if snap:
                equity = float(snap.get("total_equity", 0.0) or 0.0)
                free = float(snap.get("free_usdt", 0.0) or 0.0)
                locked = float(snap.get("locked_usdt", 0.0) or 0.0)
                pct = (free / equity * 100) if equity > 0 else 0.0
                
                balance_lines.append(
                    f"• *{acct.account_id}*:\n"
                    f"  Patrimonio: `${equity:,.2f}` | USDT Libre: `${free:,.2f}` ({pct:.1f}%)"
                )
            else:
                # Try fallback from running bots
                free_fallback = 0.0
                from runtime.api.louise_service import get_louise_service
                svc = get_louise_service()
                
                # Check if any bot runner has active balance
                for runner in svc.runners.values():
                    if runner.config.get("subaccount") == acct.account_id:
                        free_fallback = float(runner.usdt_free_balance)
                        break
                
                balance_lines.append(
                    f"• *{acct.account_id}* (Sin snapshot):\n"
                    f"  USDT Libre (estimado): `${free_fallback:,.2f}`"
                )

        # 2. Collect Bots Status
        from runtime.api.louise_service import get_louise_service
        svc = get_louise_service()
        
        bots = self._db.get_all_bots()
        bot_lines = []
        active_count = 0
        paused_count = 0
        error_count = 0
        
        total_committed = 0.0
        total_unrealized_pnl = 0.0

        for b in bots:
            bot_id = b["bot_id"]
            status = b["status"]
            symbol = b["symbol"]
            
            if status in ("RUNNING", "ACCUMULATING"):
                active_count += 1
                runner = svc.runners.get(bot_id)
                
                if runner is not None:
                    epoch = runner.active_epoch or {}
                    num_purchases = epoch.get("num_purchases", 0) or 0
                    total_cost = float(epoch.get("total_cost", 0.0) or 0.0)
                    avg_price = float(epoch.get("avg_buy_price", 0.0) or 0.0)
                    current_price = float(runner.current_price or 0.0)
                    
                    # Calculate PnL
                    unrealized_pnl = 0.0
                    unrealized_pct = 0.0
                    if num_purchases > 0 and avg_price > 0:
                        position_qty = total_cost / avg_price
                        current_value = position_qty * current_price
                        unrealized_pnl = current_value - total_cost
                        unrealized_pct = (unrealized_pnl / total_cost) * 100
                    
                    total_committed += total_cost
                    total_unrealized_pnl += unrealized_pnl
                    
                    pnl_sign = "+" if unrealized_pnl >= 0 else ""
                    bot_lines.append(
                        f"• *{bot_id}* ({symbol}): `RUNNING`\n"
                        f"  Compras: `{num_purchases}` | Comprometido: `${total_cost:.2f}`\n"
                        f"  Precio Promedio: `${avg_price:.4f}` | Actual: `${current_price:.4f}`\n"
                        f"  PnL No Realizado: `{pnl_sign}${unrealized_pnl:.2f}` ({pnl_sign}{unrealized_pct:.2f}%)"
                    )
                else:
                    bot_lines.append(
                        f"• *{bot_id}* ({symbol}): `RUNNING` (Inicializando...)"
                    )
            elif status == "PAUSED":
                paused_count += 1
                bot_lines.append(f"• *{bot_id}* ({symbol}): `PAUSED`")
            else:
                error_count += 1
                bot_lines.append(f"• *{bot_id}* ({symbol}): `ERROR`")

        # 3. Assemble Message
        msg_parts = [
            "📊 *PECUANATOR LOUISE - REPORTE DE ESTADO*",
            f"📅 _Fecha: {now_str}_",
            "",
            "🏦 *Balances de Capital (USDT)*"
        ]
        
        if balance_lines:
            msg_parts.extend(balance_lines)
        else:
            msg_parts.append("No hay cuentas activas registradas.")
            
        msg_parts.extend([
            "",
            "🤖 *Estado de Bots Louise*"
        ])
        
        if bot_lines:
            msg_parts.extend(bot_lines)
        else:
            msg_parts.append("No hay bots configurados.")
            
        # Add summary totals
        pnl_sign_total = "+" if total_unrealized_pnl >= 0 else ""
        msg_parts.extend([
            "",
            "📈 *Resumen del Hub*",
            f"• Activos: `{active_count}` | Pausados: `{paused_count}` | Error: `{error_count}`",
            f"• Comprometido Total: `${total_committed:,.2f}` USDT",
            f"• PnL No Realizado Total: `{pnl_sign_total}${total_unrealized_pnl:,.2f}` USDT"
        ])
        
        report_text = "\n".join(msg_parts)
        
        # Send using alert dispatcher (handles deduplication and retry)
        # We bypass standard alert deduplication since this is a summary report,
        # so we pass code="LOUISE_STATUS_REPORT" but we format manually
        alerts._send_telegram_async(report_text)
        _LOG.info("Telegram status and balance report dispatched (forced=%s)", force)


# Singleton
_notifier: Optional[TelegramNotifier] = None


def get_telegram_notifier(data_dir: Optional[Path | str] = None) -> TelegramNotifier:
    """Get or create the global TelegramNotifier singleton."""
    global _notifier
    if _notifier is None:
        if data_dir is None:
            try:
                from runtime.core.settings import data_dir as _data_dir
                data_dir = _data_dir()
            except Exception:
                pass
        _notifier = TelegramNotifier(Path(data_dir) if data_dir else None)
    return _notifier
