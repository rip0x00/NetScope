"""SQLite history store for desktop diagnostic runs (ADR-005).

Every completed diagnose run is stored with its full schema report
(JSON and rendered Markdown), so history can be browsed, filtered,
re-opened and exported without re-measuring. Retention — a maximum age
in days and a maximum row count — is enforced by :meth:`HistoryStore.prune`,
which the application calls at start-up and after settings change.

The database lives in the user data directory (see
:mod:`netscope_desktop.paths`): ``~/.local/share/netscope/history.db``
by default. Access is serialised with a lock because diagnose runs
finish on worker threads.

Locking invariant: every public method acquires ``self._lock``
exactly once, and helpers named ``_…_unlocked`` never acquire it —
they may only be called with the lock already held. The lock stays a
plain non-reentrant :class:`threading.Lock` on purpose: a future
nested public call then deadlocks loudly in the watchdog tests
instead of silently re-entering the way an ``RLock`` would allow.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from netscope_core.models import HostReport
from netscope_core.report import render_json, render_markdown

from . import paths

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    host TEXT NOT NULL,
    verdict TEXT NOT NULL,
    confidence TEXT,
    tcp443_avg_ms REAL,
    report_json TEXT NOT NULL,
    report_md TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_host ON reports(host);
CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at);
"""


@dataclass
class HistoryRow:
    id: int
    created_at: str
    host: str
    verdict: str
    confidence: str | None
    tcp443_avg_ms: float | None


class HistoryStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path if db_path is not None else paths.history_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    # -- writes ----------------------------------------------------------

    def add_report(self, report: HostReport) -> int:
        """Store one completed run; returns the new row id."""
        tcp443 = report.tcp.get(443)
        avg_ms = tcp443.avg_latency_ms if tcp443 is not None else None
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "INSERT INTO reports (created_at, host, verdict, confidence,"
                " tcp443_avg_ms, report_json, report_md)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    report.generated_at,
                    report.host,
                    report.verdict.code,
                    report.verdict.confidence,
                    avg_ms,
                    render_json(report),
                    render_markdown(report),
                ),
            )
            return int(cursor.lastrowid)

    def delete(self, row_id: int) -> bool:
        with self._lock, self._conn:
            cursor = self._conn.execute("DELETE FROM reports WHERE id = ?", (row_id,))
            return cursor.rowcount > 0

    def clear(self) -> int:
        with self._lock:
            count = self._count_unlocked()
            with self._conn:
                self._conn.execute("DELETE FROM reports")
            return count

    def prune(self, retention_days: int, max_rows: int) -> int:
        """Enforce retention limits; returns the number of rows removed."""
        removed = 0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat(
            timespec="seconds"
        )
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "DELETE FROM reports WHERE created_at < ?", (cutoff,)
            )
            removed += cursor.rowcount
            excess = self._count_unlocked() - max_rows
            if excess > 0:
                cursor = self._conn.execute(
                    "DELETE FROM reports WHERE id IN"
                    " (SELECT id FROM reports ORDER BY id ASC LIMIT ?)",
                    (excess,),
                )
                removed += cursor.rowcount
        return removed

    # -- reads -----------------------------------------------------------

    def count(self) -> int:
        with self._lock:
            return self._count_unlocked()

    def _count_unlocked(self) -> int:
        """Row count; the caller must already hold ``self._lock``."""
        row = self._conn.execute("SELECT COUNT(*) FROM reports").fetchone()
        return int(row[0])

    def list_reports(self, host: str | None = None, limit: int | None = None) -> list[HistoryRow]:
        query = (
            "SELECT id, created_at, host, verdict, confidence, tcp443_avg_ms"
            " FROM reports"
        )
        params: list = []
        if host:
            query += " WHERE host LIKE ?"
            params.append(f"%{host}%")
        query += " ORDER BY id DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [HistoryRow(*row) for row in rows]

    def get_report_json(self, row_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT report_json FROM reports WHERE id = ?", (row_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def get_report_markdown(self, row_id: int) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT report_md FROM reports WHERE id = ?", (row_id,)
            ).fetchone()
        return row[0] if row else None

    def close(self) -> None:
        with self._lock:
            self._conn.close()
