"""WAL-backed persistence layer for StateStore.

Provides crash-safe state snapshots so the system can rehydrate after
an unexpected termination.  Uses SQLite in WAL mode via ``db_util.open_db``
for non-blocking reads during write operations.

Design:
  - ``persist(state)`` serialises the critical StateStore fields to a
    single-row ``state_snapshot`` table (JSON blob + timestamp).
  - ``hydrate(state)`` restores the last snapshot into a StateStore instance.
  - Only *recoverable* fields are persisted (balances, equity, symbol, etc.).
    Ephemeral fields (ticker, orderbook, recent_trades) are intentionally
    excluded because they go stale within seconds.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from runtime.core.db_util import open_db

_LOG = logging.getLogger("pecunator.state_wal")

# Fields that survive a crash — chosen because they represent durable state,
# not real-time market data that goes stale within seconds.
_PERSISTED_FIELDS = (
    "selected_symbol",
    "balances",
    "balances_total_assets_in_response",
    "open_orders",
    "my_trades",
    "account_summary",
    "account_equity",
    "last_error",
    "connected",
    "api_weight_used_1m",
    "binance_server_time_ms",
    "binance_local_time_ms_at_sync",
    "binance_offset_ms",
    "binance_time_synced_at_utc",
)

_DDL = """\
CREATE TABLE IF NOT EXISTS state_snapshot (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    payload     TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
"""


def _db_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / "bot_state_wal.sqlite"


def _ensure_schema(data_dir: Path | str) -> None:
    """Create table if it doesn't exist yet."""
    db = _db_path(data_dir)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = open_db(db)
    try:
        conn.executescript(_DDL)
    finally:
        conn.close()


def persist(state: Any, data_dir: Path | str) -> None:
    """Snapshot the recoverable portion of *state* to SQLite.

    This is designed to be called at the end of every gateway polling
    cycle — fast enough (~1 ms) to not block the event loop if called
    from ``asyncio.to_thread``.
    """
    _ensure_schema(data_dir)
    payload: dict[str, Any] = {}
    for field_name in _PERSISTED_FIELDS:
        val = getattr(state, field_name, None)
        # Convert non-serialisable types
        if hasattr(val, "__iter__") and not isinstance(val, (str, list, dict)):
            val = list(val)
        payload[field_name] = val

    now = datetime.now(timezone.utc).isoformat()
    blob = json.dumps(payload, default=str)

    conn = open_db(_db_path(data_dir))
    try:
        conn.execute(
            "INSERT INTO state_snapshot (id, payload, updated_at) "
            "VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, "
            "updated_at = excluded.updated_at",
            (blob, now),
        )
        conn.commit()
    except Exception:
        _LOG.exception("state_wal: persist failed")
    finally:
        conn.close()


def hydrate(state: Any, data_dir: Path | str) -> bool:
    """Restore the last snapshot into *state*.

    Returns ``True`` if a snapshot was found and applied, ``False``
    otherwise (first run, or DB missing).
    """
    db = _db_path(data_dir)
    if not db.exists():
        return False

    _ensure_schema(data_dir)
    conn = open_db(db)
    try:
        row = conn.execute(
            "SELECT payload, updated_at FROM state_snapshot WHERE id = 1"
        ).fetchone()
        if not row:
            return False
        payload = json.loads(row[0])
        restored = 0
        for field_name in _PERSISTED_FIELDS:
            if field_name in payload:
                try:
                    setattr(state, field_name, payload[field_name])
                    restored += 1
                except (AttributeError, TypeError):
                    pass
        _LOG.info(
            "state_wal: hydrated %d fields from snapshot at %s",
            restored,
            row[1],
        )
        return True
    except Exception:
        _LOG.exception("state_wal: hydrate failed")
        return False
    finally:
        conn.close()


def last_snapshot_age_seconds(data_dir: Path | str) -> Optional[float]:
    """Return seconds since the last snapshot, or None if no snapshot exists."""
    db = _db_path(data_dir)
    if not db.exists():
        return None
    conn = open_db(db)
    try:
        row = conn.execute(
            "SELECT updated_at FROM state_snapshot WHERE id = 1"
        ).fetchone()
        if not row:
            return None
        ts = datetime.fromisoformat(row[0])
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except Exception:
        return None
    finally:
        conn.close()
