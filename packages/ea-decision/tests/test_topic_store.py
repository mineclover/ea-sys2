"""Tests for TopicStore — S3 Recording."""

from __future__ import annotations

import tempfile
from pathlib import Path

from ea_decision.topic_store import (
    DecisionQueryOptions,
    DecisionSnapshotStatus,
    DecisionStatistics,
    InMemoryTopicStore,
    SQLiteTopicStore,
    StoredDecisionSnapshot,
    TopicStore,
)


# ── Factory ─────────────────────────────────────────────────────────────

def _make_snapshot(
    topic_id: str = "topic-001",
    pattern_name: str = "TradeOff",
    complexity: str = "structural",
    option_count: int = 3,
    evaluation_score: float = 0.75,
    decided_at: str = "2025-01-15T10:00:00Z",
    status: DecisionSnapshotStatus = DecisionSnapshotStatus.ACCEPTED,
    rationale: str = "Best trade-off",
    selected_option_id: str = "opt-1",
) -> StoredDecisionSnapshot:
    return StoredDecisionSnapshot(
        storage_id="",
        topic_id=topic_id,
        pattern_name=pattern_name,
        complexity=complexity,
        option_count=option_count,
        evaluation_score=evaluation_score,
        decided_at=decided_at,
        status=status,
        rationale=rationale,
        selected_option_id=selected_option_id,
    )


# ── Shared tests for both implementations ──────────────────────────────

class _TopicStoreTests:
    """Shared test suite for TopicStore implementations."""

    def _create_store(self) -> TopicStore:
        raise NotImplementedError

    def test_store_and_get(self):
        store = self._create_store()
        snap = _make_snapshot()
        stored = store.store(snap)

        assert stored.storage_id != ""
        assert stored.stored_at != ""
        assert stored.topic_id == "topic-001"

        got = store.get(stored.storage_id)
        assert got is not None
        assert got.topic_id == "topic-001"
        assert got.pattern_name == "TradeOff"

    def test_get_nonexistent_returns_none(self):
        store = self._create_store()
        assert store.get("nonexistent") is None

    def test_query_all(self):
        store = self._create_store()
        store.store(_make_snapshot(topic_id="t1"))
        store.store(_make_snapshot(topic_id="t2"))

        results = store.query()
        assert len(results) == 2

    def test_query_by_pattern(self):
        store = self._create_store()
        store.store(_make_snapshot(pattern_name="TradeOff"))
        store.store(_make_snapshot(pattern_name="Compliance"))
        store.store(_make_snapshot(pattern_name="TradeOff"))

        options = DecisionQueryOptions(pattern_name="TradeOff")
        results = store.query(options)
        assert len(results) == 2

    def test_query_by_status(self):
        store = self._create_store()
        store.store(_make_snapshot(status=DecisionSnapshotStatus.ACCEPTED))
        store.store(_make_snapshot(status=DecisionSnapshotStatus.REJECTED))
        store.store(_make_snapshot(status=DecisionSnapshotStatus.ACCEPTED))

        options = DecisionQueryOptions(status=DecisionSnapshotStatus.ACCEPTED)
        results = store.query(options)
        assert len(results) == 2

    def test_query_by_complexity(self):
        store = self._create_store()
        store.store(_make_snapshot(complexity="trivial"))
        store.store(_make_snapshot(complexity="structural"))

        options = DecisionQueryOptions(complexity="trivial")
        results = store.query(options)
        assert len(results) == 1

    def test_query_by_time_range(self):
        store = self._create_store()
        store.store(_make_snapshot(decided_at="2025-01-10T00:00:00Z"))
        store.store(_make_snapshot(decided_at="2025-01-20T00:00:00Z"))
        store.store(_make_snapshot(decided_at="2025-01-30T00:00:00Z"))

        options = DecisionQueryOptions(
            start_time="2025-01-15T00:00:00Z",
            end_time="2025-01-25T00:00:00Z",
        )
        results = store.query(options)
        assert len(results) == 1

    def test_query_pagination(self):
        store = self._create_store()
        for i in range(5):
            store.store(_make_snapshot(topic_id=f"t-{i}"))

        options = DecisionQueryOptions(limit=2, offset=0)
        page1 = store.query(options)
        assert len(page1) == 2

        options2 = DecisionQueryOptions(limit=2, offset=2)
        page2 = store.query(options2)
        assert len(page2) == 2

    def test_count(self):
        store = self._create_store()
        store.store(_make_snapshot(pattern_name="A"))
        store.store(_make_snapshot(pattern_name="B"))
        store.store(_make_snapshot(pattern_name="A"))

        assert store.count() == 3
        assert store.count(DecisionQueryOptions(pattern_name="A")) == 2

    def test_statistics_by_pattern(self):
        store = self._create_store()
        store.store(_make_snapshot(
            pattern_name="TradeOff", option_count=3,
            evaluation_score=0.8, status=DecisionSnapshotStatus.ACCEPTED,
        ))
        store.store(_make_snapshot(
            pattern_name="TradeOff", option_count=5,
            evaluation_score=0.6, status=DecisionSnapshotStatus.REJECTED,
        ))
        store.store(_make_snapshot(
            pattern_name="Compliance", option_count=2,
            evaluation_score=0.9, status=DecisionSnapshotStatus.ACCEPTED,
        ))

        stats = store.statistics_by_pattern()
        assert len(stats) == 2

        trade_off = next(s for s in stats if s.pattern_name == "TradeOff")
        assert trade_off.total_decisions == 2
        assert trade_off.avg_options == 4.0
        assert trade_off.acceptance_rate == 0.5

    def test_metadata_preserved(self):
        store = self._create_store()
        snap = StoredDecisionSnapshot(
            storage_id="",
            topic_id="t-meta",
            pattern_name="Meta",
            complexity="trivial",
            option_count=1,
            evaluation_score=0.5,
            decided_at="2025-01-01T00:00:00Z",
            status=DecisionSnapshotStatus.ACCEPTED,
            metadata=(("key1", "val1"), ("key2", "val2")),
        )
        stored = store.store(snap)
        got = store.get(stored.storage_id)
        assert got is not None
        assert dict(got.metadata) == {"key1": "val1", "key2": "val2"}


# ── InMemory Tests ──────────────────────────────────────────────────────

class TestInMemoryTopicStore(_TopicStoreTests):
    def _create_store(self) -> TopicStore:
        return InMemoryTopicStore()


# ── SQLite Tests ────────────────────────────────────────────────────────

class TestSQLiteTopicStore(_TopicStoreTests):
    def _create_store(self) -> TopicStore:
        self._tmpdir = tempfile.mkdtemp()
        return SQLiteTopicStore(Path(self._tmpdir) / "topic.db")

    def test_sqlite_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "persist.db"
            store1 = SQLiteTopicStore(db_path)
            store1.store(_make_snapshot(topic_id="persist-1"))

            store2 = SQLiteTopicStore(db_path)
            assert store2.count() == 1
            results = store2.query()
            assert results[0].topic_id == "persist-1"
