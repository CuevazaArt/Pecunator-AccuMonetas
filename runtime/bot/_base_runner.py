"""T2.1: BaseStrategyRunner — common infrastructure for all bot runners.

Deduplicates code shared by Dorothy, Masha, and Thusnelda:
- Client management (_ensure_client, set_credentials, _to_thread)
- Equity tracking (_register_equity, _record_return)
- Metrics computation (_compute_metrics, _maybe_emit_metrics)
- Risk state persistence (restore_risk_state)
- Start/stop lifecycle with governor, panic lock, coordinator jitter
- Time sync
- Signed call retry on -1021

Concrete runners inherit this and implement only:
- run_once() -> dict: The strategy-specific decision logic
- config: The bot-specific configuration dataclass
- _bot_key() -> str: Identifier for governor/coordinator
- _loop_log_summary(report) -> str: One-line summary for cycle log
"""

from __future__ import annotations

import asyncio
import datetime as dt
import random
import time
from decimal import Decimal
from typing import Any, Callable, Optional

from binance.client import Client

from runtime.bot._decimal_utils import dec as _dec
from runtime.bot._panic import check_panic_lock
from runtime.core.security_util import sanitize_log_message


class BaseStrategyRunner:
    """Abstract base for all Pecunator bot runners."""

    # Subclass must set these
    BOT_TYPE: str = "base"

    def __init__(
        self,
        log: Callable[[str], None],
        event_log: Optional[Callable[[str, str, Optional[dict[str, Any]]], None]] = None,
    ) -> None:
        self._log = log
        self._event_log = event_log
        self._task: Optional[asyncio.Task[Any]] = None
        self._stop = asyncio.Event()
        self._last_report: dict[str, Any] = {}
        self._last_error: Optional[str] = None
        self._last_cycle_ts: Optional[str] = None
        self._api_key: Optional[str] = None
        self._api_secret: Optional[str] = None
        self._client: Optional[Client] = None
        self._error_streak = 0
        # Equity tracking
        self._peak_equity_usdt: Optional[Decimal] = None
        self._last_equity_usdt: Optional[Decimal] = None
        self._max_drawdown_seen: Decimal = Decimal("0")
        self._equity_returns: list[Decimal] = []
        self._cycle_count = 0

    # ── Event emission ──────────────────────────────────────────────

    def _emit(
        self,
        level: str,
        message: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        if self._event_log is not None:
            try:
                self._event_log(level, message, payload)
                return
            except Exception:
                pass
        self._log(message)

    # ── Properties ──────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def last_report(self) -> dict[str, Any]:
        return dict(self._last_report)

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def last_cycle_ts(self) -> Optional[str]:
        return self._last_cycle_ts

    # ── Credentials & client ────────────────────────────────────────

    def set_credentials(self, api_key: str, api_secret: str) -> None:
        self._api_key = api_key.strip()
        self._api_secret = api_secret.strip()

    def _ensure_client(self) -> Client:
        if not self._api_key or not self._api_secret:
            raise RuntimeError("No credentials resolved for bot")
        if self._client is None:
            self._client = Client(
                self._api_key,
                self._api_secret,
                requests_params={"timeout": 30},
            )
        return self._client

    def _close_client(self) -> None:
        """Close the Binance client session safely."""
        if self._client is not None:
            try:
                self._client.session.close()
            except Exception:
                pass
            self._client = None

    async def _to_thread(self, fn: Callable[[], Any]) -> Any:
        return await asyncio.to_thread(fn)

    async def _sync_time_for_signed(self, client: Client) -> None:
        """Sync local timestamp offset with Binance server time."""
        data = await self._to_thread(lambda: client.get_server_time())
        server_ms = int((data or {}).get("serverTime", 0) or 0)
        local_ms = int(time.time() * 1000)
        offset_ms = server_ms - local_ms
        try:
            client.timestamp_offset = offset_ms
        except Exception:
            pass
        self._emit(
            "INFO",
            f"{self.BOT_TYPE}:time_sync offset_ms={offset_ms}",
            {"server_time": data, "offset_ms": offset_ms},
        )

    async def _signed_call(self, client: Client, fn: Callable[[], Any]) -> Any:
        """Execute a signed Binance call, retrying on -1021 timestamp error."""
        try:
            return await self._to_thread(fn)
        except Exception as e:
            if "-1021" not in str(e):
                raise
            await self._sync_time_for_signed(client)
            return await self._to_thread(fn)

    # ── Risk state persistence ──────────────────────────────────────

    def restore_risk_state(
        self,
        *,
        peak_equity_usdt: Optional[str] = None,
        max_drawdown_seen: Optional[str] = None,
        cycle_count: Optional[int] = None,
    ) -> None:
        if peak_equity_usdt is not None:
            v = _dec(peak_equity_usdt, "0")
            self._peak_equity_usdt = v if v > 0 else None
        if max_drawdown_seen is not None:
            self._max_drawdown_seen = max(Decimal("0"), _dec(max_drawdown_seen, "0"))
        if cycle_count is not None:
            self._cycle_count = max(0, int(cycle_count))

    # ── Equity tracking ─────────────────────────────────────────────

    async def _compute_equity_usdt(
        self, client: Client, base_asset: str = "USDT",
    ) -> tuple[Decimal, Decimal]:
        """Compute total equity and free capital in base_asset."""
        try:
            from runtime.core.market_cache import get_market_cache, MarketCache
            _cache = get_market_cache()
            account = await _cache.get_or_fetch(
                MarketCache.scoped_key("account", self._api_key),
                lambda: self._to_thread(client.get_account),
            )
            tickers = await _cache.get_or_fetch(
                "tickers", lambda: self._to_thread(client.get_all_tickers),
            )
        except Exception:
            account = await self._to_thread(client.get_account)
            tickers = await self._to_thread(client.get_all_tickers)

        prices: dict[str, Decimal] = {}
        if isinstance(tickers, list):
            for t in tickers:
                if isinstance(t, dict):
                    prices[str(t.get("symbol", "")).upper()] = _dec(t.get("price", "0"), "0")

        equity = Decimal("0")
        base_free = Decimal("0")
        balances = account.get("balances", []) if isinstance(account, dict) else []
        if isinstance(balances, list):
            for b in balances:
                if not isinstance(b, dict):
                    continue
                asset = str(b.get("asset", "")).upper()
                free = _dec(b.get("free", "0"), "0")
                locked = _dec(b.get("locked", "0"), "0")
                total = free + locked
                if total <= 0:
                    continue
                if asset == base_asset:
                    equity += total
                    base_free = free
                    continue
                px = prices.get(f"{asset}{base_asset}")
                if px and px > 0:
                    equity += total * px
        return equity, base_free

    def _register_equity(self, equity: Decimal) -> tuple[Decimal, bool]:
        """Track peak equity and compute drawdown. Returns (dd, blocked)."""
        if self._peak_equity_usdt is None or equity > self._peak_equity_usdt:
            self._peak_equity_usdt = equity
        peak = self._peak_equity_usdt or equity
        dd = Decimal("0")
        if peak > 0:
            dd = (peak - equity) / peak
        if dd > self._max_drawdown_seen:
            self._max_drawdown_seen = dd
        # Access max_drawdown_pct from config (all bots have it)
        max_dd = getattr(getattr(self, 'config', None), 'max_drawdown_pct', Decimal("0.20"))
        blocked = dd > max_dd
        return dd, blocked

    def _record_return(self, prev_equity: Optional[Decimal], equity: Decimal) -> None:
        """Record equity return for metrics computation."""
        if prev_equity is None or prev_equity <= 0:
            return
        r = (equity - prev_equity) / prev_equity
        self._equity_returns.append(r)
        if len(self._equity_returns) > 500:
            self._equity_returns = self._equity_returns[-500:]

    # ── Metrics ─────────────────────────────────────────────────────

    def _compute_metrics(self) -> dict[str, Any]:
        """T1.4: Honest performance metrics — no fake Sharpe.

        - cumulative_pnl: sum of per-cycle equity returns (Decimal fraction)
        - win_rate: fraction of positive-return cycles
        - profit_factor: gross_wins / gross_losses (>1 is good)
        - max_drawdown: peak-to-trough drawdown ever observed
        """
        rs = self._equity_returns
        n = len(rs)
        if n == 0:
            return {
                "cumulative_pnl": "0",
                "win_rate": "0",
                "profit_factor": "0",
                "max_drawdown": str(self._max_drawdown_seen),
                "samples": 0,
            }
        wins = sum(1 for r in rs if r > 0)
        gross_win = sum(r for r in rs if r > 0)
        gross_loss = abs(sum(r for r in rs if r < 0))
        cumulative = sum(rs, Decimal("0"))
        pf = (gross_win / gross_loss) if gross_loss > 0 else Decimal("999")
        return {
            "cumulative_pnl": str(cumulative),
            "win_rate": str(Decimal(wins) / Decimal(n)),
            "profit_factor": str(pf),
            "max_drawdown": str(self._max_drawdown_seen),
            "samples": n,
        }

    def _maybe_emit_metrics(self) -> None:
        self._cycle_count += 1
        interval = getattr(getattr(self, 'config', None), 'metrics_interval_cycles', 5)
        if self._cycle_count % interval == 0:
            self._emit("SYSTEM", f"{self.BOT_TYPE}:metrics", self._compute_metrics())

    # ── Time sync ───────────────────────────────────────────────────

    async def sync_time(self) -> dict[str, Any]:
        client = self._ensure_client()
        data = await self._to_thread(lambda: client.get_server_time())
        server_ms = int(data.get("serverTime", 0) or 0)
        local_ms = int(time.time() * 1000)
        offset_ms = server_ms - local_ms
        try:
            client.timestamp_offset = offset_ms
        except Exception:
            pass
        self._emit(
            "INFO",
            f"{self.BOT_TYPE}:time_sync offset_ms={offset_ms}",
            {"server_time": data, "offset_ms": offset_ms},
        )
        return {
            "local_time_ms": local_ms,
            "server_time_ms": server_ms,
            "offset_ms": offset_ms,
            "source": self.BOT_TYPE,
        }

    # ── Subclass hooks ──────────────────────────────────────────────

    def _bot_key(self) -> str:
        """Return identifier for governor/coordinator (e.g. 'dorothy:XRPUSDT')."""
        raise NotImplementedError

    def _loop_log_summary(self, report: dict[str, Any]) -> str:
        """Return a one-line summary for cycle log."""
        return f"{self.BOT_TYPE}:cycle simulated={report.get('simulated')}"

    async def run_once(self) -> dict[str, Any]:
        """Execute one strategy cycle. Must be implemented by subclass."""
        raise NotImplementedError

    # ── Lifecycle ───────────────────────────────────────────────────

    async def _loop(self) -> None:
        while not self._stop.is_set():
            # ── OOB Kill Switch: PANIC.lock ────────────────────────
            if check_panic_lock():
                self._emit("CRITICAL", f"PANIC.lock detected — halting {self.BOT_TYPE}")
                break
            sleep_sec = float(getattr(self.config, 'loop_interval_sec', 450))
            # ── Fuse check with desync jitter ─────────────────────
            # If fuse is tripped, skip the cycle but add random jitter
            # so all bots don't converge when the fuse resets.
            try:
                from runtime.core.api_fuse import get_api_fuse
                fuse = get_api_fuse()
                if fuse.is_tripped():
                    remaining = fuse.remaining_cooldown_sec()
                    # Add 5-30s random desync jitter per bot
                    desync = random.uniform(5.0, 30.0)
                    self._emit("WARNING", f"API FUSE ACTIVO: ciclo omitido ({remaining:.0f}s + {desync:.0f}s jitter)")
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=min(remaining + desync, sleep_sec))
                    except asyncio.TimeoutError:
                        pass
                    continue
            except Exception:
                pass
            # ── Governor permission gate ─────────────────────────
            try:
                from runtime.core.weight_governor import get_weight_governor
                gov = get_weight_governor()
                bot_key = self._bot_key()
                wait = gov.request_permission(bot_key)
                if wait == float('inf'):
                    self._emit("WARNING", "governor:LOCKOUT — ciclo omitido (zona emergencia)")
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=sleep_sec)
                    except asyncio.TimeoutError:
                        pass
                    continue
                if wait > 0:
                    self._emit("INFO", f"governor:throttle — esperando {wait:.1f}s")
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=wait)
                    except asyncio.TimeoutError:
                        pass
                    if self._stop.is_set():
                        break
            except Exception:
                pass  # Governor unavailable — proceed normally
            try:
                rep = await self.run_once()

                self._last_report = rep
                self._last_error = None
                self._last_cycle_ts = dt.datetime.now(dt.timezone.utc).isoformat()
                self._error_streak = 0
                self._emit("INFO", self._loop_log_summary(rep), {"report": rep})
                # Report cycle to coordinator for phase tracking
                try:
                    from runtime.core.bot_coordinator import get_bot_coordinator
                    get_bot_coordinator().report_cycle(self._bot_key())
                except Exception:
                    pass
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._last_error = sanitize_log_message(str(e))
                self._error_streak += 1
                # Recreate client on failures so transient socket/session faults can self-heal.
                self._close_client()
                sleep_sec = min(
                    60.0,
                    max(2.0, min(float(getattr(self.config, 'loop_interval_sec', 450)),
                                 float(2 ** min(self._error_streak, 6)))),
                )
                self._emit("ERROR", f"{self.BOT_TYPE}:error {self._last_error}", {"error": self._last_error})
                self._emit(
                    "WARNING",
                    f"{self.BOT_TYPE}:retry_in {sleep_sec:.0f}s (streak={self._error_streak})",
                    {"retry_sec": sleep_sec, "streak": self._error_streak},
                )
            # Add coordinator jitter to prevent cycle collisions
            try:
                from runtime.core.bot_coordinator import get_bot_coordinator
                jitter = get_bot_coordinator().compute_jitter(self._bot_key())
                if jitter > 0:
                    sleep_sec += jitter
            except Exception:
                pass
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=sleep_sec)
            except asyncio.TimeoutError:
                pass

    async def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        t = self._task
        if t is not None:
            t.cancel()
            await asyncio.gather(t, return_exceptions=True)
        self._task = None
        self._close_client()
