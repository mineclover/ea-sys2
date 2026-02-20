"""Needs Store — S3 Recording for Needs Layer.

Persistent storage for need snapshots with query capabilities.
Provides:
- NeedStore ABC: 저장소 인터페이스
- InMemoryNeedStore: 테스트용 인메모리 구현
- SQLiteNeedStore: SQLite 기반 영속 저장소

References:
- ea_kernel/decision_store.py: S3 Store 3-tier 패턴
- ea_decision/topic_store.py: S3 Store 도메인 번역 패턴
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
# Domain Types — Stored Need Snapshot
# ═══════════════════════════════════════════════════════════════════════════════

class NeedSnapshotStatus(StrEnum):
    """스냅샷 시점의 니즈 상태."""
    DRAFT = "draft"
    EXPRESSED = "expressed"
    ACKNOWLEDGED = "acknowledged"
    ADDRESSED = "addressed"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True)
class StoredNeedSnapshot:
    """완료된 니즈 스냅샷.

    Need의 특정 시점 정보를 불변 레코드로 저장.
    """
    storage_id: str
    need_id: str
    lineage_id: str
    stakeholder_id: str
    status: NeedSnapshotStatus
    priority: str
    complexity: str
    use_case_id: str = ""
    version: int = 1
    expressed_at: str = ""
    stored_at: str = ""
    action: str = ""
    subject: str = ""
    justification_count: int = 0
    kernel_ref_count: int = 0
    decision_ref: str = ""
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class NeedQueryOptions:
    """니즈 조회 옵션."""
    stakeholder_id: str = ""
    status: NeedSnapshotStatus | None = None
    priority: str = ""
    complexity: str = ""
    use_case_id: str = ""
    decision_ref: str = ""
    start_time: str = ""
    end_time: str = ""
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class StakeholderNeedStatistics:
    """이해관계자별 니즈 통계."""
    stakeholder_id: str
    total_needs: int = 0
    addressed_count: int = 0
    withdrawn_count: int = 0
    expressed_count: int = 0
    acknowledged_count: int = 0
    draft_count: int = 0
    avg_justification_count: float = 0.0

    @property
    def addressed_rate(self) -> float:
        if self.total_needs == 0:
            return 0.0
        return self.addressed_count / self.total_needs

    @property
    def withdrawn_rate(self) -> float:
        if self.total_needs == 0:
            return 0.0
        return self.withdrawn_count / self.total_needs


# ═══════════════════════════════════════════════════════════════════════════════
# NeedStore ABC — 저장소 인터페이스
# ═══════════════════════════════════════════════════════════════════════════════

class NeedStore(ABC):
    """Need Store ABC — 니즈 스냅샷 저장소 인터페이스."""

    @abstractmethod
    def store(self, snapshot: StoredNeedSnapshot) -> StoredNeedSnapshot:
        """니즈 스냅샷 저장.

        Args:
            snapshot: 저장할 스냅샷 (storage_id가 비어있으면 자동 생성)

        Returns:
            StoredNeedSnapshot with storage metadata
        """
        ...

    @abstractmethod
    def get(self, storage_id: str) -> StoredNeedSnapshot | None:
        """storage_id로 스냅샷 조회."""
        ...

    @abstractmethod
    def query(
        self, options: NeedQueryOptions | None = None,
    ) -> tuple[StoredNeedSnapshot, ...]:
        """조건부 조회."""
        ...

    @abstractmethod
    def count(self, options: NeedQueryOptions | None = None) -> int:
        """조건에 맞는 레코드 수."""
        ...

    @abstractmethod
    def statistics_by_stakeholder(self) -> tuple[StakeholderNeedStatistics, ...]:
        """이해관계자별 통계."""
        ...


# ═══════════════════════════════════════════════════════════════════════════════
# InMemoryNeedStore — 테스트용 인메모리 구현
# ═══════════════════════════════════════════════════════════════════════════════

class InMemoryNeedStore(NeedStore):
    """In-memory Need Store for testing."""

    __slots__ = ("_records", "_by_stakeholder")

    def __init__(self) -> None:
        self._records: dict[str, StoredNeedSnapshot] = {}
        self._by_stakeholder: dict[str, list[StoredNeedSnapshot]] = {}

    def store(self, snapshot: StoredNeedSnapshot) -> StoredNeedSnapshot:
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        storage_id = snapshot.storage_id or str(uuid.uuid4())

        stored = StoredNeedSnapshot(
            storage_id=storage_id,
            need_id=snapshot.need_id,
            lineage_id=snapshot.lineage_id,
            stakeholder_id=snapshot.stakeholder_id,
            status=snapshot.status,
            priority=snapshot.priority,
            complexity=snapshot.complexity,
            use_case_id=snapshot.use_case_id,
            version=snapshot.version,
            expressed_at=snapshot.expressed_at,
            stored_at=now,
            action=snapshot.action,
            subject=snapshot.subject,
            justification_count=snapshot.justification_count,
            kernel_ref_count=snapshot.kernel_ref_count,
            decision_ref=snapshot.decision_ref,
            metadata=snapshot.metadata,
        )

        self._records[storage_id] = stored
        self._by_stakeholder.setdefault(
            snapshot.stakeholder_id, [],
        ).append(stored)
        return stored

    def get(self, storage_id: str) -> StoredNeedSnapshot | None:
        return self._records.get(storage_id)

    def query(
        self, options: NeedQueryOptions | None = None,
    ) -> tuple[StoredNeedSnapshot, ...]:
        if options is None:
            return tuple(self._records.values())
        return tuple(self._filter_records(options))

    def count(self, options: NeedQueryOptions | None = None) -> int:
        if options is None:
            return len(self._records)
        return len(self._filter_records(options))

    def statistics_by_stakeholder(self) -> tuple[StakeholderNeedStatistics, ...]:
        results: list[StakeholderNeedStatistics] = []

        for stakeholder_id, records in self._by_stakeholder.items():
            if not records:
                continue

            total = len(records)
            addressed = sum(
                1 for r in records
                if r.status == NeedSnapshotStatus.ADDRESSED
            )
            withdrawn = sum(
                1 for r in records
                if r.status == NeedSnapshotStatus.WITHDRAWN
            )
            expressed = sum(
                1 for r in records
                if r.status == NeedSnapshotStatus.EXPRESSED
            )
            acknowledged = sum(
                1 for r in records
                if r.status == NeedSnapshotStatus.ACKNOWLEDGED
            )
            draft = sum(
                1 for r in records
                if r.status == NeedSnapshotStatus.DRAFT
            )
            avg_justifications = (
                sum(r.justification_count for r in records) / total
            )

            results.append(StakeholderNeedStatistics(
                stakeholder_id=stakeholder_id,
                total_needs=total,
                addressed_count=addressed,
                withdrawn_count=withdrawn,
                expressed_count=expressed,
                acknowledged_count=acknowledged,
                draft_count=draft,
                avg_justification_count=avg_justifications,
            ))

        return tuple(sorted(results, key=lambda s: -s.total_needs))

    def _filter_records(
        self, options: NeedQueryOptions,
    ) -> list[StoredNeedSnapshot]:
        if options.stakeholder_id:
            candidates = self._by_stakeholder.get(
                options.stakeholder_id, [],
            )
        else:
            candidates = list(self._records.values())

        results: list[StoredNeedSnapshot] = []
        for snap in candidates:
            if options.status is not None and snap.status != options.status:
                continue
            if options.priority and snap.priority != options.priority:
                continue
            if options.complexity and snap.complexity != options.complexity:
                continue
            if options.use_case_id and snap.use_case_id != options.use_case_id:
                continue
            if options.decision_ref and snap.decision_ref != options.decision_ref:
                continue
            if options.start_time and snap.expressed_at < options.start_time:
                continue
            if options.end_time and snap.expressed_at > options.end_time:
                continue
            results.append(snap)

        start = options.offset
        end = options.offset + options.limit
        return results[start:end]


# ═══════════════════════════════════════════════════════════════════════════════
# SQLiteNeedStore — SQLite 기반 영속 저장소
# ═══════════════════════════════════════════════════════════════════════════════

class SQLiteNeedStore(NeedStore):
    """SQLite-backed Need Store for persistent storage."""

    __slots__ = ("_db_path",)

    _SCHEMA_VERSION = 2

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

                CREATE TABLE IF NOT EXISTS need_snapshots (
                    storage_id TEXT PRIMARY KEY,
                    need_id TEXT NOT NULL,
                    lineage_id TEXT NOT NULL,
                    stakeholder_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    complexity TEXT NOT NULL,
                    use_case_id TEXT DEFAULT '',
                    version INTEGER NOT NULL,
                    expressed_at TEXT DEFAULT '',
                    stored_at TEXT NOT NULL,
                    action TEXT DEFAULT '',
                    subject TEXT DEFAULT '',
                    justification_count INTEGER DEFAULT 0,
                    kernel_ref_count INTEGER DEFAULT 0,
                    decision_ref TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_stakeholder_id
                    ON need_snapshots(stakeholder_id);
                CREATE INDEX IF NOT EXISTS idx_status
                    ON need_snapshots(status);
                CREATE INDEX IF NOT EXISTS idx_priority
                    ON need_snapshots(priority);
                CREATE INDEX IF NOT EXISTS idx_complexity
                    ON need_snapshots(complexity);
                CREATE INDEX IF NOT EXISTS idx_use_case_id
                    ON need_snapshots(use_case_id);
                CREATE INDEX IF NOT EXISTS idx_expressed_at
                    ON need_snapshots(expressed_at);
                CREATE INDEX IF NOT EXISTS idx_decision_ref
                    ON need_snapshots(decision_ref);
            """)

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

    def store(self, snapshot: StoredNeedSnapshot) -> StoredNeedSnapshot:
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        storage_id = snapshot.storage_id or str(uuid.uuid4())
        metadata_json = json.dumps(dict(snapshot.metadata))

        stored = StoredNeedSnapshot(
            storage_id=storage_id,
            need_id=snapshot.need_id,
            lineage_id=snapshot.lineage_id,
            stakeholder_id=snapshot.stakeholder_id,
            status=snapshot.status,
            priority=snapshot.priority,
            complexity=snapshot.complexity,
            use_case_id=snapshot.use_case_id,
            version=snapshot.version,
            expressed_at=snapshot.expressed_at,
            stored_at=now,
            action=snapshot.action,
            subject=snapshot.subject,
            justification_count=snapshot.justification_count,
            kernel_ref_count=snapshot.kernel_ref_count,
            decision_ref=snapshot.decision_ref,
            metadata=snapshot.metadata,
        )

        with self._connection() as conn:
            conn.execute("""
                INSERT INTO need_snapshots (
                    storage_id, need_id, lineage_id, stakeholder_id,
                    status, priority, complexity, use_case_id,
                    version, expressed_at, stored_at,
                    action, subject, justification_count,
                    kernel_ref_count, decision_ref, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                storage_id, snapshot.need_id, snapshot.lineage_id,
                snapshot.stakeholder_id, snapshot.status.value,
                snapshot.priority, snapshot.complexity,
                snapshot.use_case_id, snapshot.version,
                snapshot.expressed_at, now,
                snapshot.action, snapshot.subject,
                snapshot.justification_count, snapshot.kernel_ref_count,
                snapshot.decision_ref, metadata_json,
            ))
            conn.commit()

        return stored

    def get(self, storage_id: str) -> StoredNeedSnapshot | None:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM need_snapshots WHERE storage_id = ?",
                (storage_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_snapshot(row)

    @staticmethod
    def _build_where_conditions(
        options: NeedQueryOptions,
    ) -> tuple[list[str], list[str | int]]:
        conditions: list[str] = []
        params: list[str | int] = []

        if options.stakeholder_id:
            conditions.append("stakeholder_id = ?")
            params.append(options.stakeholder_id)
        if options.status is not None:
            conditions.append("status = ?")
            params.append(options.status.value)
        if options.priority:
            conditions.append("priority = ?")
            params.append(options.priority)
        if options.complexity:
            conditions.append("complexity = ?")
            params.append(options.complexity)
        if options.use_case_id:
            conditions.append("use_case_id = ?")
            params.append(options.use_case_id)
        if options.decision_ref:
            conditions.append("decision_ref = ?")
            params.append(options.decision_ref)
        if options.start_time:
            conditions.append("expressed_at >= ?")
            params.append(options.start_time)
        if options.end_time:
            conditions.append("expressed_at <= ?")
            params.append(options.end_time)

        return conditions, params

    def query(
        self, options: NeedQueryOptions | None = None,
    ) -> tuple[StoredNeedSnapshot, ...]:
        query = "SELECT * FROM need_snapshots"
        params: list[str | int] = []

        if options:
            conditions, params = self._build_where_conditions(options)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY expressed_at DESC"

        if options:
            query += f" LIMIT {options.limit} OFFSET {options.offset}"

        with self._connection() as conn:
            cursor = conn.execute(query, params)
            return tuple(
                self._row_to_snapshot(row) for row in cursor.fetchall()
            )

    def count(self, options: NeedQueryOptions | None = None) -> int:
        query = "SELECT COUNT(*) FROM need_snapshots"
        params: list[str | int] = []

        if options:
            conditions, params = self._build_where_conditions(options)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        with self._connection() as conn:
            cursor = conn.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result else 0

    def statistics_by_stakeholder(
        self,
    ) -> tuple[StakeholderNeedStatistics, ...]:
        with self._connection() as conn:
            cursor = conn.execute("""
                SELECT
                    stakeholder_id,
                    COUNT(*) as total_needs,
                    SUM(CASE WHEN status = 'addressed'
                        THEN 1 ELSE 0 END) as addressed_count,
                    SUM(CASE WHEN status = 'withdrawn'
                        THEN 1 ELSE 0 END) as withdrawn_count,
                    SUM(CASE WHEN status = 'expressed'
                        THEN 1 ELSE 0 END) as expressed_count,
                    SUM(CASE WHEN status = 'acknowledged'
                        THEN 1 ELSE 0 END) as acknowledged_count,
                    SUM(CASE WHEN status = 'draft'
                        THEN 1 ELSE 0 END) as draft_count,
                    AVG(justification_count) as avg_justification_count
                FROM need_snapshots
                GROUP BY stakeholder_id
                ORDER BY total_needs DESC
            """)

            results: list[StakeholderNeedStatistics] = []
            for row in cursor.fetchall():
                results.append(StakeholderNeedStatistics(
                    stakeholder_id=row["stakeholder_id"],
                    total_needs=row["total_needs"],
                    addressed_count=row["addressed_count"],
                    withdrawn_count=row["withdrawn_count"],
                    expressed_count=row["expressed_count"],
                    acknowledged_count=row["acknowledged_count"],
                    draft_count=row["draft_count"],
                    avg_justification_count=row["avg_justification_count"],
                ))

            return tuple(results)

    def _row_to_snapshot(self, row: sqlite3.Row) -> StoredNeedSnapshot:
        metadata_dict = json.loads(row["metadata_json"])
        metadata = tuple(metadata_dict.items())

        return StoredNeedSnapshot(
            storage_id=row["storage_id"],
            need_id=row["need_id"],
            lineage_id=row["lineage_id"],
            stakeholder_id=row["stakeholder_id"],
            status=NeedSnapshotStatus(row["status"]),
            priority=row["priority"],
            complexity=row["complexity"],
            use_case_id=row["use_case_id"],
            version=row["version"],
            expressed_at=row["expressed_at"],
            stored_at=row["stored_at"],
            action=row["action"],
            subject=row["subject"],
            justification_count=row["justification_count"],
            kernel_ref_count=row["kernel_ref_count"],
            decision_ref=row["decision_ref"],
            metadata=metadata,
        )
