"""Scenario Store — S3 Recording for Scenario Flows.

Persistent storage for scenario flow snapshots with query capabilities.
Provides:
- StoredScenarioSnapshot: Frozen snapshot of a scenario flow
- ScenarioQueryOptions: Query filter options
- ScenarioStore ABC: Storage interface
- InMemoryScenarioStore: In-memory implementation for testing

References:
- ea_needs/needs_store.py: S3 Store pattern
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Domain Types — Stored Scenario Snapshot
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class StoredScenarioSnapshot:
    """Immutable snapshot of a scenario flow for storage."""
    storage_id: str
    scenario_id: str
    use_case_id: str
    scenario_type: str
    step_count: int
    kernel_ref_count: int
    version: int
    stored_at: str


@dataclass(frozen=True)
class ScenarioQueryOptions:
    """Query filter options for scenario snapshots."""
    use_case_id: str = ""
    scenario_type: str = ""
    limit: int = 100
    offset: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# ScenarioStore ABC
# ═══════════════════════════════════════════════════════════════════════════════

class ScenarioStore(ABC):
    """Scenario Store ABC — storage interface for scenario snapshots."""

    @abstractmethod
    def store(self, snapshot: StoredScenarioSnapshot) -> StoredScenarioSnapshot:
        """Store a scenario snapshot.

        Args:
            snapshot: Snapshot to store (storage_id auto-generated if empty)

        Returns:
            StoredScenarioSnapshot with storage metadata
        """
        ...

    @abstractmethod
    def get(self, storage_id: str) -> StoredScenarioSnapshot | None:
        """Retrieve a snapshot by storage_id."""
        ...

    @abstractmethod
    def query(
        self, options: ScenarioQueryOptions | None = None,
    ) -> tuple[StoredScenarioSnapshot, ...]:
        """Query snapshots with optional filters."""
        ...

    @abstractmethod
    def count(self) -> int:
        """Return total number of stored snapshots."""
        ...


# ═══════════════════════════════════════════════════════════════════════════════
# InMemoryScenarioStore — In-memory implementation for testing
# ═══════════════════════════════════════════════════════════════════════════════

class InMemoryScenarioStore(ScenarioStore):
    """In-memory Scenario Store for testing."""

    __slots__ = ("_records",)

    def __init__(self) -> None:
        self._records: dict[str, StoredScenarioSnapshot] = {}

    def store(self, snapshot: StoredScenarioSnapshot) -> StoredScenarioSnapshot:
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        storage_id = snapshot.storage_id or str(uuid.uuid4())

        stored = StoredScenarioSnapshot(
            storage_id=storage_id,
            scenario_id=snapshot.scenario_id,
            use_case_id=snapshot.use_case_id,
            scenario_type=snapshot.scenario_type,
            step_count=snapshot.step_count,
            kernel_ref_count=snapshot.kernel_ref_count,
            version=snapshot.version,
            stored_at=now,
        )

        self._records[storage_id] = stored
        return stored

    def get(self, storage_id: str) -> StoredScenarioSnapshot | None:
        return self._records.get(storage_id)

    def query(
        self, options: ScenarioQueryOptions | None = None,
    ) -> tuple[StoredScenarioSnapshot, ...]:
        if options is None:
            return tuple(self._records.values())
        return tuple(self._filter_records(options))

    def count(self) -> int:
        return len(self._records)

    def _filter_records(
        self, options: ScenarioQueryOptions,
    ) -> list[StoredScenarioSnapshot]:
        candidates = list(self._records.values())

        results: list[StoredScenarioSnapshot] = []
        for snap in candidates:
            if options.use_case_id and snap.use_case_id != options.use_case_id:
                continue
            if options.scenario_type and snap.scenario_type != options.scenario_type:
                continue
            results.append(snap)

        start = options.offset
        end = options.offset + options.limit
        return results[start:end]
