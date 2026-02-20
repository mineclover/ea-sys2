"""Workflow Version Store — Version Management for Flow Layer.

Persistent storage for workflow spec versions with diff capabilities.
Provides:
- WorkflowVersionStore ABC: 버전 저장소 인터페이스
- InMemoryWorkflowVersionStore: 테스트용 인메모리 구현
- SQLiteWorkflowVersionStore: SQLite 기반 영속 저장소

References:
- ea_kernel/corpus_version_store.py: CorpusVersionStore 패턴
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
# Domain Types — Workflow Version
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class StoredStepEntry:
    """버전 내 개별 step 스냅샷."""
    step_name: str
    kernel_anchor: str = ""
    input_schema_hash: str = ""
    output_schema_hash: str = ""
    description: str = ""


@dataclass(frozen=True)
class WorkflowVersionInfo:
    """워크플로 버전 정보."""
    version_id: str
    workflow_name: str
    step_count: int
    created_at: str = ""
    parent_version_id: str = ""
    description: str = ""
    step_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowVersionQueryOptions:
    """워크플로 버전 조회 옵션."""
    workflow_name: str = ""
    start_time: str = ""
    end_time: str = ""
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class WorkflowVersionDiff:
    """두 버전 간 차이."""
    added: tuple[str, ...]
    removed: tuple[str, ...]
    modified: tuple[str, ...]


# ═══════════════════════════════════════════════════════════════════════════════
# WorkflowVersionStore ABC — 저장소 인터페이스
# ═══════════════════════════════════════════════════════════════════════════════

class WorkflowVersionStore(ABC):
    """Workflow Version Store ABC — 워크플로 버전 저장소 인터페이스."""

    @abstractmethod
    def create_version(
        self,
        workflow_name: str,
        step_entries: tuple[StoredStepEntry, ...],
        description: str = "",
        parent_version_id: str = "",
    ) -> WorkflowVersionInfo:
        """새 워크플로 버전 생성."""
        ...

    @abstractmethod
    def get(self, version_id: str) -> WorkflowVersionInfo | None:
        """version_id로 버전 조회."""
        ...

    @abstractmethod
    def get_entries(self, version_id: str) -> tuple[StoredStepEntry, ...]:
        """버전의 step entries 조회."""
        ...

    @abstractmethod
    def get_latest(self, workflow_name: str) -> WorkflowVersionInfo | None:
        """워크플로의 최신 버전 조회."""
        ...

    @abstractmethod
    def query(
        self, options: WorkflowVersionQueryOptions | None = None,
    ) -> tuple[WorkflowVersionInfo, ...]:
        """조건부 조회."""
        ...

    @abstractmethod
    def history(
        self, workflow_name: str, limit: int = 100,
    ) -> tuple[WorkflowVersionInfo, ...]:
        """워크플로 버전 이력 (최신순)."""
        ...

    def diff(
        self, from_version_id: str, to_version_id: str,
    ) -> WorkflowVersionDiff:
        """두 버전 간 step name 기준 차이 계산."""
        from_entries = self.get_entries(from_version_id)
        to_entries = self.get_entries(to_version_id)

        from_map = {e.step_name: e for e in from_entries}
        to_map = {e.step_name: e for e in to_entries}

        from_names = set(from_map)
        to_names = set(to_map)

        added = tuple(sorted(to_names - from_names))
        removed = tuple(sorted(from_names - to_names))

        modified: list[str] = []
        for name in sorted(from_names & to_names):
            f = from_map[name]
            t = to_map[name]
            if (f.kernel_anchor != t.kernel_anchor
                    or f.input_schema_hash != t.input_schema_hash
                    or f.output_schema_hash != t.output_schema_hash):
                modified.append(name)

        return WorkflowVersionDiff(
            added=added,
            removed=removed,
            modified=tuple(modified),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# InMemoryWorkflowVersionStore — 테스트용 인메모리 구현
# ═══════════════════════════════════════════════════════════════════════════════

class InMemoryWorkflowVersionStore(WorkflowVersionStore):
    """In-memory Workflow Version Store for testing."""

    __slots__ = ("_versions", "_entries", "_by_workflow")

    def __init__(self) -> None:
        self._versions: dict[str, WorkflowVersionInfo] = {}
        self._entries: dict[str, tuple[StoredStepEntry, ...]] = {}
        self._by_workflow: dict[str, list[WorkflowVersionInfo]] = {}

    def create_version(
        self,
        workflow_name: str,
        step_entries: tuple[StoredStepEntry, ...],
        description: str = "",
        parent_version_id: str = "",
    ) -> WorkflowVersionInfo:
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        version_id = str(uuid.uuid4())

        info = WorkflowVersionInfo(
            version_id=version_id,
            workflow_name=workflow_name,
            step_count=len(step_entries),
            created_at=now,
            parent_version_id=parent_version_id,
            description=description,
            step_names=tuple(e.step_name for e in step_entries),
        )

        self._versions[version_id] = info
        self._entries[version_id] = step_entries
        self._by_workflow.setdefault(workflow_name, []).append(info)
        return info

    def get(self, version_id: str) -> WorkflowVersionInfo | None:
        return self._versions.get(version_id)

    def get_entries(self, version_id: str) -> tuple[StoredStepEntry, ...]:
        return self._entries.get(version_id, ())

    def get_latest(self, workflow_name: str) -> WorkflowVersionInfo | None:
        versions = self._by_workflow.get(workflow_name, [])
        if not versions:
            return None
        return versions[-1]

    def query(
        self, options: WorkflowVersionQueryOptions | None = None,
    ) -> tuple[WorkflowVersionInfo, ...]:
        if options is None:
            return tuple(self._versions.values())

        candidates = list(self._versions.values())
        results: list[WorkflowVersionInfo] = []

        for v in candidates:
            if options.workflow_name and v.workflow_name != options.workflow_name:
                continue
            if options.start_time and v.created_at < options.start_time:
                continue
            if options.end_time and v.created_at > options.end_time:
                continue
            results.append(v)

        results.sort(key=lambda x: x.created_at, reverse=True)
        start = options.offset
        end = options.offset + options.limit
        return tuple(results[start:end])

    def history(
        self, workflow_name: str, limit: int = 100,
    ) -> tuple[WorkflowVersionInfo, ...]:
        versions = self._by_workflow.get(workflow_name, [])
        return tuple(reversed(versions[-limit:]))


# ═══════════════════════════════════════════════════════════════════════════════
# SQLiteWorkflowVersionStore — SQLite 기반 영속 저장소
# ═══════════════════════════════════════════════════════════════════════════════

class SQLiteWorkflowVersionStore(WorkflowVersionStore):
    """SQLite-backed Workflow Version Store for persistent storage."""

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

                CREATE TABLE IF NOT EXISTS workflow_versions (
                    version_id TEXT PRIMARY KEY,
                    workflow_name TEXT NOT NULL,
                    step_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    parent_version_id TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    step_names_json TEXT DEFAULT '[]'
                );

                CREATE TABLE IF NOT EXISTS version_step_entries (
                    version_id TEXT NOT NULL,
                    step_name TEXT NOT NULL,
                    kernel_anchor TEXT DEFAULT '',
                    input_schema_hash TEXT DEFAULT '',
                    output_schema_hash TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    PRIMARY KEY (version_id, step_name),
                    FOREIGN KEY (version_id) REFERENCES workflow_versions(version_id)
                );

                CREATE INDEX IF NOT EXISTS idx_wv_workflow_name
                    ON workflow_versions(workflow_name);
                CREATE INDEX IF NOT EXISTS idx_wv_created_at
                    ON workflow_versions(created_at);
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

    def create_version(
        self,
        workflow_name: str,
        step_entries: tuple[StoredStepEntry, ...],
        description: str = "",
        parent_version_id: str = "",
    ) -> WorkflowVersionInfo:
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        version_id = str(uuid.uuid4())
        step_names = tuple(e.step_name for e in step_entries)
        step_names_json = json.dumps(step_names)

        info = WorkflowVersionInfo(
            version_id=version_id,
            workflow_name=workflow_name,
            step_count=len(step_entries),
            created_at=now,
            parent_version_id=parent_version_id,
            description=description,
            step_names=step_names,
        )

        with self._connection() as conn:
            conn.execute("""
                INSERT INTO workflow_versions (
                    version_id, workflow_name, step_count, created_at,
                    parent_version_id, description, step_names_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                version_id, workflow_name, len(step_entries), now,
                parent_version_id, description, step_names_json,
            ))

            for entry in step_entries:
                conn.execute("""
                    INSERT INTO version_step_entries (
                        version_id, step_name, kernel_anchor,
                        input_schema_hash, output_schema_hash, description
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    version_id, entry.step_name, entry.kernel_anchor,
                    entry.input_schema_hash, entry.output_schema_hash,
                    entry.description,
                ))

            conn.commit()

        return info

    def get(self, version_id: str) -> WorkflowVersionInfo | None:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_versions WHERE version_id = ?",
                (version_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_info(row)

    def get_entries(self, version_id: str) -> tuple[StoredStepEntry, ...]:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM version_step_entries WHERE version_id = ?",
                (version_id,),
            )
            return tuple(
                StoredStepEntry(
                    step_name=row["step_name"],
                    kernel_anchor=row["kernel_anchor"],
                    input_schema_hash=row["input_schema_hash"],
                    output_schema_hash=row["output_schema_hash"],
                    description=row["description"],
                )
                for row in cursor.fetchall()
            )

    def get_latest(self, workflow_name: str) -> WorkflowVersionInfo | None:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_versions WHERE workflow_name = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (workflow_name,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_info(row)

    def query(
        self, options: WorkflowVersionQueryOptions | None = None,
    ) -> tuple[WorkflowVersionInfo, ...]:
        query = "SELECT * FROM workflow_versions"
        params: list[str | int] = []
        conditions: list[str] = []

        if options:
            if options.workflow_name:
                conditions.append("workflow_name = ?")
                params.append(options.workflow_name)
            if options.start_time:
                conditions.append("created_at >= ?")
                params.append(options.start_time)
            if options.end_time:
                conditions.append("created_at <= ?")
                params.append(options.end_time)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC"

        if options:
            query += f" LIMIT {options.limit} OFFSET {options.offset}"

        with self._connection() as conn:
            cursor = conn.execute(query, params)
            return tuple(
                self._row_to_info(row) for row in cursor.fetchall()
            )

    def history(
        self, workflow_name: str, limit: int = 100,
    ) -> tuple[WorkflowVersionInfo, ...]:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_versions WHERE workflow_name = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (workflow_name, limit),
            )
            return tuple(
                self._row_to_info(row) for row in cursor.fetchall()
            )

    def _row_to_info(self, row: sqlite3.Row) -> WorkflowVersionInfo:
        step_names = tuple(json.loads(row["step_names_json"]))
        return WorkflowVersionInfo(
            version_id=row["version_id"],
            workflow_name=row["workflow_name"],
            step_count=row["step_count"],
            created_at=row["created_at"],
            parent_version_id=row["parent_version_id"],
            description=row["description"],
            step_names=step_names,
        )
