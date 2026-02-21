"""Infra-side service ops event ingestion utilities."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ea_ops.events import ServiceOpsEvent


def _now_iso() -> str:
    return datetime.now(UTC).isoformat() + "Z"


@dataclass(frozen=True)
class OpsEventRecord:
    """Infra-ingested normalized service ops event record."""

    id: str
    event_name: str
    severity: str
    feeds_back_to: str
    trace_id: str
    lineage_id: str
    payload: dict[str, Any]
    ingested_at: str

    @property
    def name(self) -> str:
        """Backward-compatible alias for legacy call sites."""
        return self.event_name


def build_ops_event_record(event: ServiceOpsEvent) -> OpsEventRecord:
    """Convert a validated ServiceOpsEvent into an infra ingestion record."""

    trace_id = str(event.payload.get("trace_id", "")).strip()
    lineage_id = str(event.payload.get("lineage_id", "")).strip()
    if not trace_id or not lineage_id:
        raise ValueError("service ops event payload must include trace_id and lineage_id")

    record_id = f"ops:{event.name}:{trace_id}:{lineage_id}:{uuid4().hex[:8]}"
    return OpsEventRecord(
        id=record_id,
        event_name=event.name,
        severity=event.severity.value,
        feeds_back_to=event.feeds_back_to.value,
        trace_id=trace_id,
        lineage_id=lineage_id,
        payload=dict(event.payload),
        ingested_at=_now_iso(),
    )


class InMemoryOpsEventStore:
    """Append-only in-memory store for ops event records."""

    __slots__ = ("_records",)

    def __init__(self) -> None:
        self._records: list[OpsEventRecord] = []

    def append(self, event: ServiceOpsEvent | OpsEventRecord) -> str:
        record = event if isinstance(event, OpsEventRecord) else build_ops_event_record(event)
        self._records.append(record)
        return record.id

    def read(self, *, after: str | None = None, limit: int = 100) -> list[OpsEventRecord]:
        if after is None:
            start = 0
        else:
            start = 0
            for idx, row in enumerate(self._records):
                if row.id == after:
                    start = idx + 1
                    break
        if limit < 0:
            raise ValueError("limit must be >= 0")
        return list(self._records[start : start + limit])

    def count(self) -> int:
        return len(self._records)


class SQLiteOpsEventStore:
    """Append-only SQLite store for ops event records."""

    __slots__ = ("_db_path",)

    _SCHEMA_VERSION = 1

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @property
    def db_path(self) -> Path:
        return self._db_path

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY
                );

                CREATE TABLE IF NOT EXISTS ops_event_records (
                    id TEXT PRIMARY KEY,
                    event_name TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    feeds_back_to TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    lineage_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    ingested_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_ops_event_name
                    ON ops_event_records(event_name);
                CREATE INDEX IF NOT EXISTS idx_ops_trace_id
                    ON ops_event_records(trace_id);
                CREATE INDEX IF NOT EXISTS idx_ops_lineage_id
                    ON ops_event_records(lineage_id);
                CREATE INDEX IF NOT EXISTS idx_ops_ingested_at
                    ON ops_event_records(ingested_at);
                """
            )

            row = conn.execute("SELECT version FROM schema_version").fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO schema_version(version) VALUES (?)",
                    (self._SCHEMA_VERSION,),
                )
            elif int(row["version"]) < self._SCHEMA_VERSION:
                conn.execute(
                    "UPDATE schema_version SET version = ?",
                    (self._SCHEMA_VERSION,),
                )
            conn.commit()

    def append(self, event: ServiceOpsEvent | OpsEventRecord) -> str:
        record = event if isinstance(event, OpsEventRecord) else build_ops_event_record(event)
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO ops_event_records (
                    id, event_name, severity, feeds_back_to, trace_id, lineage_id, payload_json, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.event_name,
                    record.severity,
                    record.feeds_back_to,
                    record.trace_id,
                    record.lineage_id,
                    json.dumps(record.payload, ensure_ascii=False, sort_keys=True),
                    record.ingested_at,
                ),
            )
            conn.commit()
        return record.id

    def read(self, *, after: str | None = None, limit: int = 100) -> list[OpsEventRecord]:
        if limit < 0:
            raise ValueError("limit must be >= 0")

        select_sql = (
            "SELECT id, event_name, severity, feeds_back_to, trace_id, lineage_id, payload_json, ingested_at "
            "FROM ops_event_records"
        )
        with self._connection() as conn:
            if after is None:
                rows = conn.execute(
                    f"{select_sql} ORDER BY rowid ASC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                pivot = conn.execute(
                    "SELECT rowid FROM ops_event_records WHERE id = ?",
                    (after,),
                ).fetchone()
                if pivot is None:
                    rows = conn.execute(
                        f"{select_sql} ORDER BY rowid ASC LIMIT ?",
                        (limit,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        f"{select_sql} WHERE rowid > ? ORDER BY rowid ASC LIMIT ?",
                        (int(pivot["rowid"]), limit),
                    ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def count(self) -> int:
        with self._connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM ops_event_records").fetchone()
        return int(row["cnt"]) if row else 0

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> OpsEventRecord:
        keys = row.keys()
        event_name = str(row["event_name"]) if "event_name" in keys else str(row["name"])
        payload_json = str(row["payload_json"]) if "payload_json" in keys else "{}"
        return OpsEventRecord(
            id=str(row["id"]),
            event_name=event_name,
            severity=str(row["severity"]),
            feeds_back_to=str(row["feeds_back_to"]),
            trace_id=str(row["trace_id"]),
            lineage_id=str(row["lineage_id"]),
            payload=json.loads(payload_json),
            ingested_at=str(row["ingested_at"]),
        )
