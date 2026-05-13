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
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)

            # Add migration: ensure new columns exist (for existing DBs)
            try:
                conn.execute("ALTER TABLE louise_bots ADD COLUMN max_position_size_usdt REAL DEFAULT 5000.0")
            except sqlite3.OperationalError:
                pass  # Column already exists
            try:
                conn.execute("ALTER TABLE louise_bots ADD COLUMN max_purchases_per_epoch INTEGER DEFAULT 20")
            except sqlite3.OperationalError:
                pass  # Column already exists

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

            # Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_louise_epochs_bot_id ON louise_epochs(bot_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_louise_purchases_epoch_id ON louise_purchases(epoch_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_louise_purchases_bot_id ON louise_purchases(bot_id)")

            conn.commit()

    def create_bot(self, bot_id: str, symbol: str, buy_volume: float, poll_interval_seconds: int, target_profit_pct: float, daily_budget_usdt: float, subaccount: str = "bluechip", status: str = "IDLE", max_position_size_usdt: float = 5000.0, max_purchases_per_epoch: int = 20) -> None:
        now = int(time.time())
        with open_db(self.db_path) as conn:
            conn.execute("""
                INSERT INTO louise_bots
                (bot_id, symbol, buy_volume, poll_interval_seconds, target_profit_pct, daily_budget_usdt, max_position_size_usdt, max_purchases_per_epoch, subaccount, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (bot_id, symbol, buy_volume, poll_interval_seconds, target_profit_pct, daily_budget_usdt, max_position_size_usdt, max_purchases_per_epoch, subaccount, status, now, now))
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

    def update_bot_config(self, bot_id: str, daily_budget_usdt: float, target_profit_pct: float) -> None:
        with open_db(self.db_path) as conn:
            conn.execute("""
                UPDATE louise_bots 
                SET daily_budget_usdt = ?, target_profit_pct = ?
                WHERE bot_id = ?
            """, (daily_budget_usdt, target_profit_pct, bot_id))
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

    def close_epoch(self, epoch_id: str, final_price: float, final_value: float, profit_usdt: float, profit_pct: float, status: str = "CLOSED_SUCCESSFUL") -> None:
        now = int(time.time())
        with open_db(self.db_path) as conn:
            conn.execute("""
                UPDATE louise_epochs 
                SET final_price = ?, final_value = ?, profit_usdt = ?, profit_pct = ?, status = ?, closed_at = ?
                WHERE epoch_id = ?
            """, (final_price, final_value, profit_usdt, profit_pct, status, now, epoch_id))
            conn.commit()

    def add_purchase(self, purchase_id: str, bot_id: str, epoch_id: str, price_at_buy: float, volume: float, cost_usdt: float, order_id: Optional[str], status: str) -> None:
        now = int(time.time())
        with open_db(self.db_path) as conn:
            conn.execute("""
                INSERT INTO louise_purchases 
                (purchase_id, bot_id, epoch_id, price_at_buy, volume, cost_usdt, order_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (purchase_id, bot_id, epoch_id, price_at_buy, volume, cost_usdt, order_id, status, now))
            conn.commit()

    def get_purchases_by_epoch(self, epoch_id: str) -> List[Dict[str, Any]]:
        with open_db(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM louise_purchases WHERE epoch_id = ? ORDER BY created_at ASC", (epoch_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_active_epoch(self, bot_id: str) -> Optional[Dict[str, Any]]:
        with open_db(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM louise_epochs WHERE bot_id = ? AND status = 'RUNNING' ORDER BY created_at DESC LIMIT 1", (bot_id,))
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
