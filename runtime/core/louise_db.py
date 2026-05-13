import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from runtime.core.db_util import open_db

class LouiseDB:
    """Database interface for the Louise bot hub."""

    def __init__(self, db_path: str = "runtime/data/louise_hub.sqlite"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        # Create directories if they do not exist
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with open_db(self.db_path) as conn:
            # Table: louise_bots
            conn.execute("""
                CREATE TABLE IF NOT EXISTS louise_bots (
                    bot_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    buy_volume REAL NOT NULL,
                    poll_interval_seconds INTEGER NOT NULL,
                    target_profit_pct REAL NOT NULL,
                    daily_budget_usdt REAL NOT NULL,
                    max_position_size_usdt REAL DEFAULT 5000.0,
                    max_purchases_per_epoch INTEGER DEFAULT 20,
                    subaccount TEXT DEFAULT 'bluechip',
                    bot_type TEXT DEFAULT 'louise',
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)

            # Add migration: ensure new columns exist (for existing DBs)
            try:
                conn.execute("ALTER TABLE louise_bots ADD COLUMN max_position_size_usdt REAL DEFAULT 5000.0")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE louise_bots ADD COLUMN max_purchases_per_epoch INTEGER DEFAULT 20")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE louise_bots ADD COLUMN bot_type TEXT DEFAULT 'louise'")
            except sqlite3.OperationalError:
                pass

            # Table: louise_epochs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS louise_epochs (
                    epoch_id TEXT PRIMARY KEY,
                    bot_id TEXT NOT NULL,
                    num_purchases INTEGER DEFAULT 0,
                    total_cost REAL DEFAULT 0.0,
                    avg_buy_price REAL DEFAULT 0.0,
                    final_price REAL,
                    final_value REAL,
                    profit_usdt REAL,
                    profit_pct REAL,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    closed_at INTEGER,
                    FOREIGN KEY(bot_id) REFERENCES louise_bots(bot_id)
                )
            """)

            # Table: louise_purchases
            conn.execute("""
                CREATE TABLE IF NOT EXISTS louise_purchases (
                    purchase_id TEXT PRIMARY KEY,
                    bot_id TEXT NOT NULL,
                    epoch_id TEXT NOT NULL,
                    price_at_buy REAL NOT NULL,
                    volume REAL NOT NULL,
                    cost_usdt REAL NOT NULL,
                    order_id TEXT,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY(bot_id) REFERENCES louise_bots(bot_id),
                    FOREIGN KEY(epoch_id) REFERENCES louise_epochs(epoch_id)
                )
            """)

            # Table: pnl_snapshots — time-series P&L for long-term charting
            # Every poll cycle with an active position writes one row.
            # Fields:
            #   avg_entry_price_usdt  — average entry price in USDT (nominal)
            #   total_committed_usdt  — capital deployed in current epoch (nominal USDT)
            #   unrealized_pnl_usdt   — floating P&L right now in USDT
            #   unrealized_pnl_pct    — floating P&L as % of committed capital
            #   cumulative_realized_pnl_usdt — sum of ALL profits taken since bot started
            #   net_position_usdt     — cumulative_realized + unrealized (true all-time P&L)
            #   net_position_pct      — net_position as % of total capital ever committed
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pnl_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id TEXT NOT NULL,
                    bot_type TEXT NOT NULL,
                    epoch_id TEXT,
                    snapshot_at INTEGER NOT NULL,
                    current_price REAL NOT NULL,
                    avg_entry_price_usdt REAL DEFAULT 0.0,
                    num_entries INTEGER DEFAULT 0,
                    total_committed_usdt REAL DEFAULT 0.0,
                    unrealized_pnl_usdt REAL DEFAULT 0.0,
                    unrealized_pnl_pct REAL DEFAULT 0.0,
                    cumulative_realized_pnl_usdt REAL DEFAULT 0.0,
                    net_position_usdt REAL DEFAULT 0.0,
                    net_position_pct REAL DEFAULT 0.0,
                    FOREIGN KEY(bot_id) REFERENCES louise_bots(bot_id)
                )
            """)

            # Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_louise_epochs_bot_id ON louise_epochs(bot_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_louise_purchases_epoch_id ON louise_purchases(epoch_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_louise_purchases_bot_id ON louise_purchases(bot_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pnl_snapshots_bot_id ON pnl_snapshots(bot_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pnl_snapshots_at ON pnl_snapshots(snapshot_at)")

            conn.commit()

    def create_bot(
        self,
        bot_id: str,
        symbol: str,
        buy_volume: float,
        poll_interval_seconds: int,
        target_profit_pct: float,
        daily_budget_usdt: float,
        subaccount: str = "bluechip",
        status: str = "IDLE",
        max_position_size_usdt: float = 5000.0,
        max_purchases_per_epoch: int = 20,
        bot_type: str = "louise",
    ) -> None:
        now = int(time.time())
        with open_db(self.db_path) as conn:
            conn.execute("""
                INSERT INTO louise_bots
                (bot_id, symbol, buy_volume, poll_interval_seconds,
                 target_profit_pct, daily_budget_usdt, max_position_size_usdt,
                 max_purchases_per_epoch, subaccount, bot_type, status, created_at,
                 updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bot_id, symbol, buy_volume, poll_interval_seconds,
                target_profit_pct, daily_budget_usdt, max_position_size_usdt,
                max_purchases_per_epoch, subaccount, bot_type, status, now, now
            ))
            conn.commit()

    def update_bot_status(self, bot_id: str, status: str) -> None:
        now = int(time.time())
        with open_db(self.db_path) as conn:
            conn.execute("""
                UPDATE louise_bots SET status = ?, updated_at = ? WHERE bot_id = ?
            """, (status, now, bot_id))
            conn.commit()

    def get_bot(self, bot_id: str) -> Optional[Dict[str, Any]]:
        with open_db(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM louise_bots WHERE bot_id = ?", (bot_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_bots(self) -> List[Dict[str, Any]]:
        with open_db(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM louise_bots ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def update_bot_config(
        self,
        bot_id: str,
        daily_budget_usdt: Optional[float] = None,
        target_profit_pct: Optional[float] = None,
        symbol: Optional[str] = None,
        buy_volume: Optional[float] = None,
        poll_interval_seconds: Optional[int] = None,
        max_position_size_usdt: Optional[float] = None,
        max_purchases_per_epoch: Optional[int] = None,
    ) -> None:
        """Partial update of bot config; only non-None fields are written."""
        fields: List[str] = []
        params: List[Any] = []
        for col, val in (
            ("daily_budget_usdt", daily_budget_usdt),
            ("target_profit_pct", target_profit_pct),
            ("symbol", symbol),
            ("buy_volume", buy_volume),
            ("poll_interval_seconds", poll_interval_seconds),
            ("max_position_size_usdt", max_position_size_usdt),
            ("max_purchases_per_epoch", max_purchases_per_epoch),
        ):
            if val is not None:
                fields.append(f"{col} = ?")
                params.append(val)

        if not fields:
            return

        fields.append("updated_at = ?")
        params.append(int(time.time()))
        params.append(bot_id)

        sql = f"UPDATE louise_bots SET {', '.join(fields)} WHERE bot_id = ?"
        with open_db(self.db_path) as conn:
            conn.execute(sql, tuple(params))
            conn.commit()

    def create_epoch(self, epoch_id: str, bot_id: str, status: str = "RUNNING") -> None:
        now = int(time.time())
        with open_db(self.db_path) as conn:
            conn.execute("""
                INSERT INTO louise_epochs (epoch_id, bot_id, status, created_at)
                VALUES (?, ?, ?, ?)
            """, (epoch_id, bot_id, status, now))
            conn.commit()

    def update_epoch_stats(self, epoch_id: str, num_purchases: int, total_cost: float, avg_buy_price: float) -> None:
        with open_db(self.db_path) as conn:
            conn.execute("""
                UPDATE louise_epochs
                SET num_purchases = ?, total_cost = ?, avg_buy_price = ?
                WHERE epoch_id = ?
            """, (num_purchases, total_cost, avg_buy_price, epoch_id))
            conn.commit()

    def close_epoch(
        self,
        epoch_id: str,
        final_price: float,
        final_value: float,
        profit_usdt: float,
        profit_pct: float,
        status: str = "CLOSED_SUCCESSFUL"
    ) -> None:
        now = int(time.time())
        with open_db(self.db_path) as conn:
            conn.execute("""
                UPDATE louise_epochs
                SET final_price = ?, final_value = ?, profit_usdt = ?,
                    profit_pct = ?, status = ?, closed_at = ?
                WHERE epoch_id = ?
            """, (
                final_price, final_value, profit_usdt, profit_pct,
                status, now, epoch_id
            ))
            conn.commit()

    def add_purchase(
        self,
        purchase_id: str,
        bot_id: str,
        epoch_id: str,
        price_at_buy: float,
        volume: float,
        cost_usdt: float,
        order_id: Optional[str],
        status: str
    ) -> None:
        now = int(time.time())
        with open_db(self.db_path) as conn:
            conn.execute("""
                INSERT INTO louise_purchases
                (purchase_id, bot_id, epoch_id, price_at_buy, volume,
                 cost_usdt, order_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                purchase_id, bot_id, epoch_id, price_at_buy, volume,
                cost_usdt, order_id, status, now
            ))
            conn.commit()

    def get_purchases_by_epoch(self, epoch_id: str) -> List[Dict[str, Any]]:
        with open_db(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM louise_purchases WHERE epoch_id = ? "
                "ORDER BY created_at ASC",
                (epoch_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_purchases_by_bot(
        self,
        bot_id: str,
        since: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Return purchases for a bot across all its epochs, oldest first.
        Used by the console to plot every entry point on the price chart."""
        with open_db(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if since is not None:
                cursor = conn.execute(
                    "SELECT * FROM louise_purchases WHERE bot_id = ? AND created_at >= ? "
                    "ORDER BY created_at ASC LIMIT ?",
                    (bot_id, since, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM louise_purchases WHERE bot_id = ? "
                    "ORDER BY created_at ASC LIMIT ?",
                    (bot_id, limit),
                )
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_pnl_snapshot(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Return the most recent P&L snapshot for a bot (None if no snapshots yet)."""
        with open_db(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM pnl_snapshots WHERE bot_id = ? "
                "ORDER BY snapshot_at DESC LIMIT 1",
                (bot_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_active_epoch(self, bot_id: str) -> Optional[Dict[str, Any]]:
        with open_db(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM louise_epochs WHERE bot_id = ? AND "
                "status = 'RUNNING' ORDER BY created_at DESC LIMIT 1",
                (bot_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_completed_epochs_count(self) -> int:
        with open_db(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM louise_epochs WHERE status = 'CLOSED_SUCCESSFUL'")
            row = cursor.fetchone()
            return row[0] if row else 0

    def get_epoch(self, epoch_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific epoch by ID."""
        with open_db(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM louise_epochs WHERE epoch_id = ?", (epoch_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_epochs(self, bot_id: str) -> List[Dict[str, Any]]:
        """Get all epochs for a bot."""
        with open_db(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM louise_epochs WHERE bot_id = ? ORDER BY created_at DESC", (bot_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_epoch_purchases(self, epoch_id: str) -> List[Dict[str, Any]]:
        """Alias for get_purchases_by_epoch for test convenience."""
        return self.get_purchases_by_epoch(epoch_id)

    def get_total_realized_pnl(self, bot_id: str) -> float:
        """Return total profit_usdt summed across all closed epochs for a bot.

        This is the cumulative_realized_pnl: all profits effectively collected
        since the bot started. Negative values mean more losses than gains so far.
        """
        with open_db(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COALESCE(SUM(profit_usdt), 0.0) FROM louise_epochs "
                "WHERE bot_id = ? AND status NOT IN ('RUNNING')",
                (bot_id,),
            )
            row = cursor.fetchone()
            return float(row[0]) if row else 0.0

    def record_pnl_snapshot(
        self,
        bot_id: str,
        bot_type: str,
        current_price: float,
        epoch_id: Optional[str] = None,
        avg_entry_price_usdt: float = 0.0,
        num_entries: int = 0,
        total_committed_usdt: float = 0.0,
        unrealized_pnl_usdt: float = 0.0,
        unrealized_pnl_pct: float = 0.0,
        cumulative_realized_pnl_usdt: float = 0.0,
    ) -> None:
        """Record a P&L snapshot for time-series charting.

        net_position_usdt = cumulative_realized + unrealized (true all-time P&L).
        net_position_pct  = net_position / total_committed * 100 (when committed > 0).
        """
        net_position_usdt = cumulative_realized_pnl_usdt + unrealized_pnl_usdt
        net_position_pct = (
            (net_position_usdt / total_committed_usdt * 100.0)
            if total_committed_usdt > 0.0 else 0.0
        )
        now = int(time.time())
        with open_db(self.db_path) as conn:
            conn.execute("""
                INSERT INTO pnl_snapshots
                (bot_id, bot_type, epoch_id, snapshot_at, current_price,
                 avg_entry_price_usdt, num_entries, total_committed_usdt,
                 unrealized_pnl_usdt, unrealized_pnl_pct,
                 cumulative_realized_pnl_usdt, net_position_usdt, net_position_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bot_id, bot_type, epoch_id, now, current_price,
                avg_entry_price_usdt, num_entries, total_committed_usdt,
                unrealized_pnl_usdt, unrealized_pnl_pct,
                cumulative_realized_pnl_usdt, net_position_usdt, net_position_pct,
            ))
            conn.commit()

    def get_pnl_history(
        self,
        bot_id: str,
        since: Optional[int] = None,
        limit: int = 2000,
    ) -> List[Dict[str, Any]]:
        """Return P&L snapshots for a bot, ordered oldest-first.

        Args:
            bot_id: Target bot.
            since: Unix timestamp lower bound (inclusive). None = all history.
            limit: Maximum number of rows returned (default 2000 ≈ ~7 days at 5-min polls).
        """
        with open_db(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if since is not None:
                cursor = conn.execute(
                    "SELECT * FROM pnl_snapshots WHERE bot_id = ? AND snapshot_at >= ? "
                    "ORDER BY snapshot_at ASC LIMIT ?",
                    (bot_id, since, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM pnl_snapshots WHERE bot_id = ? "
                    "ORDER BY snapshot_at ASC LIMIT ?",
                    (bot_id, limit),
                )
            return [dict(row) for row in cursor.fetchall()]

    def get_combined_pnl_history(
        self,
        since: Optional[int] = None,
        limit: int = 4000,
    ) -> List[Dict[str, Any]]:
        """Return P&L snapshots for ALL bots, ordered by time.
        Useful for dual-hub combined view (Louise + AntiLouise together).
        """
        with open_db(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if since is not None:
                cursor = conn.execute(
                    "SELECT * FROM pnl_snapshots WHERE snapshot_at >= ? "
                    "ORDER BY snapshot_at ASC LIMIT ?",
                    (since, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM pnl_snapshots ORDER BY snapshot_at ASC LIMIT ?",
                    (limit,),
                )
            return [dict(row) for row in cursor.fetchall()]
