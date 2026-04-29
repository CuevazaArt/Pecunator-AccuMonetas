"""Append-only local log of REST weight samples for penalty avoidance (429/418)."""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

_THROTTLE_SEC = 4.0
_HEARTBEAT_SEC = 20.0


@dataclass
class RestUsageSample:
    ts_utc: str
    used_weight_1m: Optional[int]
    weight_limit_1m: int
    hub_bots_total: int
    hub_bots_running: int
    poll_interval_sec: float
    gateway_running: bool
    last_error_snippet: Optional[str]


class RestUsageLog:
    def __init__(self, db_path: Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._last_insert_mono: float = 0.0
        self._last_used: Optional[int] = None
        self._last_limit: Optional[int] = None
        self._last_hub_bots_total: Optional[int] = None
        self._last_hub_bots_running: Optional[int] = None
        self._last_gateway_running: Optional[bool] = None
        self._last_error_snippet: Optional[str] = None
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self._path) as cx:
            cx.execute(
                """
                CREATE TABLE IF NOT EXISTS rest_weight_samples (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ts_utc TEXT NOT NULL,
                  used_weight_1m INTEGER,
                  weight_limit_1m INTEGER NOT NULL,
                  hub_bots_total INTEGER NOT NULL,
                  hub_bots_running INTEGER NOT NULL,
                  poll_interval_sec REAL NOT NULL,
                  gateway_running INTEGER NOT NULL,
                  last_error_snippet TEXT
                )
                """
            )
            cx.commit()

    def maybe_record(
        self,
        *,
        used: Optional[int],
        limit: int,
        hub_bots_total: int,
        hub_bots_running: int,
        poll_sec: float,
        gateway_running: bool,
        last_error: Optional[str],
    ) -> None:
        now = time.monotonic()
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        err_snip = None
        if last_error:
            s = str(last_error).strip()
            err_snip = s[:240] if s else None

        used_i = int(used) if used is not None else None
        limit_i = int(limit)
        hub_total_i = int(hub_bots_total)
        hub_running_i = int(hub_bots_running)
        gw_running_b = bool(gateway_running)

        changed = (
            self._last_used != used_i
            or self._last_limit != limit_i
            or self._last_hub_bots_total != hub_total_i
            or self._last_hub_bots_running != hub_running_i
            or self._last_gateway_running != gw_running_b
            or self._last_error_snippet != err_snip
        )
        elapsed = now - self._last_insert_mono

        # Hard throttle for bursts.
        if elapsed < _THROTTLE_SEC:
            return
        # Avoid inflated logs when everything is unchanged; keep a heartbeat.
        if (not changed) and elapsed < _HEARTBEAT_SEC:
            return

        with self._lock:
            with sqlite3.connect(self._path) as cx:
                cx.execute(
                    """
                    INSERT INTO rest_weight_samples (
                      ts_utc, used_weight_1m, weight_limit_1m,
                      hub_bots_total, hub_bots_running, poll_interval_sec,
                      gateway_running, last_error_snippet
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts,
                        used_i,
                        limit_i,
                        hub_total_i,
                        hub_running_i,
                        float(poll_sec),
                        1 if gw_running_b else 0,
                        err_snip,
                    ),
                )
                cx.commit()
        self._last_insert_mono = now
        self._last_used = used_i
        self._last_limit = limit_i
        self._last_hub_bots_total = hub_total_i
        self._last_hub_bots_running = hub_running_i
        self._last_gateway_running = gw_running_b
        self._last_error_snippet = err_snip

    def list_samples(self, limit: int = 200) -> list[dict[str, Any]]:
        lim = max(1, min(limit, 2000))
        with self._lock:
            with sqlite3.connect(self._path) as cx:
                cx.row_factory = sqlite3.Row
                cur = cx.execute(
                    """
                    SELECT ts_utc, used_weight_1m, weight_limit_1m,
                           hub_bots_total, hub_bots_running, poll_interval_sec,
                           gateway_running, last_error_snippet
                    FROM rest_weight_samples
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (lim,),
                )
                rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            r["gateway_running"] = bool(r.get("gateway_running"))
        return rows


_log: Optional[RestUsageLog] = None


def get_rest_usage_log(data_dir: Path) -> RestUsageLog:
    global _log
    if _log is None:
        _log = RestUsageLog(Path(data_dir) / "rest_usage_samples.sqlite")
    return _log
