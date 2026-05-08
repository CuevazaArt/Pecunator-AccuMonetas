"""T0.2: Daily budget guard — hard kill-switch on USDT spend per 24h window.

Independent of any bot logic. If total spend across ALL bots in a rolling
24-hour window exceeds max_daily_spend_usdt, ALL buys are blocked.

Supports per-hub spend buckets so a single aggressive hub cannot starve
others.  Hub ratios default to proportional splits but are configurable.

This prevents runaway spending even if individual bot guards fail.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional

from runtime.core.db_util import open_db

_LOG = logging.getLogger("pecunator.core.budget_guard")

_DDL = """\
CREATE TABLE IF NOT EXISTS budget_ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL    NOT NULL,
    ts_utc      TEXT    NOT NULL,
    bot_id      TEXT    NOT NULL,
    symbol      TEXT    NOT NULL,
    side        TEXT    NOT NULL,
    amount_usdt TEXT    NOT NULL
);
"""

# Default hub-level budget ratios (fraction of the global ceiling).
# Values must sum to <= 1.0.  Anything not listed falls into "other".
_DEFAULT_HUB_RATIOS: Dict[str, float] = {
    "dorothy":   0.40,
    "masha":     0.35,
    "thusnelda": 0.20,
    # 5% headroom for unclassified bots
}


def _hub_from_bot_id(bot_id: str) -> str:
    """Extract hub name from a bot_id like 'dorothy-abc123' or 'thusnelda:PEPE…'."""
    for prefix in ("dorothy", "masha", "thusnelda"):
        if bot_id.lower().startswith(prefix):
            return prefix
    return "other"


class BudgetGuard:
    """Singleton budget guard — enforces a hard daily spend ceiling.

    Two-tier protection:
      1. **Global ceiling** — total across all bots cannot exceed max_daily_spend_usdt.
      2. **Per-hub ceiling** — each hub cannot exceed its allocated fraction.
    """

    def __init__(
        self,
        data_dir: Path | str,
        max_daily_spend_usdt: Decimal = Decimal("50"),
        hub_ratios: Optional[Dict[str, float]] = None,
    ) -> None:
        self._db_path = Path(data_dir) / "budget_guard.sqlite"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_daily_spend_usdt = max_daily_spend_usdt
        self._hub_ratios = hub_ratios or _DEFAULT_HUB_RATIOS
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = open_db(self._db_path)
        try:
            conn.executescript(_DDL)
        finally:
            conn.close()

    def _conn(self) -> sqlite3.Connection:
        return open_db(self._db_path)

    def _hub_ceiling(self, hub: str) -> Decimal:
        """Per-hub ceiling = global ceiling * hub ratio."""
        ratio = self._hub_ratios.get(hub, 0.05)
        return Decimal(str(float(self.max_daily_spend_usdt) * ratio))

    def can_spend(self, amount_usdt: Decimal, bot_id: str = "") -> bool:
        """Check if spending `amount_usdt` would exceed the daily budget.

        Checks BOTH global ceiling and per-hub ceiling.
        """
        spent_global = self.spent_last_24h()
        if (spent_global + amount_usdt) > self.max_daily_spend_usdt:
            return False
        if bot_id:
            hub = _hub_from_bot_id(bot_id)
            spent_hub = self.spent_last_24h_by_hub(hub)
            if (spent_hub + amount_usdt) > self._hub_ceiling(hub):
                return False
        return True

    def record_spend(
        self,
        bot_id: str,
        symbol: str,
        side: str,
        amount_usdt: Decimal,
    ) -> None:
        """Record a spend event in the append-only ledger."""
        now = time.time()
        now_utc = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO budget_ledger (ts, ts_utc, bot_id, symbol, side, amount_usdt) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now, now_utc, bot_id, symbol, side, str(amount_usdt)),
            )
            conn.commit()
        finally:
            conn.close()
        hub = _hub_from_bot_id(bot_id)
        _LOG.info(
            "budget_guard: recorded %s %s %s %s USDT (hub=%s: %s/%s, global: %s/%s)",
            bot_id, side, symbol, amount_usdt,
            hub, self.spent_last_24h_by_hub(hub), self._hub_ceiling(hub),
            self.spent_last_24h(), self.max_daily_spend_usdt,
        )

    def try_reserve(
        self,
        bot_id: str,
        symbol: str,
        amount_usdt: Decimal,
    ) -> bool:
        """Atomically check budget and record spend in ONE transaction.

        Eliminates the TOCTOU race between can_spend() and record_spend()
        where concurrent bots could both pass the check and then both spend,
        exceeding the daily budget.

        Enforces both global and per-hub ceilings.

        Returns True if the spend was reserved, False if budget exhausted.
        """
        now = time.time()
        now_utc = datetime.now(timezone.utc).isoformat()
        cutoff = now - 86400
        hub = _hub_from_bot_id(bot_id)
        hub_ceiling = self._hub_ceiling(hub)
        hub_prefix = f"{hub}%"
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")

            # Global check
            row = conn.execute(
                "SELECT COALESCE(SUM(CAST(amount_usdt AS REAL)), 0) "
                "FROM budget_ledger WHERE ts >= ? AND side = 'BUY'",
                (cutoff,),
            ).fetchone()
            spent_global = Decimal(str(row[0])) if row else Decimal("0")
            if (spent_global + amount_usdt) > self.max_daily_spend_usdt:
                conn.execute("ROLLBACK")
                _LOG.warning(
                    "budget_guard: REJECTED_GLOBAL %s %s %s USDT (spent=%s, max=%s)",
                    bot_id, symbol, amount_usdt, spent_global, self.max_daily_spend_usdt,
                )
                return False

            # Per-hub check
            row_hub = conn.execute(
                "SELECT COALESCE(SUM(CAST(amount_usdt AS REAL)), 0) "
                "FROM budget_ledger WHERE ts >= ? AND side = 'BUY' AND bot_id LIKE ?",
                (cutoff, hub_prefix),
            ).fetchone()
            spent_hub = Decimal(str(row_hub[0])) if row_hub else Decimal("0")
            if (spent_hub + amount_usdt) > hub_ceiling:
                conn.execute("ROLLBACK")
                _LOG.warning(
                    "budget_guard: REJECTED_HUB %s(%s) %s %s USDT "
                    "(hub_spent=%s, hub_max=%s)",
                    bot_id, hub, symbol, amount_usdt, spent_hub, hub_ceiling,
                )
                return False

            conn.execute(
                "INSERT INTO budget_ledger (ts, ts_utc, bot_id, symbol, side, amount_usdt) "
                "VALUES (?, ?, ?, ?, 'BUY', ?)",
                (now, now_utc, bot_id, symbol, str(amount_usdt)),
            )
            conn.execute("COMMIT")
            _LOG.info(
                "budget_guard: RESERVED %s %s %s USDT "
                "(hub=%s: %s/%s, global: %s/%s)",
                bot_id, symbol, amount_usdt,
                hub, spent_hub + amount_usdt, hub_ceiling,
                spent_global + amount_usdt, self.max_daily_spend_usdt,
            )
            return True
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            conn.close()

    def spent_last_24h(self) -> Decimal:
        """Sum of all BUY-side spends in the last 24 hours."""
        cutoff = time.time() - 86400
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(CAST(amount_usdt AS REAL)), 0) "
                "FROM budget_ledger WHERE ts >= ? AND side = 'BUY'",
                (cutoff,),
            ).fetchone()
            return Decimal(str(row[0])) if row else Decimal("0")
        finally:
            conn.close()

    def spent_last_24h_by_hub(self, hub: str) -> Decimal:
        """Sum of BUY-side spends in the last 24h for a specific hub."""
        cutoff = time.time() - 86400
        prefix = f"{hub}%"
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(CAST(amount_usdt AS REAL)), 0) "
                "FROM budget_ledger WHERE ts >= ? AND side = 'BUY' AND bot_id LIKE ?",
                (cutoff, prefix),
            ).fetchone()
            return Decimal(str(row[0])) if row else Decimal("0")
        finally:
            conn.close()

    def status(self) -> dict:
        spent = self.spent_last_24h()
        hub_status = {}
        for hub in list(self._hub_ratios.keys()) + ["other"]:
            hub_spent = self.spent_last_24h_by_hub(hub)
            hub_ceil = self._hub_ceiling(hub)
            hub_status[hub] = {
                "spent_24h": str(hub_spent),
                "ceiling": str(hub_ceil),
                "remaining": str(hub_ceil - hub_spent),
                "blocked": hub_spent >= hub_ceil,
                "pct": round(
                    float(hub_spent) / float(hub_ceil) * 100, 1
                ) if hub_ceil > 0 else 0,
            }
        return {
            "spent_24h_usdt": str(spent),
            "max_daily_usdt": str(self.max_daily_spend_usdt),
            "remaining_usdt": str(self.max_daily_spend_usdt - spent),
            "blocked": spent >= self.max_daily_spend_usdt,
            "pct": round(
                float(spent) / float(self.max_daily_spend_usdt) * 100, 1
            ),
            "hubs": hub_status,
        }


# ── Singleton ───────────────────────────────────────────────────────

_guard: Optional[BudgetGuard] = None


def get_budget_guard(
    data_dir: Optional[Path | str] = None,
    max_daily_spend_usdt: Decimal = Decimal("1500"),
) -> BudgetGuard:
    """Get or create the global BudgetGuard singleton."""
    global _guard
    if _guard is None:
        if data_dir is None:
            from runtime.core.settings import data_dir as _data_dir
            data_dir = _data_dir()
        _guard = BudgetGuard(data_dir, max_daily_spend_usdt)
    return _guard
