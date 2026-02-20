"""Tests for SDLCStore — S3 Recording in SDLC domain."""

from __future__ import annotations

import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

import pytest
from sdlc_domain.sdlc_store import (
    InMemorySDLCStore,
    SDLCQueryOptions,
    SDLCStore,
    SQLiteSDLCStore,
    StoredSDLCSnapshot,
)


def _make_snapshot(
    snapshot_id: str = "req-1",
    lineage_id: str = "req-1",
    profile_id: str = "requirements",
    status: str = "BACKLOG",
    recorded_at: str = "2025-01-01T09:00:00Z",
    version: int = 1,
    owner: str = "team-platform",
    trace_id: str = "",
    metadata: tuple[tuple[str, str], ...] = (),
) -> StoredSDLCSnapshot:
    return StoredSDLCSnapshot(
        storage_id="",
        snapshot_id=snapshot_id,
        lineage_id=lineage_id,
        profile_id=profile_id,
        status=status,
        recorded_at=recorded_at,
        version=version,
        owner=owner,
        trace_id=trace_id,
        metadata=metadata,
    )


class _SDLCStoreTests(ABC):
    """Shared SDLCStore contract tests."""

    @abstractmethod
    def create_store(self) -> SDLCStore:
        ...

    def test_store_get_query_count_delete_crud(self) -> None:
        store = self.create_store()
        created = store.store(_make_snapshot())
        assert created.storage_id != ""
        assert created.stored_at != ""
        assert created.version == 1

        read_back = store.get(created.storage_id)
        assert read_back is not None
        assert read_back.snapshot_id == "req-1"

        # update path: another snapshot in same lineage
        updated = store.store(_make_snapshot(
            snapshot_id="req-1-v2",
            lineage_id="req-1",
            status="GROOMED",
            recorded_at="2025-01-02T09:00:00Z",
            version=1,  # should auto-increment
        ))
        assert updated.version == 2
        assert store.count() == 2
        assert len(store.query()) == 2

        assert store.delete(created.storage_id) is True
        assert store.get(created.storage_id) is None
        assert store.delete(created.storage_id) is False

    def test_query_filters(self) -> None:
        store = self.create_store()
        store.store(_make_snapshot(
            snapshot_id="r1",
            lineage_id="r1",
            profile_id="requirements",
            status="BACKLOG",
            recorded_at="2025-01-01T00:00:00Z",
            owner="alpha",
        ))
        store.store(_make_snapshot(
            snapshot_id="r1-2",
            lineage_id="r1",
            profile_id="requirements",
            status="GROOMED",
            recorded_at="2025-01-02T00:00:00Z",
            owner="alpha",
        ))
        store.store(_make_snapshot(
            snapshot_id="adr-1",
            lineage_id="adr-1",
            profile_id="arch-decision",
            status="PROPOSED",
            recorded_at="2025-01-03T00:00:00Z",
            owner="beta",
        ))

        results = store.query(SDLCQueryOptions(profile_id="requirements"))
        assert len(results) == 2

        results = store.query(SDLCQueryOptions(lineage_id="r1", status="GROOMED"))
        assert len(results) == 1
        assert results[0].snapshot_id == "r1-2"

        time_filtered = store.query(SDLCQueryOptions(
            start_time="2025-01-02T00:00:00Z",
            end_time="2025-01-03T00:00:00Z",
        ))
        assert len(time_filtered) == 2

        page = store.query(SDLCQueryOptions(limit=1, offset=1))
        assert len(page) == 1

    def test_valid_profile_transition(self) -> None:
        store = self.create_store()
        first = store.store(_make_snapshot(
            lineage_id="req-2",
            snapshot_id="req-2-a",
            profile_id="requirements",
            status="BACKLOG",
        ))
        second = store.store(_make_snapshot(
            lineage_id="req-2",
            snapshot_id="req-2-b",
            profile_id="requirements",
            status="GROOMED",
            recorded_at="2025-01-02T00:00:00Z",
        ))
        assert first.version == 1
        assert second.version == 2

    def test_invalid_profile_transition_rejected(self) -> None:
        store = self.create_store()
        store.store(_make_snapshot(
            lineage_id="req-3",
            snapshot_id="req-3-a",
            profile_id="requirements",
            status="BACKLOG",
        ))
        with pytest.raises(ValueError, match="Invalid transition"):
            store.store(_make_snapshot(
                lineage_id="req-3",
                snapshot_id="req-3-b",
                profile_id="requirements",
                status="DONE",
                recorded_at="2025-01-02T00:00:00Z",
            ))

    def test_unknown_state_rejected(self) -> None:
        store = self.create_store()
        with pytest.raises(ValueError, match="Invalid snapshot state"):
            store.store(_make_snapshot(
                lineage_id="req-4",
                snapshot_id="req-4-a",
                profile_id="requirements",
                status="NOT_A_REAL_STATE",
            ))

    def test_profile_without_transitions_rejected(self) -> None:
        store = self.create_store()
        with pytest.raises(RuntimeError, match="has no \\[\\[state_transitions\\]\\] entries"):
            store.store(_make_snapshot(
                lineage_id="dm-1",
                snapshot_id="dm-1-a",
                profile_id="domain-model",
                status="MODELING",
            ))


class TestInMemorySDLCStore(_SDLCStoreTests):
    def create_store(self) -> SDLCStore:
        return InMemorySDLCStore()


class TestSQLiteSDLCStore(_SDLCStoreTests):
    def create_store(self) -> SDLCStore:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        return SQLiteSDLCStore(Path(path))
