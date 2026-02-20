"""Topic Store — S3 Recording for Decision Layer.

Persistent storage for completed decision snapshots with query capabilities.
Provides:
- TopicStore ABC: 저장소 인터페이스
- InMemoryTopicStore: 테스트용 인메모리 구현
- SQLiteTopicStore: SQLite 기반 영속 저장소

References:
- ea_kernel/decision_store.py: S3 Store 3-tier 패턴
- ea-sys-conventions.md §5: Store 패턴
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════════
# Domain Types — Stored Decision Snapshot
# ═══════════════════════════════════════════════════════════════════════════════

class DecisionSnapshotStatus(StrEnum):
    """완료된 의사결정 상태."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class StoredDecisionSnapshot:
    """완료된 의사결정 스냅샷.

    Topic의 확정 시점 정보를 불변 레코드로 저장.
    """
    storage_id: str
    topic_id: str
    pattern_name: str
    complexity: str
    option_count: int
    evaluation_score: float
    decided_at: str
    status: DecisionSnapshotStatus
    stored_at: str = ""
    rationale: str = ""
    selected_option_id: str = ""
    execution_id: str = ""
    execution_success: bool | None = None
    transaction_id: str = ""
    trace_id: str = ""
    need_refs: tuple[str, ...] = ()  # Forward causal reference to Needs
    projection_refs: tuple[str, ...] = ()  # Projection snapshot IDs observed
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class DecisionQueryOptions:
    """의사결정 조회 옵션."""
    pattern_name: str = ""
    complexity: str = ""
    status: DecisionSnapshotStatus | None = None
    start_time: str = ""
    end_time: str = ""
    trace_id: str = ""
    need_ref: str = ""  # Filter by Need ID in need_refs
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class DecisionStatistics:
    """패턴별 의사결정 통계."""
    pattern_name: str
    total_decisions: int = 0
    avg_options: float = 0.0
    avg_evaluation_score: float = 0.0
    acceptance_rate: float = 0.0
    avg_time_to_decision_days: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# TopicStore ABC — 저장소 인터페이스
# ═══════════════════════════════════════════════════════════════════════════════

class TopicStore(ABC):
    """Topic Store ABC — 의사결정 스냅샷 저장소 인터페이스."""

    @abstractmethod
    def store(self, snapshot: StoredDecisionSnapshot) -> StoredDecisionSnapshot:
        """의사결정 스냅샷 저장.

        Args:
            snapshot: 저장할 스냅샷 (storage_id가 비어있으면 자동 생성)

        Returns:
            StoredDecisionSnapshot with storage metadata
        """
        ...

    @abstractmethod
    def get(self, storage_id: str) -> StoredDecisionSnapshot | None:
        """storage_id로 스냅샷 조회."""
        ...

    @abstractmethod
    def query(
        self, options: DecisionQueryOptions | None = None,
    ) -> tuple[StoredDecisionSnapshot, ...]:
        """조건부 조회."""
        ...

    @abstractmethod
    def count(self, options: DecisionQueryOptions | None = None) -> int:
        """조건에 맞는 레코드 수."""
        ...

    @abstractmethod
    def statistics_by_pattern(self) -> tuple[DecisionStatistics, ...]:
        """패턴별 통계."""
        ...


# ═══════════════════════════════════════════════════════════════════════════════
# InMemoryTopicStore — 테스트용 인메모리 구현
# ═══════════════════════════════════════════════════════════════════════════════

class InMemoryTopicStore(TopicStore):
    """In-memory Topic Store for testing."""

    __slots__ = ("_records", "_by_pattern")

    def __init__(self) -> None:
        self._records: dict[str, StoredDecisionSnapshot] = {}
        self._by_pattern: dict[str, list[StoredDecisionSnapshot]] = {}

    def store(self, snapshot: StoredDecisionSnapshot) -> StoredDecisionSnapshot:
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        storage_id = snapshot.storage_id or str(uuid.uuid4())

        stored = StoredDecisionSnapshot(
            storage_id=storage_id,
            topic_id=snapshot.topic_id,
            pattern_name=snapshot.pattern_name,
            complexity=snapshot.complexity,
            option_count=snapshot.option_count,
            evaluation_score=snapshot.evaluation_score,
            decided_at=snapshot.decided_at,
            status=snapshot.status,
            stored_at=now,
            rationale=snapshot.rationale,
            selected_option_id=snapshot.selected_option_id,
            execution_id=snapshot.execution_id,
            execution_success=snapshot.execution_success,
            transaction_id=snapshot.transaction_id,
            trace_id=snapshot.trace_id,
            need_refs=snapshot.need_refs,
            projection_refs=snapshot.projection_refs,
            metadata=snapshot.metadata,
        )

        self._records[storage_id] = stored
        self._by_pattern.setdefault(snapshot.pattern_name, []).append(stored)
        return stored

    def get(self, storage_id: str) -> StoredDecisionSnapshot | None:
        return self._records.get(storage_id)

    def query(
        self, options: DecisionQueryOptions | None = None,
    ) -> tuple[StoredDecisionSnapshot, ...]:
        if options is None:
            return tuple(self._records.values())
        return tuple(self._filter_records(options))

    def count(self, options: DecisionQueryOptions | None = None) -> int:
        if options is None:
            return len(self._records)
        return len(self._filter_records(options))

    def statistics_by_pattern(self) -> tuple[DecisionStatistics, ...]:
        results: list[DecisionStatistics] = []

        for pattern_name, records in self._by_pattern.items():
            if not records:
                continue

            total = len(records)
            avg_options = sum(r.option_count for r in records) / total
            avg_score = sum(r.evaluation_score for r in records) / total
            accepted = sum(
                1 for r in records
                if r.status == DecisionSnapshotStatus.ACCEPTED
            )
            acceptance_rate = accepted / total if total > 0 else 0.0

            results.append(DecisionStatistics(
                pattern_name=pattern_name,
                total_decisions=total,
                avg_options=avg_options,
                avg_evaluation_score=avg_score,
                acceptance_rate=acceptance_rate,
            ))

        return tuple(sorted(results, key=lambda s: -s.total_decisions))

    def _filter_records(
        self, options: DecisionQueryOptions,
    ) -> list[StoredDecisionSnapshot]:
        if options.pattern_name:
            candidates = self._by_pattern.get(options.pattern_name, [])
        else:
            candidates = list(self._records.values())

        results: list[StoredDecisionSnapshot] = []
        for snap in candidates:
            if options.complexity and snap.complexity != options.complexity:
                continue
            if options.status is not None and snap.status != options.status:
                continue
            if options.start_time and snap.decided_at < options.start_time:
                continue
            if options.end_time and snap.decided_at > options.end_time:
                continue
            if options.trace_id and snap.trace_id != options.trace_id:
                continue
            if options.need_ref and options.need_ref not in snap.need_refs:
                continue
            results.append(snap)

        start = options.offset
        end = options.offset + options.limit
        return results[start:end]


# ═══════════════════════════════════════════════════════════════════════════════
# SQLiteTopicStore — SQLite 기반 영속 저장소
# ═══════════════════════════════════════════════════════════════════════════════

class SQLiteTopicStore(TopicStore):
    """SQLite-backed Topic Store for persistent storage."""

    __slots__ = ("_db_path",)

    _SCHEMA_VERSION = 5

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._init_schema()

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
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY
                );

                CREATE TABLE IF NOT EXISTS decision_snapshots (
                    storage_id TEXT PRIMARY KEY,
                    topic_id TEXT NOT NULL,
                    pattern_name TEXT NOT NULL,
                    complexity TEXT NOT NULL,
                    option_count INTEGER NOT NULL,
                    evaluation_score REAL NOT NULL,
                    decided_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stored_at TEXT NOT NULL,
                    rationale TEXT DEFAULT '',
                    selected_option_id TEXT DEFAULT '',
                    execution_id TEXT DEFAULT '',
                    execution_success INTEGER DEFAULT NULL,
                    transaction_id TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_pattern_name
                    ON decision_snapshots(pattern_name);
                CREATE INDEX IF NOT EXISTS idx_complexity
                    ON decision_snapshots(complexity);
                CREATE INDEX IF NOT EXISTS idx_status
                    ON decision_snapshots(status);
                CREATE INDEX IF NOT EXISTS idx_decided_at
                    ON decision_snapshots(decided_at);
            """)

            # Migration: add columns for existing databases
            for col, default, col_type in (
                ("execution_id", "''", "TEXT"),
                ("execution_success", "NULL", "INTEGER"),
                ("transaction_id", "''", "TEXT"),
                ("trace_id", "''", "TEXT"),
                ("need_refs_json", "'[]'", "TEXT"),
                ("projection_refs_json", "'[]'", "TEXT"),
            ):
                try:
                    conn.execute(
                        f"ALTER TABLE decision_snapshots ADD COLUMN {col} "
                        f"{col_type} DEFAULT {default}"
                    )
                except sqlite3.OperationalError:
                    pass  # column already exists

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_trace_id ON decision_snapshots(trace_id)"
            )

            cursor = conn.execute("SELECT version FROM schema_version")
            row = cursor.fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (self._SCHEMA_VERSION,),
                )
            elif row[0] < self._SCHEMA_VERSION:
                conn.execute(
                    "UPDATE schema_version SET version = ?",
                    (self._SCHEMA_VERSION,),
                )

            conn.commit()

    def store(self, snapshot: StoredDecisionSnapshot) -> StoredDecisionSnapshot:
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        storage_id = snapshot.storage_id or str(uuid.uuid4())
        metadata_json = json.dumps(dict(snapshot.metadata))

        stored = StoredDecisionSnapshot(
            storage_id=storage_id,
            topic_id=snapshot.topic_id,
            pattern_name=snapshot.pattern_name,
            complexity=snapshot.complexity,
            option_count=snapshot.option_count,
            evaluation_score=snapshot.evaluation_score,
            decided_at=snapshot.decided_at,
            status=snapshot.status,
            stored_at=now,
            rationale=snapshot.rationale,
            selected_option_id=snapshot.selected_option_id,
            execution_id=snapshot.execution_id,
            execution_success=snapshot.execution_success,
            transaction_id=snapshot.transaction_id,
            trace_id=snapshot.trace_id,
            need_refs=snapshot.need_refs,
            projection_refs=snapshot.projection_refs,
            metadata=snapshot.metadata,
        )

        exec_success_val = None
        if snapshot.execution_success is not None:
            exec_success_val = 1 if snapshot.execution_success else 0
        need_refs_json = json.dumps(list(snapshot.need_refs))
        projection_refs_json = json.dumps(list(snapshot.projection_refs))

        with self._connection() as conn:
            conn.execute("""
                INSERT INTO decision_snapshots (
                    storage_id, topic_id, pattern_name, complexity,
                    option_count, evaluation_score, decided_at, status,
                    stored_at, rationale, selected_option_id,
                    execution_id, execution_success, transaction_id,
                    trace_id, need_refs_json, projection_refs_json,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                storage_id, snapshot.topic_id, snapshot.pattern_name,
                snapshot.complexity, snapshot.option_count,
                snapshot.evaluation_score, snapshot.decided_at,
                snapshot.status.value, now, snapshot.rationale,
                snapshot.selected_option_id,
                snapshot.execution_id, exec_success_val,
                snapshot.transaction_id, snapshot.trace_id,
                need_refs_json, projection_refs_json, metadata_json,
            ))
            conn.commit()

        return stored

    def get(self, storage_id: str) -> StoredDecisionSnapshot | None:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM decision_snapshots WHERE storage_id = ?",
                (storage_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_snapshot(row)

    def query(
        self, options: DecisionQueryOptions | None = None,
    ) -> tuple[StoredDecisionSnapshot, ...]:
        query = "SELECT * FROM decision_snapshots"
        conditions, params = self._build_where_conditions(options)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY decided_at DESC"

        if options:
            query += f" LIMIT {options.limit} OFFSET {options.offset}"

        with self._connection() as conn:
            cursor = conn.execute(query, params)
            return tuple(self._row_to_snapshot(row) for row in cursor.fetchall())

    def count(self, options: DecisionQueryOptions | None = None) -> int:
        query = "SELECT COUNT(*) FROM decision_snapshots"
        conditions, params = self._build_where_conditions(options)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        with self._connection() as conn:
            cursor = conn.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result else 0

    @staticmethod
    def _build_where_conditions(
        options: DecisionQueryOptions | None,
    ) -> tuple[list[str], list[str | int]]:
        """Build WHERE clause conditions and params from query options."""
        conditions: list[str] = []
        params: list[str | int] = []
        if options is None:
            return conditions, params
        if options.pattern_name:
            conditions.append("pattern_name = ?")
            params.append(options.pattern_name)
        if options.complexity:
            conditions.append("complexity = ?")
            params.append(options.complexity)
        if options.status is not None:
            conditions.append("status = ?")
            params.append(options.status.value)
        if options.start_time:
            conditions.append("decided_at >= ?")
            params.append(options.start_time)
        if options.end_time:
            conditions.append("decided_at <= ?")
            params.append(options.end_time)
        if options.trace_id:
            conditions.append("trace_id = ?")
            params.append(options.trace_id)
        if options.need_ref:
            conditions.append("need_refs_json LIKE ?")
            params.append(f'%"{options.need_ref}"%')
        return conditions, params

    def statistics_by_pattern(self) -> tuple[DecisionStatistics, ...]:
        with self._connection() as conn:
            cursor = conn.execute("""
                SELECT
                    pattern_name,
                    COUNT(*) as total_decisions,
                    AVG(option_count) as avg_options,
                    AVG(evaluation_score) as avg_evaluation_score,
                    SUM(CASE WHEN status = 'accepted' THEN 1 ELSE 0 END) as accepted_count
                FROM decision_snapshots
                GROUP BY pattern_name
                ORDER BY total_decisions DESC
            """)

            results: list[DecisionStatistics] = []
            for row in cursor.fetchall():
                total = row["total_decisions"]
                accepted = row["accepted_count"]
                results.append(DecisionStatistics(
                    pattern_name=row["pattern_name"],
                    total_decisions=total,
                    avg_options=row["avg_options"],
                    avg_evaluation_score=row["avg_evaluation_score"],
                    acceptance_rate=accepted / total if total > 0 else 0.0,
                ))

            return tuple(results)

    def _row_to_snapshot(self, row: sqlite3.Row) -> StoredDecisionSnapshot:
        metadata_dict = json.loads(row["metadata_json"])
        metadata = tuple(metadata_dict.items())

        keys = row.keys()
        exec_success_raw = row["execution_success"] if "execution_success" in keys else None
        exec_success: bool | None = None
        if exec_success_raw is not None:
            exec_success = bool(exec_success_raw)

        need_refs_raw = row["need_refs_json"] if "need_refs_json" in keys else "[]"
        need_refs = tuple(json.loads(need_refs_raw))

        projection_refs_raw = row["projection_refs_json"] if "projection_refs_json" in keys else "[]"
        projection_refs = tuple(json.loads(projection_refs_raw))

        return StoredDecisionSnapshot(
            storage_id=row["storage_id"],
            topic_id=row["topic_id"],
            pattern_name=row["pattern_name"],
            complexity=row["complexity"],
            option_count=row["option_count"],
            evaluation_score=row["evaluation_score"],
            decided_at=row["decided_at"],
            status=DecisionSnapshotStatus(row["status"]),
            stored_at=row["stored_at"],
            rationale=row["rationale"],
            selected_option_id=row["selected_option_id"],
            execution_id=row["execution_id"] if "execution_id" in keys else "",
            execution_success=exec_success,
            transaction_id=row["transaction_id"] if "transaction_id" in keys else "",
            trace_id=row["trace_id"] if "trace_id" in keys else "",
            need_refs=need_refs,
            projection_refs=projection_refs,
            metadata=metadata,
        )
