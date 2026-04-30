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
        self._last_event_used: Optional[int] = None
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
            cx.execute(
                """
                CREATE TABLE IF NOT EXISTS rest_weight_events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ts_utc TEXT NOT NULL,
                  source TEXT NOT NULL,
                  action TEXT NOT NULL,
                  used_weight_1m INTEGER,
                  delta_weight_1m INTEGER,
                  note TEXT
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

    def record_event(
        self,
        *,
        source: str,
        action: str,
        used_weight_1m: Optional[int],
        note: Optional[str] = None,
    ) -> None:
        from datetime import datetime, timezone

        used_i = None if used_weight_1m is None else int(used_weight_1m)
        delta_i: Optional[int] = None
        event_note = (note or "").strip()[:240] or None
        if used_i is not None and self._last_event_used is not None:
            if used_i >= self._last_event_used:
                delta_i = used_i - self._last_event_used
            else:
                event_note = (event_note or "weight window reset")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        src = (source or "unknown").strip()[:60] or "unknown"
        act = (action or "unknown").strip()[:120] or "unknown"
        with self._lock:
            with sqlite3.connect(self._path) as cx:
                cx.execute(
                    """
                    INSERT INTO rest_weight_events (
                      ts_utc, source, action, used_weight_1m, delta_weight_1m, note
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (ts, src, act, used_i, delta_i, event_note),
                )
                cx.commit()
        self._last_event_used = used_i

    def list_events(self, limit: int = 300) -> list[dict[str, Any]]:
        lim = max(1, min(limit, 5000))
        with self._lock:
            with sqlite3.connect(self._path) as cx:
                cx.row_factory = sqlite3.Row
                cur = cx.execute(
                    """
                    SELECT ts_utc, source, action, used_weight_1m, delta_weight_1m, note
                    FROM rest_weight_events
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (lim,),
                )
                return [dict(r) for r in cur.fetchall()]

    def summary_by_action(self, limit: int = 5000) -> list[dict[str, Any]]:
        lim = max(1, min(limit, 20000))
        with self._lock:
            with sqlite3.connect(self._path) as cx:
                cx.row_factory = sqlite3.Row
                cur = cx.execute(
                    """
                    WITH base AS (
                      SELECT ts_utc, source, action, used_weight_1m, delta_weight_1m
                      FROM rest_weight_events
                      ORDER BY id DESC
                      LIMIT ?
                    )
                    SELECT
                      source,
                      action,
                      COUNT(*) AS events,
                      SUM(CASE WHEN delta_weight_1m IS NULL OR delta_weight_1m < 0 THEN 0 ELSE delta_weight_1m END) AS delta_sum,
                      MAX(CASE WHEN delta_weight_1m IS NULL OR delta_weight_1m < 0 THEN 0 ELSE delta_weight_1m END) AS delta_max,
                      AVG(CASE WHEN delta_weight_1m IS NULL OR delta_weight_1m < 0 THEN NULL ELSE delta_weight_1m END) AS delta_avg,
                      MAX(ts_utc) AS last_ts_utc,
                      MAX(used_weight_1m) AS max_used_seen
                    FROM base
                    GROUP BY source, action
                    ORDER BY delta_sum DESC, events DESC
                    """,
                    (lim,),
                )
                return [dict(r) for r in cur.fetchall()]


_log: Optional[RestUsageLog] = None


def get_rest_usage_log(data_dir: Path) -> RestUsageLog:
    global _log
    if _log is None:
        _log = RestUsageLog(Path(data_dir) / "rest_usage_samples.sqlite")
    return _log
