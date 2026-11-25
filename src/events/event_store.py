"""SQLite storage for safety events and inspection summaries.

Two tables:
* events       - one row per potential PPE violation event (after deduplication).
* inspections  - one row per processed image / video / live session, holding
                 detection counts used by the Analytics page.

A new SQLite connection is opened for every call, so the store can be used from
the Streamlit script thread and the webcam callback thread at the same time.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.utils.paths import load_settings, project_path

REVIEW_STATUSES = ("pending_review", "confirmed", "false_positive", "dismissed")
SOURCE_TYPES = ("image", "video", "live_camera")

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id      TEXT PRIMARY KEY,
    timestamp     TEXT NOT NULL,          -- ISO wall-clock time the event was recorded
    source_type   TEXT NOT NULL,          -- image | video | live_camera
    source_name   TEXT,
    category      TEXT NOT NULL,          -- e.g. no_helmet
    confidence    REAL NOT NULL,          -- confidence of the missing-PPE detection
    worker_ref    TEXT,                   -- per-frame worker label (W1, W2...), not an identity
    worker_box    TEXT,                   -- JSON [x1, y1, x2, y2]
    media_time_s  REAL,                   -- position in the video, if applicable
    evidence_path TEXT,
    review_status TEXT NOT NULL DEFAULT 'pending_review',
    notes         TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(timestamp);
CREATE TABLE IF NOT EXISTS inspections (
    inspection_id     TEXT PRIMARY KEY,
    timestamp         TEXT NOT NULL,
    source_type       TEXT NOT NULL,
    source_name       TEXT,
    frames_processed  INTEGER NOT NULL,
    person_detections INTEGER NOT NULL,   -- Person boxes >= worker threshold, summed over frames; NOT unique workers
    class_counts      TEXT NOT NULL,      -- JSON {class_name: count}
    events_created    INTEGER NOT NULL,
    settings          TEXT                -- JSON of thresholds used
);
"""


@dataclass
class SafetyEvent:
    event_id: str
    timestamp: str
    source_type: str
    source_name: str
    category: str
    confidence: float
    worker_ref: str | None = None
    worker_box: list[float] | None = None
    media_time_s: float | None = None
    evidence_path: str | None = None
    review_status: str = "pending_review"
    notes: str = ""


@dataclass
class InspectionRecord:
    inspection_id: str
    timestamp: str
    source_type: str
    source_name: str
    frames_processed: int
    person_detections: int
    class_counts: dict[str, int] = field(default_factory=dict)
    events_created: int = 0
    settings: dict = field(default_factory=dict)


class EventStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        # SITEGUARD_EVENTS_DB lets tests use a throw-away database.
        self.db_path = project_path(db_path or os.environ.get("SITEGUARD_EVENTS_DB") or load_settings()["events"]["database"])
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        with self._connect() as con:
            con.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        con = sqlite3.connect(self.db_path, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    # ------------------------------------------------------------------ events
    def add_event(self, event: SafetyEvent) -> None:
        if event.source_type not in SOURCE_TYPES:
            raise ValueError(f"unknown source_type {event.source_type}")
        row = asdict(event)
        row["worker_box"] = json.dumps(event.worker_box) if event.worker_box is not None else None
        with self._write_lock, self._connect() as con:
            con.execute(
                f"INSERT INTO events ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
                list(row.values()),
            )

    def update_review_status(self, event_id: str, status: str, notes: str | None = None) -> None:
        if status not in REVIEW_STATUSES:
            raise ValueError(f"review status must be one of {REVIEW_STATUSES}")
        with self._write_lock, self._connect() as con:
            if notes is None:
                con.execute("UPDATE events SET review_status=? WHERE event_id=?", (status, event_id))
            else:
                con.execute("UPDATE events SET review_status=?, notes=? WHERE event_id=?", (status, notes, event_id))

    def list_events(
        self,
        categories: list[str] | None = None,
        sources: list[str] | None = None,
        statuses: list[str] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        sql, args = "SELECT * FROM events WHERE 1=1", []
        for col, values in (("category", categories), ("source_type", sources), ("review_status", statuses)):
            if values:
                sql += f" AND {col} IN ({', '.join('?' for _ in values)})"
                args += list(values)
        if start:
            sql += " AND timestamp >= ?"
            args.append(start.isoformat(timespec="seconds"))
        if end:
            sql += " AND timestamp <= ?"
            args.append(end.isoformat(timespec="seconds"))
        sql += " ORDER BY timestamp DESC"
        if limit:
            sql += f" LIMIT {int(limit)}"
        with self._connect() as con:
            return pd.read_sql_query(sql, con, params=args)

    def count_events(self) -> int:
        with self._connect() as con:
            return int(con.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    # ------------------------------------------------------------- inspections
    def add_inspection(self, rec: InspectionRecord) -> None:
        row = asdict(rec)
        row["class_counts"] = json.dumps(rec.class_counts)
        row["settings"] = json.dumps(rec.settings)
        with self._write_lock, self._connect() as con:
            con.execute(
                f"INSERT OR REPLACE INTO inspections ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
                list(row.values()),
            )

    def list_inspections(self) -> pd.DataFrame:
        with self._connect() as con:
            return pd.read_sql_query("SELECT * FROM inspections ORDER BY timestamp DESC", con)
