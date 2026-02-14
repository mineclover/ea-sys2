from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class TransactionStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class TransactionUnit:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    tx_type: str = "governance_change"
    status: TransactionStatus = TransactionStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    payload: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        self.logs.append(f"[{datetime.now(UTC).isoformat()}] {message}")


@dataclass(frozen=True)
class TransactionEvent:
    id: int
    tx_id: str
    event_type: str
    message: str
    payload: dict[str, Any]
    created_at: str


class TransactionManager:
    _SCHEMA_VERSION = 1

    def __init__(self, db_path: str | Path) -> None:
        if db_path is None:
            raise ValueError("db_path is required; TransactionManager is DB-backed only")
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
        conn.execute("PRAGMA foreign_keys=ON")
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

                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    tx_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    logs_json TEXT NOT NULL DEFAULT '[]'
                );

                CREATE INDEX IF NOT EXISTS idx_tx_status
                    ON transactions(status);
                CREATE INDEX IF NOT EXISTS idx_tx_updated
                    ON transactions(updated_at);

                CREATE TABLE IF NOT EXISTS transaction_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tx_id TEXT NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_tx_event_tx_created
                    ON transaction_events(tx_id, created_at);
                """
            )
            row = conn.execute("SELECT version FROM schema_version").fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO schema_version(version) VALUES (?)",
                    (self._SCHEMA_VERSION,),
                )
            conn.commit()

    def begin_transaction(
        self,
        name: str,
        tx_type: str = "generic",
        payload: dict[str, Any] | None = None,
    ) -> TransactionUnit:
        tx = TransactionUnit(
            name=name,
            tx_type=tx_type,
            status=TransactionStatus.IN_PROGRESS,
            payload=payload or {},
        )
        self._persist_upsert(tx)
        self._persist_event(tx.id, "begin", "Transaction started", tx.payload)
        return tx

    def commit(self, tx_id: str) -> bool:
        tx = self.get_transaction(tx_id)
        if not tx:
            return False
        if tx.status != TransactionStatus.IN_PROGRESS:
            return False

        tx.status = TransactionStatus.COMMITTED
        tx.updated_at = datetime.now(UTC).isoformat()
        tx.log("Transaction committed successfully.")
        self._persist_upsert(tx)
        self._persist_event(tx_id, "commit", "Transaction committed successfully.")
        return True

    def rollback(self, tx_id: str, reason: str = "Request") -> bool:
        tx = self.get_transaction(tx_id)
        if not tx:
            return False

        tx.status = TransactionStatus.ROLLED_BACK
        tx.updated_at = datetime.now(UTC).isoformat()
        tx.log(f"Transaction rolled back. Reason: {reason}")
        self._persist_upsert(tx)
        self._persist_event(tx_id, "rollback", f"Transaction rolled back. Reason: {reason}")
        return True

    def fail(self, tx_id: str, error_msg: str) -> bool:
        tx = self.get_transaction(tx_id)
        if not tx:
            return False

        tx.status = TransactionStatus.FAILED
        tx.updated_at = datetime.now(UTC).isoformat()
        tx.log(f"Transaction failed. Error: {error_msg}")
        self._persist_upsert(tx)
        self._persist_event(tx_id, "fail", f"Transaction failed. Error: {error_msg}")
        return True

    def get_transaction(self, tx_id: str) -> TransactionUnit | None:
        return self._load_transaction(tx_id)

    def get_events(self, tx_id: str) -> list[TransactionEvent]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, tx_id, event_type, message, payload_json, created_at
                FROM transaction_events
                WHERE tx_id = ?
                ORDER BY id ASC
                """,
                (tx_id,),
            ).fetchall()

        return [self._row_to_event(row) for row in rows]

    def _persist_upsert(self, tx: TransactionUnit) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO transactions (
                    id, name, tx_type, status, created_at, updated_at, payload_json, logs_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    tx_type = excluded.tx_type,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    payload_json = excluded.payload_json,
                    logs_json = excluded.logs_json
                """,
                (
                    tx.id,
                    tx.name,
                    tx.tx_type,
                    tx.status.value,
                    tx.created_at,
                    tx.updated_at,
                    json.dumps(tx.payload, ensure_ascii=False, sort_keys=True),
                    json.dumps(tx.logs, ensure_ascii=False),
                ),
            )
            conn.commit()

    def _persist_event(
        self,
        tx_id: str,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO transaction_events (
                    tx_id, event_type, message, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    tx_id,
                    event_type,
                    message,
                    json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()

    def _load_transaction(self, tx_id: str) -> TransactionUnit | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id, name, tx_type, status, created_at, updated_at, payload_json, logs_json
                FROM transactions
                WHERE id = ?
                """,
                (tx_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_transaction(row)

    @staticmethod
    def _row_to_transaction(row: sqlite3.Row) -> TransactionUnit:
        status = TransactionStatus(str(row["status"]))
        payload = json.loads(str(row["payload_json"]))
        logs = json.loads(str(row["logs_json"]))
        return TransactionUnit(
            id=str(row["id"]),
            name=str(row["name"]),
            tx_type=str(row["tx_type"]),
            status=status,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            payload=payload,
            logs=list(logs),
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> TransactionEvent:
        return TransactionEvent(
            id=int(row["id"]),
            tx_id=str(row["tx_id"]),
            event_type=str(row["event_type"]),
            message=str(row["message"]),
            payload=json.loads(str(row["payload_json"])),
            created_at=str(row["created_at"]),
        )
