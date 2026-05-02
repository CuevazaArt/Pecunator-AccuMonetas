"""Earn Manager Service for Pecunator.

Handles ingesting Simple Earn data from Binance and persisting it to SQLite
for historical APR tracking and yield optimization.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import threading
from typing import Any, Callable, Dict, List, Optional
import time

from binance.client import Client

_LOG = logging.getLogger("pecunator.api.earn")

class EarnService:
    def __init__(self):
        self._data_dir: Optional[str] = None
        self._db_path: str = ""
        self._lock = threading.Lock()
        self._bg_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def attach_data_dir(self, data_dir: str):
        self._data_dir = data_dir
        self._db_path = f"{data_dir}/earn_history.db"
        self._init_db()

    def _init_db(self):
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path, timeout=5.0)
                conn.execute("PRAGMA journal_mode=WAL")
                with conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS earn_apr_history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            timestamp_ms INTEGER NOT NULL,
                            symbol TEXT NOT NULL,
                            product_type TEXT NOT NULL,
                            duration_days TEXT NOT NULL,
                            apr_pct REAL NOT NULL,
                            quota_left REAL,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    conn.execute("""
                        CREATE INDEX IF NOT EXISTS idx_earn_sym ON earn_apr_history(symbol)
                    """)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS earn_positions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            symbol TEXT NOT NULL,
                            product_type TEXT NOT NULL,
                            amount REAL NOT NULL,
                            daily_interest REAL,
                            accumulated_interest REAL,
                            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
            except Exception as e:
                _LOG.error(f"Failed to initialize earn DB: {e}")
            finally:
                if 'conn' in locals():
                    conn.close()

    def start_background_sync(self, get_client_cb: Callable[[], Optional[Client]], interval_sec: int = 28800):
        """Starts the periodic background sync (default 28800s = 8 hours)."""
        self._stop_event.clear()
        
        async def _loop():
            _LOG.info(f"EarnService background sync started (interval={interval_sec}s)")
            while not self._stop_event.is_set():
                try:
                    await self.force_sync(get_client_cb)
                except Exception as e:
                    _LOG.error(f"EarnService background sync error: {e}")
                
                # Sleep in chunks to allow responsive shutdown
                for _ in range(interval_sec):
                    if self._stop_event.is_set():
                        break
                    await asyncio.sleep(1.0)
                    
        self._bg_task = asyncio.create_task(_loop())

    async def stop_background_sync(self):
        self._stop_event.set()
        if self._bg_task:
            await self._bg_task
            self._bg_task = None
            _LOG.info("EarnService background sync stopped.")

    async def force_sync(self, get_client_cb: Callable[[], Optional[Client]]) -> Dict[str, Any]:
        """Manually trigger a sync of Simple Earn data from Binance API."""
        client = get_client_cb()
        if not client:
            return {"status": "error", "message": "No active Binance client available."}

        _LOG.info("EarnService: Syncing Simple Earn data from Binance...")
        
        # Run synchronous binance API calls in a thread pool
        loop = asyncio.get_running_loop()
        try:
            flex_list = await loop.run_in_executor(None, lambda: client.get_simple_earn_flexible_product_list(size=100))
            locked_list = await loop.run_in_executor(None, lambda: client.get_simple_earn_locked_product_list(size=100))
        except Exception as e:
            _LOG.error(f"Binance API error during earn sync: {e}")
            return {"status": "error", "message": str(e)}

        now_ms = int(time.time() * 1000)
        inserted = 0

        with self._lock:
            conn = sqlite3.connect(self._db_path, timeout=5.0)
            try:
                with conn:
                    # Insert Flexible Products
                    if flex_list and "rows" in flex_list:
                        for row in flex_list["rows"]:
                            asset = row.get("asset", "")
                            apr = float(row.get("latestAnnualPercentageRate", 0)) * 100
                            quota = float(row.get("purchasedAmount", 0)) # Using this as a proxy for quota
                            conn.execute("""
                                INSERT INTO earn_apr_history (timestamp_ms, symbol, product_type, duration_days, apr_pct, quota_left)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (now_ms, asset, "flexible", "0", apr, quota))
                            inserted += 1
                            
                    # Insert Locked Products
                    if locked_list and "rows" in locked_list:
                        for row in locked_list["rows"]:
                            asset = row.get("asset", "")
                            detail = row.get("detail", {})
                            duration = row.get("duration", "0")
                            apr = float(detail.get("apr", 0)) * 100
                            conn.execute("""
                                INSERT INTO earn_apr_history (timestamp_ms, symbol, product_type, duration_days, apr_pct, quota_left)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (now_ms, asset, "locked", str(duration), apr, 0.0))
                            inserted += 1
                            
            except Exception as e:
                _LOG.error(f"DB insert error: {e}")
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()

        _LOG.info(f"EarnService: Synced {inserted} products.")
        return {"status": "ok", "inserted": inserted}

    def get_history(self, symbol: str) -> List[Dict[str, Any]]:
        with self._lock:
            conn = sqlite3.connect(self._db_path, timeout=5.0)
            try:
                cur = conn.execute("""
                    SELECT timestamp_ms, symbol, product_type, duration_days, apr_pct
                    FROM earn_apr_history
                    WHERE symbol = ?
                    ORDER BY timestamp_ms DESC
                    LIMIT 1000
                """, (symbol,))
                
                rows = []
                for row in cur.fetchall():
                    rows.append({
                        "timestamp_ms": row[0],
                        "symbol": row[1],
                        "product_type": row[2],
                        "duration_days": row[3],
                        "apr_pct": row[4]
                    })
                return rows
            finally:
                conn.close()
