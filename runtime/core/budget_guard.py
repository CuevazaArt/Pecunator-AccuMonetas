"""T0.2: Daily budget guard — hard kill-switch on USDT spend per 24h window.

Independent of any bot logic. If total spend across ALL bots in a rolling
24-hour window exceeds max_daily_spend_usdt, ALL buys are blocked.

This prevents runaway spending even if individual bot guards fail.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

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


class BudgetGuard:
    """Singleton budget guard — enforces a hard daily spend ceiling."""

    def __init__(
        self,
        data_dir: Path | str,
        max_daily_spend_usdt: Decimal = Decimal("50"),  # Conservative for 100 USDT test
    ) -> None:
        self._db_path = Path(data_dir) / "budget_guard.sqlite"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_daily_spend_usdt = max_daily_spend_usdt
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = open_db(self._db_path)
        try:
            conn.executescript(_DDL)
        finally:
            conn.close()

    def _conn(self) -> sqlite3.Connection:
        return open_db(self._db_path)

    def can_spend(self, amount_usdt: Decimal) -> bool:
        """Check if spending `amount_usdt` would exceed the daily budget."""
        spent = self.spent_last_24h()
        return (spent + amount_usdt) <= self.max_daily_spend_usdt

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
        _LOG.info(
            "budget_guard: recorded %s %s %s %s USDT (total 24h: %s / %s)",
            bot_id, side, symbol, amount_usdt,
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

        Returns True if the spend was reserved, False if budget exhausted.
        """
        now = time.time()
        now_utc = datetime.now(timezone.utc).isoformat()
        cutoff = now - 86400
        conn = self._conn()
        try:
            # BEGIN IMMEDIATE forces a write-lock before reading
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT COALESCE(SUM(CAST(amount_usdt AS REAL)), 0) "
                "FROM budget_ledger WHERE ts >= ? AND side = 'BUY'",
                (cutoff,),
            ).fetchone()
            spent = Decimal(str(row[0])) if row else Decimal("0")
            if (spent + amount_usdt) > self.max_daily_spend_usdt:
                conn.execute("ROLLBACK")
                _LOG.warning(
                    "budget_guard: REJECTED %s %s %s USDT (spent=%s, max=%s)",
                    bot_id, symbol, amount_usdt, spent, self.max_daily_spend_usdt,
                )
                return False
            conn.execute(
                "INSERT INTO budget_ledger (ts, ts_utc, bot_id, symbol, side, amount_usdt) "
                "VALUES (?, ?, ?, ?, 'BUY', ?)",
                (now, now_utc, bot_id, symbol, str(amount_usdt)),
            )
            conn.execute("COMMIT")
            _LOG.info(
                "budget_guard: RESERVED %s %s %s USDT (total 24h: %s / %s)",
                bot_id, symbol, amount_usdt,
                spent + amount_usdt, self.max_daily_spend_usdt,
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

    def status(self) -> dict:
        spent = self.spent_last_24h()
        return {
            "spent_24h_usdt": str(spent),
            "max_daily_usdt": str(self.max_daily_spend_usdt),
            "remaining_usdt": str(self.max_daily_spend_usdt - spent),
            "blocked": spent >= self.max_daily_spend_usdt,
        }


# ── Singleton ───────────────────────────────────────────────────────

_guard: Optional[BudgetGuard] = None


def get_budget_guard(
    data_dir: Optional[Path | str] = None,
    max_daily_spend_usdt: Decimal = Decimal("100"),
) -> BudgetGuard:
    """Get or create the global BudgetGuard singleton."""
    global _guard
    if _guard is None:
        if data_dir is None:
            from runtime.core.settings import data_dir as _data_dir
            data_dir = _data_dir()
        _guard = BudgetGuard(data_dir, max_daily_spend_usdt)
    return _guard
