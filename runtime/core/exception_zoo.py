"""Exception Zoo — Registry of novel exceptions for forensic study.

Every exception that passes through a Pecunator module gets fingerprinted.
If it's the first time we've seen that particular exception signature,
it's logged to SQLite with full context. Already-seen exceptions get
their hit counter incremented without re-logging the full trace.

This turns runtime errors into a searchable knowledge base for future
hardening and pattern recognition by both humans and AI.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from runtime.core.db_util import open_db

_DDL = """\
CREATE TABLE IF NOT EXISTS exception_zoo (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint     TEXT    NOT NULL UNIQUE,
    exception_type  TEXT    NOT NULL,
    message         TEXT    NOT NULL,
    module          TEXT    NOT NULL DEFAULT '',
    traceback_text  TEXT    NOT NULL DEFAULT '',
    first_seen_utc  TEXT    NOT NULL,
    last_seen_utc   TEXT    NOT NULL,
    hit_count       INTEGER NOT NULL DEFAULT 1,
    resolved        INTEGER NOT NULL DEFAULT 0,
    notes           TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_zoo_type
    ON exception_zoo(exception_type);
CREATE INDEX IF NOT EXISTS idx_zoo_first
    ON exception_zoo(first_seen_utc DESC);
"""


def _fingerprint(exc: BaseException, module: str) -> str:
    """Create a stable hash from exception type + message + origin module."""
    key = f"{type(exc).__qualname__}:{module}:{str(exc)[:200]}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


class ExceptionZoo:
    """Append-only registry of unique exceptions."""

    def __init__(self, db_path: Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._known: set[str] = set()
        self._init_schema()

    def _init_schema(self) -> None:
        conn = open_db(self._path)
        try:
            conn.executescript(_DDL)
            # Pre-load known fingerprints into memory for fast lookup
            rows = conn.execute(
                "SELECT fingerprint FROM exception_zoo"
            ).fetchall()
            self._known = {r[0] for r in rows}
        finally:
            conn.close()

    def register(
        self,
        exc: BaseException,
        module: str = "",
        context: str = "",
    ) -> tuple[str, bool]:
        """Register an exception. Returns (fingerprint, is_novel).

        is_novel=True means this is a NEVER-BEFORE-SEEN exception type+message.
        """
        fp = _fingerprint(exc, module)
        now = datetime.now(timezone.utc).isoformat()
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        tb_text = "".join(tb)[-2000:]  # Last 2000 chars of traceback

        with self._lock:
            is_novel = fp not in self._known
            conn = open_db(self._path)
            try:
                if is_novel:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO exception_zoo
                            (fingerprint, exception_type, message, module,
                             traceback_text, first_seen_utc, last_seen_utc,
                             hit_count, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                        """,
                        (
                            fp,
                            type(exc).__qualname__,
                            str(exc)[:500],
                            module[:60],
                            tb_text,
                            now, now,
                            context[:500] if context else "",
                        ),
                    )
                    self._known.add(fp)
                else:
                    conn.execute(
                        """
                        UPDATE exception_zoo
                        SET last_seen_utc = ?, hit_count = hit_count + 1
                        WHERE fingerprint = ?
                        """,
                        (now, fp),
                    )
                conn.commit()
            finally:
                conn.close()

        return fp, is_novel

    def list_novel(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent novel exceptions."""
        conn = open_db(self._path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM exception_zoo
                WHERE resolved = 0
                ORDER BY first_seen_utc DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def list_top_offenders(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return exceptions sorted by hit_count (most frequent first)."""
        conn = open_db(self._path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM exception_zoo
                ORDER BY hit_count DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def mark_resolved(self, fingerprint: str, notes: str = "") -> bool:
        conn = open_db(self._path)
        try:
            cur = conn.execute(
                "UPDATE exception_zoo SET resolved = 1, notes = ? WHERE fingerprint = ?",
                (notes[:500], fingerprint),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def summary(self) -> dict[str, Any]:
        conn = open_db(self._path)
        try:
            total = conn.execute("SELECT COUNT(*) FROM exception_zoo").fetchone()[0]
            unresolved = conn.execute(
                "SELECT COUNT(*) FROM exception_zoo WHERE resolved = 0"
            ).fetchone()[0]
            total_hits = conn.execute(
                "SELECT COALESCE(SUM(hit_count), 0) FROM exception_zoo"
            ).fetchone()[0]
            return {
                "unique_exceptions": total,
                "unresolved": unresolved,
                "total_occurrences": total_hits,
            }
        finally:
            conn.close()


# ── Singleton ───────────────────────────────────────────────────────

_zoo: Optional[ExceptionZoo] = None


def get_exception_zoo(data_dir: Optional[Path] = None) -> ExceptionZoo:
    global _zoo
    if _zoo is None:
        d = data_dir or Path("runtime/data")
        _zoo = ExceptionZoo(Path(d) / "exception_zoo.sqlite")
    return _zoo
