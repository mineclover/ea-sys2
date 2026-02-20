"""Projection Store — S3 Recording for Projection Layer.

Persistent storage for projection snapshots with query capabilities.
Provides:
- ProjectionStore ABC: 저장소 인터페이스
- InMemoryProjectionStore: 테스트용 인메모리 구현
- SQLiteProjectionStore: SQLite 기반 영속 저장소

References:
- ea_needs/needs_store.py: S3 Store 3-tier 패턴
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
# Domain Types — Stored Projection Snapshot
# ═══════════════════════════════════════════════════════════════════════════════

class ProjectionSnapshotStatus(StrEnum):
    """스냅샷 시점의 프로젝션 상태."""
    PROJECTED = "projected"
    STALE = "stale"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class StoredProjectionSnapshot:
    """완료된 프로젝션 스냅샷.

    프로젝션 실행 결과의 특정 시점 정보를 불변 레코드로 저장.
    """
    storage_id: str
    profile_name: str
    level: str
    lens: str
    node_count: int
    edge_count: int

    status: ProjectionSnapshotStatus = ProjectionSnapshotStatus.PROJECTED

    # Optional exploration axes
    tier: str = ""
    seed: str = ""

    # Filter statistics
    filter_node_input: int = 0
    filter_node_output: int = 0
    filter_edge_input: int = 0
    filter_edge_output: int = 0

    # Timing
    projected_at: str = ""
    stored_at: str = ""
    duration_ms: int = 0

    # Cross-layer references
    decision_ref: str = ""
    trace_id: str = ""

    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ProjectionQueryOptions:
    """프로젝션 조회 옵션."""
    profile_name: str = ""
    level: str = ""
    lens: str = ""
    tier: str = ""
    seed: str = ""
    status: ProjectionSnapshotStatus | None = None
    start_time: str = ""
    end_time: str = ""
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class LevelProjectionStatistics:
    """레벨별 프로젝션 통계."""
    level: str
    total_projections: int = 0
    avg_node_count: float = 0.0
    avg_edge_count: float = 0.0
    min_node_count: int = 0
    max_node_count: int = 0
    min_edge_count: int = 0
    max_edge_count: int = 0
    stale_count: int = 0

    @property
    def stale_rate(self) -> float:
        if self.total_projections == 0:
            return 0.0
        return self.stale_count / self.total_projections

    @property
    def node_range(self) -> int:
        return self.max_node_count - self.min_node_count

    @property
    def edge_range(self) -> int:
        return self.max_edge_count - self.min_edge_count


# ═══════════════════════════════════════════════════════════════════════════════
# ProjectionStore ABC — 저장소 인터페이스
# ═══════════════════════════════════════════════════════════════════════════════

class ProjectionStore(ABC):
    """Projection Store ABC — 프로젝션 스냅샷 저장소 인터페이스."""

    @abstractmethod
    def store(self, snapshot: StoredProjectionSnapshot) -> StoredProjectionSnapshot:
        """프로젝션 스냅샷 저장.

        Args:
            snapshot: 저장할 스냅샷 (storage_id가 비어있으면 자동 생성)

        Returns:
            StoredProjectionSnapshot with storage metadata
        """
        ...

    @abstractmethod
    def get(self, storage_id: str) -> StoredProjectionSnapshot | None:
        """storage_id로 스냅샷 조회."""
        ...

    @abstractmethod
    def query(
        self, options: ProjectionQueryOptions | None = None,
    ) -> tuple[StoredProjectionSnapshot, ...]:
        """조건부 조회."""
        ...

    @abstractmethod
    def count(self, options: ProjectionQueryOptions | None = None) -> int:
        """조건에 맞는 레코드 수."""
        ...

    @abstractmethod
    def statistics_by_level(self) -> tuple[LevelProjectionStatistics, ...]:
        """레벨별 통계."""
        ...


# ═══════════════════════════════════════════════════════════════════════════════
# InMemoryProjectionStore — 테스트용 인메모리 구현
# ═══════════════════════════════════════════════════════════════════════════════

class InMemoryProjectionStore(ProjectionStore):
    """In-memory Projection Store for testing."""

    __slots__ = ("_records", "_by_level")

    def __init__(self) -> None:
        self._records: dict[str, StoredProjectionSnapshot] = {}
        self._by_level: dict[str, list[StoredProjectionSnapshot]] = {}

    def store(self, snapshot: StoredProjectionSnapshot) -> StoredProjectionSnapshot:
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        storage_id = snapshot.storage_id or str(uuid.uuid4())

        stored = StoredProjectionSnapshot(
            storage_id=storage_id,
            profile_name=snapshot.profile_name,
            level=snapshot.level,
            lens=snapshot.lens,
            node_count=snapshot.node_count,
            edge_count=snapshot.edge_count,
            status=snapshot.status,
            tier=snapshot.tier,
            seed=snapshot.seed,
            filter_node_input=snapshot.filter_node_input,
            filter_node_output=snapshot.filter_node_output,
            filter_edge_input=snapshot.filter_edge_input,
            filter_edge_output=snapshot.filter_edge_output,
            projected_at=snapshot.projected_at,
            stored_at=now,
            duration_ms=snapshot.duration_ms,
            decision_ref=snapshot.decision_ref,
            trace_id=snapshot.trace_id,
            metadata=snapshot.metadata,
        )

        self._records[storage_id] = stored
        self._by_level.setdefault(snapshot.level, []).append(stored)
        return stored

    def get(self, storage_id: str) -> StoredProjectionSnapshot | None:
        return self._records.get(storage_id)

    def query(
        self, options: ProjectionQueryOptions | None = None,
    ) -> tuple[StoredProjectionSnapshot, ...]:
        if options is None:
            return tuple(self._records.values())
        return tuple(self._filter_records(options))

    def count(self, options: ProjectionQueryOptions | None = None) -> int:
        if options is None:
            return len(self._records)
        return len(self._filter_records(options))

    def statistics_by_level(self) -> tuple[LevelProjectionStatistics, ...]:
        results: list[LevelProjectionStatistics] = []

        for level, records in self._by_level.items():
            if not records:
                continue

            total = len(records)
            node_counts = [r.node_count for r in records]
            edge_counts = [r.edge_count for r in records]
            stale = sum(
                1 for r in records
                if r.status == ProjectionSnapshotStatus.STALE
            )

            results.append(LevelProjectionStatistics(
                level=level,
                total_projections=total,
                avg_node_count=sum(node_counts) / total,
                avg_edge_count=sum(edge_counts) / total,
                min_node_count=min(node_counts),
                max_node_count=max(node_counts),
                min_edge_count=min(edge_counts),
                max_edge_count=max(edge_counts),
                stale_count=stale,
            ))

        return tuple(sorted(results, key=lambda s: s.level))

    def _filter_records(
        self, options: ProjectionQueryOptions,
    ) -> list[StoredProjectionSnapshot]:
        if options.level:
            candidates = self._by_level.get(options.level, [])
        else:
            candidates = list(self._records.values())

        results: list[StoredProjectionSnapshot] = []
        for snap in candidates:
            if options.profile_name and snap.profile_name != options.profile_name:
                continue
            if options.lens and snap.lens != options.lens:
                continue
            if options.tier and snap.tier != options.tier:
                continue
            if options.seed and snap.seed != options.seed:
                continue
            if options.status is not None and snap.status != options.status:
                continue
            if options.start_time and snap.projected_at < options.start_time:
                continue
            if options.end_time and snap.projected_at > options.end_time:
                continue
            results.append(snap)

        start = options.offset
        end = options.offset + options.limit
        return results[start:end]


# ═══════════════════════════════════════════════════════════════════════════════
# SQLiteProjectionStore — SQLite 기반 영속 저장소
# ═══════════════════════════════════════════════════════════════════════════════

class SQLiteProjectionStore(ProjectionStore):
    """SQLite-backed Projection Store for persistent storage."""

    __slots__ = ("_db_path",)

    _SCHEMA_VERSION = 1

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

                CREATE TABLE IF NOT EXISTS projection_snapshots (
                    storage_id TEXT PRIMARY KEY,
                    profile_name TEXT NOT NULL,
                    level TEXT NOT NULL,
                    lens TEXT NOT NULL,
                    node_count INTEGER NOT NULL,
                    edge_count INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'projected',
                    tier TEXT DEFAULT '',
                    seed TEXT DEFAULT '',
                    filter_node_input INTEGER DEFAULT 0,
                    filter_node_output INTEGER DEFAULT 0,
                    filter_edge_input INTEGER DEFAULT 0,
                    filter_edge_output INTEGER DEFAULT 0,
                    projected_at TEXT DEFAULT '',
                    stored_at TEXT NOT NULL,
                    duration_ms INTEGER DEFAULT 0,
                    decision_ref TEXT DEFAULT '',
                    trace_id TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_profile_name
                    ON projection_snapshots(profile_name);
                CREATE INDEX IF NOT EXISTS idx_level
                    ON projection_snapshots(level);
                CREATE INDEX IF NOT EXISTS idx_lens
                    ON projection_snapshots(lens);
                CREATE INDEX IF NOT EXISTS idx_tier
                    ON projection_snapshots(tier);
                CREATE INDEX IF NOT EXISTS idx_status
                    ON projection_snapshots(status);
                CREATE INDEX IF NOT EXISTS idx_projected_at
                    ON projection_snapshots(projected_at);
            """)

            cursor = conn.execute("SELECT version FROM schema_version")
            if cursor.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (self._SCHEMA_VERSION,),
                )

            conn.commit()

    def store(self, snapshot: StoredProjectionSnapshot) -> StoredProjectionSnapshot:
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        storage_id = snapshot.storage_id or str(uuid.uuid4())
        metadata_json = json.dumps(dict(snapshot.metadata))

        stored = StoredProjectionSnapshot(
            storage_id=storage_id,
            profile_name=snapshot.profile_name,
            level=snapshot.level,
            lens=snapshot.lens,
            node_count=snapshot.node_count,
            edge_count=snapshot.edge_count,
            status=snapshot.status,
            tier=snapshot.tier,
            seed=snapshot.seed,
            filter_node_input=snapshot.filter_node_input,
            filter_node_output=snapshot.filter_node_output,
            filter_edge_input=snapshot.filter_edge_input,
            filter_edge_output=snapshot.filter_edge_output,
            projected_at=snapshot.projected_at,
            stored_at=now,
            duration_ms=snapshot.duration_ms,
            decision_ref=snapshot.decision_ref,
            trace_id=snapshot.trace_id,
            metadata=snapshot.metadata,
        )

        with self._connection() as conn:
            conn.execute("""
                INSERT INTO projection_snapshots (
                    storage_id, profile_name, level, lens,
                    node_count, edge_count, status,
                    tier, seed,
                    filter_node_input, filter_node_output,
                    filter_edge_input, filter_edge_output,
                    projected_at, stored_at, duration_ms,
                    decision_ref, trace_id, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                storage_id, snapshot.profile_name, snapshot.level,
                snapshot.lens, snapshot.node_count, snapshot.edge_count,
                snapshot.status.value,
                snapshot.tier, snapshot.seed,
                snapshot.filter_node_input, snapshot.filter_node_output,
                snapshot.filter_edge_input, snapshot.filter_edge_output,
                snapshot.projected_at, now, snapshot.duration_ms,
                snapshot.decision_ref, snapshot.trace_id, metadata_json,
            ))
            conn.commit()

        return stored

    def get(self, storage_id: str) -> StoredProjectionSnapshot | None:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM projection_snapshots WHERE storage_id = ?",
                (storage_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_snapshot(row)

    def query(
        self, options: ProjectionQueryOptions | None = None,
    ) -> tuple[StoredProjectionSnapshot, ...]:
        query = "SELECT * FROM projection_snapshots"
        params: list[str | int] = []
        conditions: list[str] = []

        if options:
            if options.profile_name:
                conditions.append("profile_name = ?")
                params.append(options.profile_name)
            if options.level:
                conditions.append("level = ?")
                params.append(options.level)
            if options.lens:
                conditions.append("lens = ?")
                params.append(options.lens)
            if options.tier:
                conditions.append("tier = ?")
                params.append(options.tier)
            if options.seed:
                conditions.append("seed = ?")
                params.append(options.seed)
            if options.status is not None:
                conditions.append("status = ?")
                params.append(options.status.value)
            if options.start_time:
                conditions.append("projected_at >= ?")
                params.append(options.start_time)
            if options.end_time:
                conditions.append("projected_at <= ?")
                params.append(options.end_time)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY projected_at DESC"

        if options:
            query += f" LIMIT {options.limit} OFFSET {options.offset}"

        with self._connection() as conn:
            cursor = conn.execute(query, params)
            return tuple(
                self._row_to_snapshot(row) for row in cursor.fetchall()
            )

    def count(self, options: ProjectionQueryOptions | None = None) -> int:
        query = "SELECT COUNT(*) FROM projection_snapshots"
        params: list[str | int] = []
        conditions: list[str] = []

        if options:
            if options.profile_name:
                conditions.append("profile_name = ?")
                params.append(options.profile_name)
            if options.level:
                conditions.append("level = ?")
                params.append(options.level)
            if options.lens:
                conditions.append("lens = ?")
                params.append(options.lens)
            if options.tier:
                conditions.append("tier = ?")
                params.append(options.tier)
            if options.seed:
                conditions.append("seed = ?")
                params.append(options.seed)
            if options.status is not None:
                conditions.append("status = ?")
                params.append(options.status.value)
            if options.start_time:
                conditions.append("projected_at >= ?")
                params.append(options.start_time)
            if options.end_time:
                conditions.append("projected_at <= ?")
                params.append(options.end_time)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        with self._connection() as conn:
            cursor = conn.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result else 0

    def statistics_by_level(
        self,
    ) -> tuple[LevelProjectionStatistics, ...]:
        with self._connection() as conn:
            cursor = conn.execute("""
                SELECT
                    level,
                    COUNT(*) as total_projections,
                    AVG(node_count) as avg_node_count,
                    AVG(edge_count) as avg_edge_count,
                    MIN(node_count) as min_node_count,
                    MAX(node_count) as max_node_count,
                    MIN(edge_count) as min_edge_count,
                    MAX(edge_count) as max_edge_count,
                    SUM(CASE WHEN status = 'stale'
                        THEN 1 ELSE 0 END) as stale_count
                FROM projection_snapshots
                GROUP BY level
                ORDER BY level
            """)

            results: list[LevelProjectionStatistics] = []
            for row in cursor.fetchall():
                results.append(LevelProjectionStatistics(
                    level=row["level"],
                    total_projections=row["total_projections"],
                    avg_node_count=row["avg_node_count"],
                    avg_edge_count=row["avg_edge_count"],
                    min_node_count=row["min_node_count"],
                    max_node_count=row["max_node_count"],
                    min_edge_count=row["min_edge_count"],
                    max_edge_count=row["max_edge_count"],
                    stale_count=row["stale_count"],
                ))

            return tuple(results)

    def _row_to_snapshot(self, row: sqlite3.Row) -> StoredProjectionSnapshot:
        metadata_dict = json.loads(row["metadata_json"])
        metadata = tuple(metadata_dict.items())

        return StoredProjectionSnapshot(
            storage_id=row["storage_id"],
            profile_name=row["profile_name"],
            level=row["level"],
            lens=row["lens"],
            node_count=row["node_count"],
            edge_count=row["edge_count"],
            status=ProjectionSnapshotStatus(row["status"]),
            tier=row["tier"],
            seed=row["seed"],
            filter_node_input=row["filter_node_input"],
            filter_node_output=row["filter_node_output"],
            filter_edge_input=row["filter_edge_input"],
            filter_edge_output=row["filter_edge_output"],
            projected_at=row["projected_at"],
            stored_at=row["stored_at"],
            duration_ms=row["duration_ms"],
            decision_ref=row["decision_ref"],
            trace_id=row["trace_id"],
            metadata=metadata,
        )
