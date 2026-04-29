"""Persistent audit log for operational protocols (close protocol / red button)."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class OpsAuditLog:
    def __init__(self, db_path: Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self._path) as cx:
            cx.execute(
                """
                CREATE TABLE IF NOT EXISTS ops_audit (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ts_utc TEXT NOT NULL,
                  op_name TEXT NOT NULL,
                  status TEXT NOT NULL,
                  summary_json TEXT NOT NULL,
                  error_snippet TEXT
                )
                """
            )
            cx.commit()

    def record(
        self,
        *,
        op_name: str,
        status: str,
        summary: dict[str, Any],
        error: Optional[str] = None,
    ) -> dict[str, Any]:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        row = {
            "ts_utc": ts,
            "op_name": op_name,
            "status": status,
            "summary": dict(summary),
            "error_snippet": (error or "").strip()[:240] or None,
        }
        with self._lock:
            with sqlite3.connect(self._path) as cx:
                cur = cx.execute(
                    """
                    INSERT INTO ops_audit (ts_utc, op_name, status, summary_json, error_snippet)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        row["ts_utc"],
                        row["op_name"],
                        row["status"],
                        json.dumps(row["summary"], ensure_ascii=True),
                        row["error_snippet"],
                    ),
                )
                cx.commit()
                row["id"] = int(cur.lastrowid or 0)
        return row

    def last(self, op_name: str) -> Optional[dict[str, Any]]:
        with self._lock:
            with sqlite3.connect(self._path) as cx:
                cx.row_factory = sqlite3.Row
                row = cx.execute(
                    """
                    SELECT id, ts_utc, op_name, status, summary_json, error_snippet
                    FROM ops_audit
                    WHERE op_name = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (op_name,),
                ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "ts_utc": row["ts_utc"],
            "op_name": row["op_name"],
            "status": row["status"],
            "summary": json.loads(row["summary_json"] or "{}"),
            "error_snippet": row["error_snippet"],
        }


_log: Optional[OpsAuditLog] = None


def get_ops_audit_log(data_dir: Path) -> OpsAuditLog:
    global _log
    if _log is None:
        _log = OpsAuditLog(Path(data_dir) / "ops_audit.sqlite")
    return _log
