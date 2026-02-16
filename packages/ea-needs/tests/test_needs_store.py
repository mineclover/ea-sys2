"""Tests for NeedStore — S3 Recording."""

from __future__ import annotations

import tempfile
from abc import ABC, abstractmethod

import pytest

from ea_needs.needs_store import (
    InMemoryNeedStore,
    NeedQueryOptions,
    NeedSnapshotStatus,
    NeedStore,
    SQLiteNeedStore,
    StakeholderNeedStatistics,
    StoredNeedSnapshot,
)


# ── Factory ─────────────────────────────────────────────────────────────

def _make_snapshot(
    need_id: str = "need-1",
    lineage_id: str = "lineage-1",
    stakeholder_id: str = "sh-cto",
    status: NeedSnapshotStatus = NeedSnapshotStatus.ADDRESSED,
    priority: str = "high",
    complexity: str = "procedural",
    use_case_id: str = "",
    version: int = 1,
    expressed_at: str = "2025-01-15T10:00:00Z",
    action: str = "migrate",
    subject: str = "payment system",
    justification_count: int = 2,
    kernel_ref_count: int = 1,
    decision_ref: str = "",
    metadata: tuple[tuple[str, str], ...] = (),
) -> StoredNeedSnapshot:
    return StoredNeedSnapshot(
        storage_id="",
        need_id=need_id,
        lineage_id=lineage_id,
        stakeholder_id=stakeholder_id,
        status=status,
        priority=priority,
        complexity=complexity,
        use_case_id=use_case_id,
        version=version,
        expressed_at=expressed_at,
        action=action,
        subject=subject,
        justification_count=justification_count,
        kernel_ref_count=kernel_ref_count,
        decision_ref=decision_ref,
        metadata=metadata,
    )


# ── Shared Test Contract ────────────────────────────────────────────────

class _NeedStoreTests(ABC):
    """Shared tests for NeedStore implementations."""

    @abstractmethod
    def create_store(self) -> NeedStore:
        ...

    def test_store_and_get(self):
        store = self.create_store()
        snap = _make_snapshot()
        stored = store.store(snap)

        assert stored.storage_id != ""
        assert stored.stored_at != ""
        assert stored.need_id == "need-1"
        assert stored.stakeholder_id == "sh-cto"

        got = store.get(stored.storage_id)
        assert got is not None
        assert got.need_id == "need-1"
        assert got.status == NeedSnapshotStatus.ADDRESSED

    def test_get_nonexistent(self):
        store = self.create_store()
        assert store.get("nonexistent") is None

    def test_query_all(self):
        store = self.create_store()
        store.store(_make_snapshot(need_id="n1"))
        store.store(_make_snapshot(need_id="n2"))
        store.store(_make_snapshot(need_id="n3"))

        results = store.query()
        assert len(results) == 3

    def test_query_by_stakeholder(self):
        store = self.create_store()
        store.store(_make_snapshot(need_id="n1", stakeholder_id="sh-cto"))
        store.store(_make_snapshot(need_id="n2", stakeholder_id="sh-cto"))
        store.store(_make_snapshot(need_id="n3", stakeholder_id="sh-dev"))

        options = NeedQueryOptions(stakeholder_id="sh-cto")
        results = store.query(options)
        assert len(results) == 2

    def test_query_by_status(self):
        store = self.create_store()
        store.store(_make_snapshot(
            need_id="n1", status=NeedSnapshotStatus.ADDRESSED,
        ))
        store.store(_make_snapshot(
            need_id="n2", status=NeedSnapshotStatus.WITHDRAWN,
        ))
        store.store(_make_snapshot(
            need_id="n3", status=NeedSnapshotStatus.ADDRESSED,
        ))

        options = NeedQueryOptions(status=NeedSnapshotStatus.ADDRESSED)
        results = store.query(options)
        assert len(results) == 2

    def test_query_by_priority(self):
        store = self.create_store()
        store.store(_make_snapshot(need_id="n1", priority="critical"))
        store.store(_make_snapshot(need_id="n2", priority="low"))
        store.store(_make_snapshot(need_id="n3", priority="critical"))

        options = NeedQueryOptions(priority="critical")
        results = store.query(options)
        assert len(results) == 2

    def test_query_by_complexity(self):
        store = self.create_store()
        store.store(_make_snapshot(need_id="n1", complexity="simple"))
        store.store(_make_snapshot(need_id="n2", complexity="complex"))

        options = NeedQueryOptions(complexity="complex")
        results = store.query(options)
        assert len(results) == 1

    def test_query_by_use_case(self):
        store = self.create_store()
        store.store(_make_snapshot(need_id="n1", use_case_id="uc-1"))
        store.store(_make_snapshot(need_id="n2", use_case_id="uc-2"))

        options = NeedQueryOptions(use_case_id="uc-1")
        results = store.query(options)
        assert len(results) == 1

    def test_query_time_range(self):
        store = self.create_store()
        store.store(_make_snapshot(
            need_id="n1", expressed_at="2025-01-01T00:00:00Z",
        ))
        store.store(_make_snapshot(
            need_id="n2", expressed_at="2025-06-15T00:00:00Z",
        ))
        store.store(_make_snapshot(
            need_id="n3", expressed_at="2025-12-31T00:00:00Z",
        ))

        options = NeedQueryOptions(
            start_time="2025-03-01T00:00:00Z",
            end_time="2025-09-01T00:00:00Z",
        )
        results = store.query(options)
        assert len(results) == 1

    def test_query_pagination(self):
        store = self.create_store()
        for i in range(10):
            store.store(_make_snapshot(need_id=f"n{i}"))

        options = NeedQueryOptions(limit=3, offset=0)
        page1 = store.query(options)
        assert len(page1) == 3

        options2 = NeedQueryOptions(limit=3, offset=3)
        page2 = store.query(options2)
        assert len(page2) == 3

    def test_count_all(self):
        store = self.create_store()
        store.store(_make_snapshot(need_id="n1"))
        store.store(_make_snapshot(need_id="n2"))

        assert store.count() == 2

    def test_count_filtered(self):
        store = self.create_store()
        store.store(_make_snapshot(
            need_id="n1", status=NeedSnapshotStatus.ADDRESSED,
        ))
        store.store(_make_snapshot(
            need_id="n2", status=NeedSnapshotStatus.WITHDRAWN,
        ))

        options = NeedQueryOptions(status=NeedSnapshotStatus.ADDRESSED)
        assert store.count(options) == 1

    def test_statistics_by_stakeholder(self):
        store = self.create_store()
        # CTO: 3 needs (2 addressed, 1 withdrawn)
        store.store(_make_snapshot(
            need_id="n1", stakeholder_id="sh-cto",
            status=NeedSnapshotStatus.ADDRESSED, justification_count=2,
        ))
        store.store(_make_snapshot(
            need_id="n2", stakeholder_id="sh-cto",
            status=NeedSnapshotStatus.ADDRESSED, justification_count=3,
        ))
        store.store(_make_snapshot(
            need_id="n3", stakeholder_id="sh-cto",
            status=NeedSnapshotStatus.WITHDRAWN, justification_count=1,
        ))
        # Dev: 1 need (addressed)
        store.store(_make_snapshot(
            need_id="n4", stakeholder_id="sh-dev",
            status=NeedSnapshotStatus.ADDRESSED, justification_count=1,
        ))

        stats = store.statistics_by_stakeholder()
        assert len(stats) == 2

        cto = next(s for s in stats if s.stakeholder_id == "sh-cto")
        assert cto.total_needs == 3
        assert cto.addressed_count == 2
        assert cto.withdrawn_count == 1
        assert cto.addressed_rate == pytest.approx(2 / 3)
        assert cto.avg_justification_count == pytest.approx(2.0)

    def test_metadata_preserved(self):
        store = self.create_store()
        snap = _make_snapshot(
            metadata=(("source", "workshop"), ("domain", "payment")),
        )
        stored = store.store(snap)

        got = store.get(stored.storage_id)
        assert got is not None
        assert dict(got.metadata) == {"source": "workshop", "domain": "payment"}


# ── InMemory Tests ──────────────────────────────────────────────────────

class TestInMemoryNeedStore(_NeedStoreTests):
    def create_store(self) -> NeedStore:
        return InMemoryNeedStore()


# ── SQLite Tests ────────────────────────────────────────────────────────

class TestSQLiteNeedStore(_NeedStoreTests):
    def create_store(self) -> NeedStore:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        return SQLiteNeedStore(tmp.name)

    def test_persistence_across_instances(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        path = tmp.name

        store1 = SQLiteNeedStore(path)
        store1.store(_make_snapshot(need_id="persist-1"))
        assert store1.count() == 1

        store2 = SQLiteNeedStore(path)
        assert store2.count() == 1
        results = store2.query()
        assert results[0].need_id == "persist-1"
