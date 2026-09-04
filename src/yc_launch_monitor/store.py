from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from threading import RLock

from .domain import CollectorResult, Signal, Source, utc_now


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = RLock()
        self._migrate()

    def _migrate(self) -> None:
        with self.connection:
            self.connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS signals (
                    signal_key TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    founder_name TEXT NOT NULL,
                    text TEXT NOT NULL,
                    program TEXT NOT NULL,
                    batch_or_cohort TEXT NOT NULL,
                    occurred_at TEXT,
                    detected_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    metadata_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    last_changed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS deliveries (
                    signal_key TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    delivered_at TEXT NOT NULL,
                    outcome TEXT NOT NULL DEFAULT 'sent',
                    PRIMARY KEY(signal_key, content_hash)
                );
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    collected INTEGER NOT NULL DEFAULT 0,
                    new_or_changed INTEGER NOT NULL DEFAULT 0,
                    delivered INTEGER NOT NULL DEFAULT 0,
                    failed_deliveries INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS source_health (
                    run_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    health TEXT NOT NULL,
                    signal_count INTEGER NOT NULL,
                    diagnostic TEXT NOT NULL,
                    checked_at TEXT NOT NULL,
                    PRIMARY KEY(run_id, source)
                );
            """)
            columns = {
                row[1] for row in self.connection.execute("PRAGMA table_info(deliveries)").fetchall()
            }
            if "outcome" not in columns:
                self.connection.execute(
                    "ALTER TABLE deliveries ADD COLUMN outcome TEXT NOT NULL DEFAULT 'sent'"
                )
            run_columns = {
                row[1] for row in self.connection.execute("PRAGMA table_info(runs)").fetchall()
            }
            if "new_or_changed" not in run_columns:
                self.connection.execute(
                    "ALTER TABLE runs ADD COLUMN new_or_changed INTEGER NOT NULL DEFAULT 0"
                )
            if "failed_deliveries" not in run_columns:
                self.connection.execute(
                    "ALTER TABLE runs ADD COLUMN failed_deliveries INTEGER NOT NULL DEFAULT 0"
                )

    def close(self) -> None:
        self.connection.close()

    def upsert_signal(self, item: Signal) -> bool:
        now = utc_now()
        with self.lock, self.connection:
            current = self.connection.execute(
                "SELECT content_hash FROM signals WHERE signal_key = ?", (item.key,)
            ).fetchone()
            changed = current is None or current["content_hash"] != item.content_hash
            if current is None:
                self.connection.execute("""
                    INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.key, item.source.value, item.source_id, item.source_url, item.company_name,
                    item.founder_name, item.text, item.program, item.batch_or_cohort, item.occurred_at,
                    item.detected_at, item.status.value, item.confidence,
                    json.dumps(item.metadata, ensure_ascii=False, sort_keys=True), item.content_hash,
                    now, now, now,
                ))
            else:
                self.connection.execute("""
                    UPDATE signals SET source_url=?, company_name=?, founder_name=?, text=?, program=?,
                        batch_or_cohort=?, occurred_at=?, status=?, confidence=?, metadata_json=?,
                        content_hash=?, last_seen_at=?, last_changed_at=CASE WHEN content_hash<>? THEN ? ELSE last_changed_at END
                    WHERE signal_key=?
                """, (
                    item.source_url, item.company_name, item.founder_name, item.text, item.program,
                    item.batch_or_cohort, item.occurred_at, item.status.value, item.confidence,
                    json.dumps(item.metadata, ensure_ascii=False, sort_keys=True), item.content_hash,
                    now, item.content_hash, now, item.key,
                ))
            return changed

    def should_deliver(self, item: Signal) -> bool:
        with self.lock:
            row = self.connection.execute(
                "SELECT 1 FROM deliveries WHERE signal_key=? AND content_hash=?", (item.key, item.content_hash)
            ).fetchone()
        return row is None

    def mark_delivered(self, item: Signal) -> None:
        self._mark_processed(item, "sent")

    def mark_suppressed(self, item: Signal) -> None:
        self._mark_processed(item, "bootstrap_suppressed")

    def _mark_processed(self, item: Signal, outcome: str) -> None:
        with self.lock, self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO deliveries(signal_key, content_hash, delivered_at, outcome) VALUES (?, ?, ?, ?)",
                (item.key, item.content_hash, utc_now(), outcome),
            )

    def has_signals(self, source: Source) -> bool:
        with self.lock:
            row = self.connection.execute(
                "SELECT 1 FROM signals WHERE source=? LIMIT 1", (source.value,)
            ).fetchone()
        return row is not None

    def start_run(self, run_id: str, started_at: str) -> None:
        with self.lock, self.connection:
            self.connection.execute(
                "INSERT INTO runs(run_id, started_at, status) VALUES (?, ?, 'running')", (run_id, started_at)
            )

    def record_source(self, run_id: str, result: CollectorResult) -> None:
        with self.lock, self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO source_health VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, result.source.value, result.health.value, len(result.signals), result.diagnostic, utc_now()),
            )

    def finish_run(
        self,
        run_id: str,
        completed_at: str,
        collected: int,
        new_or_changed: int,
        delivered: int,
        failed_deliveries: int,
    ) -> None:
        with self.lock, self.connection:
            self.connection.execute(
                """UPDATE runs SET completed_at=?, status='completed', collected=?, new_or_changed=?,
                    delivered=?, failed_deliveries=? WHERE run_id=?""",
                (completed_at, collected, new_or_changed, delivered, failed_deliveries, run_id),
            )

    def latest_status(self) -> dict:
        with self.lock:
            run = self.connection.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
        if run is None:
            return {"ready": True, "last_run": None, "sources": {}}
        with self.lock:
            health = self.connection.execute(
                "SELECT source, health, signal_count, diagnostic, checked_at FROM source_health WHERE run_id=?",
                (run["run_id"],),
            ).fetchall()
        return {
            "ready": True,
            "last_run": dict(run),
            "sources": {row["source"]: dict(row) for row in health},
        }

    def list_signals(self, limit: int = 100) -> list[dict]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT * FROM signals ORDER BY first_seen_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]
