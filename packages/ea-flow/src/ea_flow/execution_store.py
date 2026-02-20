"""Execution Store — S3 Recording for Flow Layer.

Persistent storage for workflow execution records with query capabilities.
Provides:
- ExecutionStore ABC: 저장소 인터페이스
- InMemoryExecutionStore: 테스트용 인메모리 구현
- SQLiteExecutionStore: SQLite 기반 영속 저장소

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
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════════
# Domain Types — Stored Execution Record
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class StepResultSummary:
    """개별 스텝 실행 요약."""
    step_name: str
    accepted: bool
    kernel_anchor: str = ""


@dataclass(frozen=True)
class StoredExecutionRecord:
    """워크플로 실행 기록.

    FlowRuntime.interpret() 결과를 불변 레코드로 저장.
    """
    storage_id: str
    workflow_name: str
    success: bool
    total_steps: int
    completed_steps: int
    failed_step: str
    rollback_occurred: bool
    duration_ms: int
    executed_at: str
    stored_at: str = ""
    step_results: tuple[StepResultSummary, ...] = ()
    execution_id: str = ""
    report_id: str = ""
    topic_id: str = ""
    trace_id: str = ""
    workflow_version_id: str = ""
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ExecutionQueryOptions:
    """실행 기록 조회 옵션."""
    workflow_name: str = ""
    success: bool | None = None
    rollback_occurred: bool | None = None
    start_time: str = ""
    end_time: str = ""
    report_id: str = ""
    topic_id: str = ""
    trace_id: str = ""
    workflow_version_id: str = ""
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class WorkflowStatistics:
    """워크플로별 실행 통계."""
    workflow_name: str
    total_executions: int = 0
    success_count: int = 0
    rollback_count: int = 0
    avg_duration_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.success_count / self.total_executions

    @property
    def rollback_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.rollback_count / self.total_executions


# ═══════════════════════════════════════════════════════════════════════════════
# ExecutionStore ABC — 저장소 인터페이스
# ═══════════════════════════════════════════════════════════════════════════════

class ExecutionStore(ABC):
    """Execution Store ABC — 워크플로 실행 기록 저장소 인터페이스."""

    @abstractmethod
    def store(self, record: StoredExecutionRecord) -> StoredExecutionRecord:
        """실행 기록 저장.

        Args:
            record: 저장할 실행 기록 (storage_id가 비어있으면 자동 생성)

        Returns:
            StoredExecutionRecord with storage metadata
        """
        ...

    @abstractmethod
    def get(self, storage_id: str) -> StoredExecutionRecord | None:
        """storage_id로 기록 조회."""
        ...

    @abstractmethod
    def query(
        self, options: ExecutionQueryOptions | None = None,
    ) -> tuple[StoredExecutionRecord, ...]:
        """조건부 조회."""
        ...

    @abstractmethod
    def count(self, options: ExecutionQueryOptions | None = None) -> int:
        """조건에 맞는 레코드 수."""
        ...

    @abstractmethod
    def statistics_by_workflow(self) -> tuple[WorkflowStatistics, ...]:
        """워크플로별 통계."""
        ...


# ═══════════════════════════════════════════════════════════════════════════════
# InMemoryExecutionStore — 테스트용 인메모리 구현
# ═══════════════════════════════════════════════════════════════════════════════

class InMemoryExecutionStore(ExecutionStore):
    """In-memory Execution Store for testing."""

    __slots__ = ("_records", "_by_workflow")

    def __init__(self) -> None:
        self._records: dict[str, StoredExecutionRecord] = {}
        self._by_workflow: dict[str, list[StoredExecutionRecord]] = {}

    def store(self, record: StoredExecutionRecord) -> StoredExecutionRecord:
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        storage_id = record.storage_id or str(uuid.uuid4())

        stored = StoredExecutionRecord(
            storage_id=storage_id,
            workflow_name=record.workflow_name,
            success=record.success,
            total_steps=record.total_steps,
            completed_steps=record.completed_steps,
            failed_step=record.failed_step,
            rollback_occurred=record.rollback_occurred,
            duration_ms=record.duration_ms,
            executed_at=record.executed_at,
            stored_at=now,
            step_results=record.step_results,
            execution_id=record.execution_id,
            report_id=record.report_id,
            topic_id=record.topic_id,
            trace_id=record.trace_id,
            workflow_version_id=record.workflow_version_id,
            metadata=record.metadata,
        )

        self._records[storage_id] = stored
        self._by_workflow.setdefault(record.workflow_name, []).append(stored)
        return stored

    def get(self, storage_id: str) -> StoredExecutionRecord | None:
        return self._records.get(storage_id)

    def query(
        self, options: ExecutionQueryOptions | None = None,
    ) -> tuple[StoredExecutionRecord, ...]:
        if options is None:
            return tuple(self._records.values())
        return tuple(self._filter_records(options))

    def count(self, options: ExecutionQueryOptions | None = None) -> int:
        if options is None:
            return len(self._records)
        return len(self._filter_records(options))

    def statistics_by_workflow(self) -> tuple[WorkflowStatistics, ...]:
        results: list[WorkflowStatistics] = []

        for wf_name, records in self._by_workflow.items():
            if not records:
                continue

            total = len(records)
            success_count = sum(1 for r in records if r.success)
            rollback_count = sum(1 for r in records if r.rollback_occurred)
            avg_duration = sum(r.duration_ms for r in records) / total

            results.append(WorkflowStatistics(
                workflow_name=wf_name,
                total_executions=total,
                success_count=success_count,
                rollback_count=rollback_count,
                avg_duration_ms=avg_duration,
            ))

        return tuple(sorted(results, key=lambda s: -s.total_executions))

    def _filter_records(
        self, options: ExecutionQueryOptions,
    ) -> list[StoredExecutionRecord]:
        if options.workflow_name:
            candidates = self._by_workflow.get(options.workflow_name, [])
        else:
            candidates = list(self._records.values())

        results: list[StoredExecutionRecord] = []
        for rec in candidates:
            if options.success is not None and rec.success != options.success:
                continue
            if (options.rollback_occurred is not None
                    and rec.rollback_occurred != options.rollback_occurred):
                continue
            if options.start_time and rec.executed_at < options.start_time:
                continue
            if options.end_time and rec.executed_at > options.end_time:
                continue
            if options.report_id and rec.report_id != options.report_id:
                continue
            if options.topic_id and rec.topic_id != options.topic_id:
                continue
            if options.trace_id and rec.trace_id != options.trace_id:
                continue
            if options.workflow_version_id and rec.workflow_version_id != options.workflow_version_id:
                continue
            results.append(rec)

        start = options.offset
        end = options.offset + options.limit
        return results[start:end]


# ═══════════════════════════════════════════════════════════════════════════════
# SQLiteExecutionStore — SQLite 기반 영속 저장소
# ═══════════════════════════════════════════════════════════════════════════════

class SQLiteExecutionStore(ExecutionStore):
    """SQLite-backed Execution Store for persistent storage."""

    __slots__ = ("_db_path",)

    _SCHEMA_VERSION = 4

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

                CREATE TABLE IF NOT EXISTS execution_records (
                    storage_id TEXT PRIMARY KEY,
                    workflow_name TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    total_steps INTEGER NOT NULL,
                    completed_steps INTEGER NOT NULL,
                    failed_step TEXT DEFAULT '',
                    rollback_occurred INTEGER NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    executed_at TEXT NOT NULL,
                    stored_at TEXT NOT NULL,
                    step_results_json TEXT DEFAULT '[]',
                    execution_id TEXT DEFAULT '',
                    report_id TEXT DEFAULT '',
                    topic_id TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_workflow_name
                    ON execution_records(workflow_name);
                CREATE INDEX IF NOT EXISTS idx_success
                    ON execution_records(success);
                CREATE INDEX IF NOT EXISTS idx_executed_at
                    ON execution_records(executed_at);
                CREATE INDEX IF NOT EXISTS idx_report_id
                    ON execution_records(report_id);
                CREATE INDEX IF NOT EXISTS idx_topic_id
                    ON execution_records(topic_id);
            """)

            # Migration: add columns for existing databases
            for col, default in (
                ("report_id", "''"), ("topic_id", "''"),
                ("trace_id", "''"), ("workflow_version_id", "''"),
            ):
                try:
                    conn.execute(
                        f"ALTER TABLE execution_records ADD COLUMN {col} TEXT DEFAULT {default}"
                    )
                except sqlite3.OperationalError:
                    pass  # column already exists

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_trace_id ON execution_records(trace_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_workflow_version_id ON execution_records(workflow_version_id)"
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

    def store(self, record: StoredExecutionRecord) -> StoredExecutionRecord:
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        storage_id = record.storage_id or str(uuid.uuid4())

        step_results_json = json.dumps([
            {
                "step_name": sr.step_name,
                "accepted": sr.accepted,
                "kernel_anchor": sr.kernel_anchor,
            }
            for sr in record.step_results
        ])
        metadata_json = json.dumps(dict(record.metadata))

        stored = StoredExecutionRecord(
            storage_id=storage_id,
            workflow_name=record.workflow_name,
            success=record.success,
            total_steps=record.total_steps,
            completed_steps=record.completed_steps,
            failed_step=record.failed_step,
            rollback_occurred=record.rollback_occurred,
            duration_ms=record.duration_ms,
            executed_at=record.executed_at,
            stored_at=now,
            step_results=record.step_results,
            execution_id=record.execution_id,
            report_id=record.report_id,
            topic_id=record.topic_id,
            trace_id=record.trace_id,
            workflow_version_id=record.workflow_version_id,
            metadata=record.metadata,
        )

        with self._connection() as conn:
            conn.execute("""
                INSERT INTO execution_records (
                    storage_id, workflow_name, success, total_steps,
                    completed_steps, failed_step, rollback_occurred,
                    duration_ms, executed_at, stored_at,
                    step_results_json, execution_id,
                    report_id, topic_id, trace_id,
                    workflow_version_id, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                storage_id, record.workflow_name,
                1 if record.success else 0,
                record.total_steps, record.completed_steps,
                record.failed_step,
                1 if record.rollback_occurred else 0,
                record.duration_ms, record.executed_at, now,
                step_results_json, record.execution_id,
                record.report_id, record.topic_id, record.trace_id,
                record.workflow_version_id, metadata_json,
            ))
            conn.commit()

        return stored

    def get(self, storage_id: str) -> StoredExecutionRecord | None:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM execution_records WHERE storage_id = ?",
                (storage_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_record(row)

    def query(
        self, options: ExecutionQueryOptions | None = None,
    ) -> tuple[StoredExecutionRecord, ...]:
        query = "SELECT * FROM execution_records"
        params: list[str | int] = []
        conditions: list[str] = []

        if options:
            if options.workflow_name:
                conditions.append("workflow_name = ?")
                params.append(options.workflow_name)
            if options.success is not None:
                conditions.append("success = ?")
                params.append(1 if options.success else 0)
            if options.rollback_occurred is not None:
                conditions.append("rollback_occurred = ?")
                params.append(1 if options.rollback_occurred else 0)
            if options.start_time:
                conditions.append("executed_at >= ?")
                params.append(options.start_time)
            if options.end_time:
                conditions.append("executed_at <= ?")
                params.append(options.end_time)
            if options.report_id:
                conditions.append("report_id = ?")
                params.append(options.report_id)
            if options.topic_id:
                conditions.append("topic_id = ?")
                params.append(options.topic_id)
            if options.trace_id:
                conditions.append("trace_id = ?")
                params.append(options.trace_id)
            if options.workflow_version_id:
                conditions.append("workflow_version_id = ?")
                params.append(options.workflow_version_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY executed_at DESC"

        if options:
            query += f" LIMIT {options.limit} OFFSET {options.offset}"

        with self._connection() as conn:
            cursor = conn.execute(query, params)
            return tuple(self._row_to_record(row) for row in cursor.fetchall())

    def count(self, options: ExecutionQueryOptions | None = None) -> int:
        query = "SELECT COUNT(*) FROM execution_records"
        params: list[str | int] = []
        conditions: list[str] = []

        if options:
            if options.workflow_name:
                conditions.append("workflow_name = ?")
                params.append(options.workflow_name)
            if options.success is not None:
                conditions.append("success = ?")
                params.append(1 if options.success else 0)
            if options.rollback_occurred is not None:
                conditions.append("rollback_occurred = ?")
                params.append(1 if options.rollback_occurred else 0)
            if options.start_time:
                conditions.append("executed_at >= ?")
                params.append(options.start_time)
            if options.end_time:
                conditions.append("executed_at <= ?")
                params.append(options.end_time)
            if options.report_id:
                conditions.append("report_id = ?")
                params.append(options.report_id)
            if options.topic_id:
                conditions.append("topic_id = ?")
                params.append(options.topic_id)
            if options.trace_id:
                conditions.append("trace_id = ?")
                params.append(options.trace_id)
            if options.workflow_version_id:
                conditions.append("workflow_version_id = ?")
                params.append(options.workflow_version_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        with self._connection() as conn:
            cursor = conn.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result else 0

    def statistics_by_workflow(self) -> tuple[WorkflowStatistics, ...]:
        with self._connection() as conn:
            cursor = conn.execute("""
                SELECT
                    workflow_name,
                    COUNT(*) as total_executions,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN rollback_occurred = 1 THEN 1 ELSE 0 END) as rollback_count,
                    AVG(duration_ms) as avg_duration_ms
                FROM execution_records
                GROUP BY workflow_name
                ORDER BY total_executions DESC
            """)

            results: list[WorkflowStatistics] = []
            for row in cursor.fetchall():
                results.append(WorkflowStatistics(
                    workflow_name=row["workflow_name"],
                    total_executions=row["total_executions"],
                    success_count=row["success_count"],
                    rollback_count=row["rollback_count"],
                    avg_duration_ms=row["avg_duration_ms"],
                ))

            return tuple(results)

    def _row_to_record(self, row: sqlite3.Row) -> StoredExecutionRecord:
        step_data = json.loads(row["step_results_json"])
        step_results = tuple(
            StepResultSummary(
                step_name=s["step_name"],
                accepted=s["accepted"],
                kernel_anchor=s.get("kernel_anchor", ""),
            )
            for s in step_data
        )
        metadata_dict = json.loads(row["metadata_json"])
        metadata = tuple(metadata_dict.items())

        return StoredExecutionRecord(
            storage_id=row["storage_id"],
            workflow_name=row["workflow_name"],
            success=bool(row["success"]),
            total_steps=row["total_steps"],
            completed_steps=row["completed_steps"],
            failed_step=row["failed_step"],
            rollback_occurred=bool(row["rollback_occurred"]),
            duration_ms=row["duration_ms"],
            executed_at=row["executed_at"],
            stored_at=row["stored_at"],
            step_results=step_results,
            execution_id=row["execution_id"],
            report_id=row["report_id"] if "report_id" in row.keys() else "",
            topic_id=row["topic_id"] if "topic_id" in row.keys() else "",
            trace_id=row["trace_id"] if "trace_id" in row.keys() else "",
            workflow_version_id=row["workflow_version_id"] if "workflow_version_id" in row.keys() else "",
            metadata=metadata,
        )
