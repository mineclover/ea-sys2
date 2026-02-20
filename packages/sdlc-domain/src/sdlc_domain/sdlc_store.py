"""SDLC Store — S3 Recording for SDLC domain snapshots.

Provides:
- SDLCStore ABC: 저장소 인터페이스
- InMemorySDLCStore: 테스트용 인메모리 구현
- SQLiteSDLCStore: SQLite 기반 영속 저장소

Store save validates lifecycle transitions using SDLC profile metadata.
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
from enum import Enum
from functools import lru_cache
from pathlib import Path

from ea_kernel.profiles.sdlc import PROFILE_FILE_MAP, profile_path
from ea_profile.loader import load_profile


def _now_iso() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"


def _normalize_state(state: str | Enum) -> str:
    raw = state.value if isinstance(state, Enum) else state
    token = str(raw).strip()
    if "." in token:
        token = token.rsplit(".", 1)[-1]
    return token.upper()


@lru_cache(maxsize=16)
def _profile_transition_table(
    profile_id: str,
) -> tuple[dict[str, frozenset[str]], frozenset[str], frozenset[str]]:
    """Load and compile transition rules from a SDLC profile."""
    try:
        path = profile_path(profile_id)
    except KeyError as exc:
        allowed = ", ".join(sorted(PROFILE_FILE_MAP))
        raise ValueError(
            f"Unknown SDLC profile id '{profile_id}'. Allowed: {allowed}"
        ) from exc

    profile = load_profile(path)
    if not profile.state_transitions:
        raise RuntimeError(
            f"SDLC profile '{profile_id}' has no [[state_transitions]] entries."
        )

    explicit_targets: dict[str, set[str]] = {}
    wildcard_targets: set[str] = set()
    known_states: set[str] = set()

    for transition in profile.state_transitions:
        from_state = _normalize_state(transition.from_state)
        to_state = _normalize_state(transition.to_state)

        if from_state != "*":
            known_states.add(from_state)
        if to_state != "*":
            known_states.add(to_state)

        if from_state == "*":
            if to_state != "*":
                wildcard_targets.add(to_state)
            continue

        explicit_targets.setdefault(from_state, set()).add(to_state)

    frozen_explicit = {
        state: frozenset(targets)
        for state, targets in explicit_targets.items()
    }
    return frozen_explicit, frozenset(wildcard_targets), frozenset(known_states)


def _ensure_known_state(profile_id: str, state: str | Enum) -> str:
    _, _, known_states = _profile_transition_table(profile_id)
    token = _normalize_state(state)
    if token not in known_states:
        raise ValueError(
            f"Invalid snapshot state: {token}. "
            f"State is not declared in SDLC profile '{profile_id}' transitions."
        )
    return token


def _ensure_profile_transition(
    profile_id: str,
    source_state: str | Enum,
    target_state: str | Enum,
) -> None:
    explicit_targets, wildcard_targets, known_states = _profile_transition_table(profile_id)
    source = _normalize_state(source_state)
    target = _normalize_state(target_state)

    if source not in known_states:
        raise ValueError(
            f"Invalid transition source state: {source}. "
            f"State is not declared in SDLC profile '{profile_id}' transitions."
        )
    if target not in known_states:
        raise ValueError(
            f"Invalid transition target state: {target}. "
            f"State is not declared in SDLC profile '{profile_id}' transitions."
        )

    allowed = set(explicit_targets.get(source, frozenset()))
    allowed.update(wildcard_targets)
    if target not in allowed:
        raise ValueError(
            f"Invalid transition for profile '{profile_id}': {source} -> {target}. "
            f"Allowed: {sorted(allowed)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Domain Types
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class StoredSDLCSnapshot:
    """Immutable SDLC snapshot record."""

    storage_id: str
    snapshot_id: str
    lineage_id: str
    profile_id: str
    status: str
    recorded_at: str
    stored_at: str = ""
    version: int = 1
    owner: str = ""
    trace_id: str = ""
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SDLCQueryOptions:
    """SDLC snapshot query options."""

    snapshot_id: str = ""
    lineage_id: str = ""
    profile_id: str = ""
    status: str = ""
    owner: str = ""
    start_time: str = ""
    end_time: str = ""
    limit: int = 100
    offset: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# Store ABC
# ═══════════════════════════════════════════════════════════════════════════════


class SDLCStore(ABC):
    """SDLC snapshot store interface."""

    @abstractmethod
    def store(self, snapshot: StoredSDLCSnapshot) -> StoredSDLCSnapshot:
        """Store snapshot after profile transition validation."""
        ...

    @abstractmethod
    def get(self, storage_id: str) -> StoredSDLCSnapshot | None:
        """Get a snapshot by storage id."""
        ...

    @abstractmethod
    def query(
        self,
        options: SDLCQueryOptions | None = None,
    ) -> tuple[StoredSDLCSnapshot, ...]:
        """Query snapshots with optional filters."""
        ...

    @abstractmethod
    def count(self, options: SDLCQueryOptions | None = None) -> int:
        """Count snapshots with optional filters."""
        ...

    @abstractmethod
    def delete(self, storage_id: str) -> bool:
        """Delete a snapshot by storage id."""
        ...


def _resolved_version(
    requested_version: int,
    previous: StoredSDLCSnapshot | None,
) -> int:
    if previous is None:
        return requested_version if requested_version > 0 else 1
    if requested_version > previous.version:
        return requested_version
    return previous.version + 1


# ═══════════════════════════════════════════════════════════════════════════════
# InMemory Store
# ═══════════════════════════════════════════════════════════════════════════════


class InMemorySDLCStore(SDLCStore):
    """In-memory SDLC snapshot store for tests."""

    __slots__ = ("_records", "_by_profile_lineage")

    def __init__(self) -> None:
        self._records: dict[str, StoredSDLCSnapshot] = {}
        self._by_profile_lineage: dict[tuple[str, str], list[str]] = {}

    def store(self, snapshot: StoredSDLCSnapshot) -> StoredSDLCSnapshot:
        existing = self._latest_for_lineage(snapshot.profile_id, snapshot.lineage_id)
        if existing is None:
            _ensure_known_state(snapshot.profile_id, snapshot.status)
        else:
            _ensure_profile_transition(
                snapshot.profile_id,
                existing.status,
                snapshot.status,
            )

        storage_id = snapshot.storage_id or str(uuid.uuid4())
        if storage_id in self._records:
            raise ValueError(f"Snapshot already exists: {storage_id}")

        now = _now_iso()
        version = _resolved_version(snapshot.version, existing)
        stored = StoredSDLCSnapshot(
            storage_id=storage_id,
            snapshot_id=snapshot.snapshot_id,
            lineage_id=snapshot.lineage_id,
            profile_id=snapshot.profile_id,
            status=snapshot.status,
            recorded_at=snapshot.recorded_at,
            stored_at=now,
            version=version,
            owner=snapshot.owner,
            trace_id=snapshot.trace_id,
            metadata=snapshot.metadata,
        )
        self._records[storage_id] = stored
        self._by_profile_lineage.setdefault(
            (snapshot.profile_id, snapshot.lineage_id),
            [],
        ).append(storage_id)
        return stored

    def get(self, storage_id: str) -> StoredSDLCSnapshot | None:
        return self._records.get(storage_id)

    def query(
        self,
        options: SDLCQueryOptions | None = None,
    ) -> tuple[StoredSDLCSnapshot, ...]:
        records = list(self._records.values())

        if options is not None:
            records = [snap for snap in records if self._matches_options(snap, options)]

        records.sort(
            key=lambda snap: (snap.recorded_at, snap.version, snap.stored_at),
            reverse=True,
        )

        if options is None:
            return tuple(records)

        start = options.offset
        end = options.offset + options.limit
        return tuple(records[start:end])

    def count(self, options: SDLCQueryOptions | None = None) -> int:
        if options is None:
            return len(self._records)
        return sum(
            1 for snap in self._records.values()
            if self._matches_options(snap, options)
        )

    def delete(self, storage_id: str) -> bool:
        removed = self._records.pop(storage_id, None)
        if removed is None:
            return False

        key = (removed.profile_id, removed.lineage_id)
        storage_ids = self._by_profile_lineage.get(key, [])
        if storage_id in storage_ids:
            storage_ids.remove(storage_id)
        if not storage_ids:
            self._by_profile_lineage.pop(key, None)
        return True

    def _latest_for_lineage(
        self,
        profile_id: str,
        lineage_id: str,
    ) -> StoredSDLCSnapshot | None:
        ids = self._by_profile_lineage.get((profile_id, lineage_id), [])
        if not ids:
            return None
        snapshots = (self._records[storage_id] for storage_id in ids)
        return max(snapshots, key=lambda snap: (snap.version, snap.recorded_at, snap.stored_at))

    @staticmethod
    def _matches_options(snapshot: StoredSDLCSnapshot, options: SDLCQueryOptions) -> bool:
        if options.snapshot_id and snapshot.snapshot_id != options.snapshot_id:
            return False
        if options.lineage_id and snapshot.lineage_id != options.lineage_id:
            return False
        if options.profile_id and snapshot.profile_id != options.profile_id:
            return False
        if options.status and _normalize_state(snapshot.status) != _normalize_state(options.status):
            return False
        if options.owner and snapshot.owner != options.owner:
            return False
        if options.start_time and snapshot.recorded_at < options.start_time:
            return False
        return not (options.end_time and snapshot.recorded_at > options.end_time)


# ═══════════════════════════════════════════════════════════════════════════════
# SQLite Store
# ═══════════════════════════════════════════════════════════════════════════════


class SQLiteSDLCStore(SDLCStore):
    """SQLite-backed SDLC snapshot store."""

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
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY
                );

                CREATE TABLE IF NOT EXISTS sdlc_snapshots (
                    storage_id TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL,
                    lineage_id TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    recorded_at TEXT NOT NULL,
                    stored_at TEXT NOT NULL,
                    owner TEXT DEFAULT '',
                    trace_id TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_sdlc_snapshot_id
                    ON sdlc_snapshots(snapshot_id);
                CREATE INDEX IF NOT EXISTS idx_sdlc_lineage_profile
                    ON sdlc_snapshots(profile_id, lineage_id);
                CREATE INDEX IF NOT EXISTS idx_sdlc_profile_id
                    ON sdlc_snapshots(profile_id);
                CREATE INDEX IF NOT EXISTS idx_sdlc_status
                    ON sdlc_snapshots(status);
                CREATE INDEX IF NOT EXISTS idx_sdlc_recorded_at
                    ON sdlc_snapshots(recorded_at);
                """
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

    def store(self, snapshot: StoredSDLCSnapshot) -> StoredSDLCSnapshot:
        existing = self._latest_for_lineage(snapshot.profile_id, snapshot.lineage_id)
        if existing is None:
            _ensure_known_state(snapshot.profile_id, snapshot.status)
        else:
            _ensure_profile_transition(
                snapshot.profile_id,
                existing.status,
                snapshot.status,
            )

        now = _now_iso()
        storage_id = snapshot.storage_id or str(uuid.uuid4())
        version = _resolved_version(snapshot.version, existing)
        metadata_json = json.dumps(dict(snapshot.metadata))
        stored = StoredSDLCSnapshot(
            storage_id=storage_id,
            snapshot_id=snapshot.snapshot_id,
            lineage_id=snapshot.lineage_id,
            profile_id=snapshot.profile_id,
            status=snapshot.status,
            recorded_at=snapshot.recorded_at,
            stored_at=now,
            version=version,
            owner=snapshot.owner,
            trace_id=snapshot.trace_id,
            metadata=snapshot.metadata,
        )

        with self._connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO sdlc_snapshots (
                        storage_id, snapshot_id, lineage_id, profile_id, status,
                        version, recorded_at, stored_at, owner, trace_id, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        storage_id,
                        snapshot.snapshot_id,
                        snapshot.lineage_id,
                        snapshot.profile_id,
                        snapshot.status,
                        version,
                        snapshot.recorded_at,
                        now,
                        snapshot.owner,
                        snapshot.trace_id,
                        metadata_json,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Snapshot already exists: {storage_id}") from exc
            conn.commit()

        return stored

    def get(self, storage_id: str) -> StoredSDLCSnapshot | None:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM sdlc_snapshots WHERE storage_id = ?",
                (storage_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_snapshot(row)

    @staticmethod
    def _build_where_conditions(
        options: SDLCQueryOptions,
    ) -> tuple[list[str], list[str | int]]:
        conditions: list[str] = []
        params: list[str | int] = []

        if options.snapshot_id:
            conditions.append("snapshot_id = ?")
            params.append(options.snapshot_id)
        if options.lineage_id:
            conditions.append("lineage_id = ?")
            params.append(options.lineage_id)
        if options.profile_id:
            conditions.append("profile_id = ?")
            params.append(options.profile_id)
        if options.status:
            conditions.append("UPPER(status) = ?")
            params.append(_normalize_state(options.status))
        if options.owner:
            conditions.append("owner = ?")
            params.append(options.owner)
        if options.start_time:
            conditions.append("recorded_at >= ?")
            params.append(options.start_time)
        if options.end_time:
            conditions.append("recorded_at <= ?")
            params.append(options.end_time)

        return conditions, params

    def query(
        self,
        options: SDLCQueryOptions | None = None,
    ) -> tuple[StoredSDLCSnapshot, ...]:
        query = "SELECT * FROM sdlc_snapshots"
        params: list[str | int] = []

        if options is not None:
            conditions, params = self._build_where_conditions(options)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY recorded_at DESC, version DESC"

        if options is not None:
            query += f" LIMIT {options.limit} OFFSET {options.offset}"

        with self._connection() as conn:
            cursor = conn.execute(query, params)
            return tuple(self._row_to_snapshot(row) for row in cursor.fetchall())

    def count(self, options: SDLCQueryOptions | None = None) -> int:
        query = "SELECT COUNT(*) FROM sdlc_snapshots"
        params: list[str | int] = []

        if options is not None:
            conditions, params = self._build_where_conditions(options)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        with self._connection() as conn:
            cursor = conn.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result else 0

    def delete(self, storage_id: str) -> bool:
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM sdlc_snapshots WHERE storage_id = ?",
                (storage_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def _latest_for_lineage(
        self,
        profile_id: str,
        lineage_id: str,
    ) -> StoredSDLCSnapshot | None:
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM sdlc_snapshots
                WHERE profile_id = ? AND lineage_id = ?
                ORDER BY version DESC, recorded_at DESC, stored_at DESC
                LIMIT 1
                """,
                (profile_id, lineage_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_snapshot(row)

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> StoredSDLCSnapshot:
        metadata_dict = json.loads(row["metadata_json"])
        metadata = tuple(metadata_dict.items())
        return StoredSDLCSnapshot(
            storage_id=row["storage_id"],
            snapshot_id=row["snapshot_id"],
            lineage_id=row["lineage_id"],
            profile_id=row["profile_id"],
            status=row["status"],
            recorded_at=row["recorded_at"],
            stored_at=row["stored_at"],
            version=row["version"],
            owner=row["owner"],
            trace_id=row["trace_id"],
            metadata=metadata,
        )
