"""Tests for ProjectionStore — S3 Recording."""

from __future__ import annotations

import tempfile
from pathlib import Path

from ea_projection.projection_store import (
    InMemoryProjectionStore,
    LevelProjectionStatistics,
    ProjectionQueryOptions,
    ProjectionSnapshotStatus,
    SQLiteProjectionStore,
    StoredProjectionSnapshot,
)


# ── Factory ─────────────────────────────────────────────────────────────

def _make_snapshot(
    profile_name: str = "ea_sys",
    level: str = "l0",
    lens: str = "panorama",
    node_count: int = 10,
    edge_count: int = 20,
    status: ProjectionSnapshotStatus = ProjectionSnapshotStatus.PROJECTED,
    tier: str = "",
    seed: str = "",
    projected_at: str = "2025-01-15T10:00:00Z",
    filter_node_input: int = 0,
    filter_node_output: int = 0,
) -> StoredProjectionSnapshot:
    return StoredProjectionSnapshot(
        storage_id="",
        profile_name=profile_name,
        level=level,
        lens=lens,
        node_count=node_count,
        edge_count=edge_count,
        status=status,
        tier=tier,
        seed=seed,
        projected_at=projected_at,
        filter_node_input=filter_node_input,
        filter_node_output=filter_node_output,
    )


# ── StoredProjectionSnapshot Tests ──────────────────────────────────────

class TestStoredProjectionSnapshot:
    def test_frozen(self):
        snap = _make_snapshot()
        try:
            snap.node_count = 99  # type: ignore[misc]
            assert False, "Should raise"
        except AttributeError:
            pass

    def test_default_status(self):
        snap = _make_snapshot()
        assert snap.status == ProjectionSnapshotStatus.PROJECTED


# ── LevelProjectionStatistics Tests ─────────────────────────────────────

class TestLevelProjectionStatistics:
    def test_stale_rate(self):
        stats = LevelProjectionStatistics(
            level="l0", total_projections=10, stale_count=3,
        )
        assert stats.stale_rate == 0.3

    def test_stale_rate_zero(self):
        stats = LevelProjectionStatistics(level="l0")
        assert stats.stale_rate == 0.0

    def test_node_range(self):
        stats = LevelProjectionStatistics(
            level="l0", min_node_count=5, max_node_count=15,
        )
        assert stats.node_range == 10

    def test_edge_range(self):
        stats = LevelProjectionStatistics(
            level="l0", min_edge_count=10, max_edge_count=50,
        )
        assert stats.edge_range == 40


# ── InMemoryProjectionStore Tests ───────────────────────────────────────

class TestInMemoryProjectionStore:
    def test_store_and_get(self):
        store = InMemoryProjectionStore()
        snap = _make_snapshot()
        stored = store.store(snap)

        assert stored.storage_id != ""
        assert stored.stored_at != ""
        assert stored.profile_name == "ea_sys"

        retrieved = store.get(stored.storage_id)
        assert retrieved is not None
        assert retrieved.storage_id == stored.storage_id

    def test_get_nonexistent(self):
        store = InMemoryProjectionStore()
        assert store.get("nonexistent") is None

    def test_query_all(self):
        store = InMemoryProjectionStore()
        store.store(_make_snapshot(level="l0"))
        store.store(_make_snapshot(level="l1", lens="capability"))
        store.store(_make_snapshot(level="l2", lens="interaction"))

        results = store.query()
        assert len(results) == 3

    def test_query_by_level(self):
        store = InMemoryProjectionStore()
        store.store(_make_snapshot(level="l0"))
        store.store(_make_snapshot(level="l0"))
        store.store(_make_snapshot(level="l1", lens="capability"))

        options = ProjectionQueryOptions(level="l0")
        results = store.query(options)
        assert len(results) == 2

    def test_query_by_profile_name(self):
        store = InMemoryProjectionStore()
        store.store(_make_snapshot(profile_name="ea_sys"))
        store.store(_make_snapshot(profile_name="ea_sys"))
        store.store(_make_snapshot(profile_name="other"))

        options = ProjectionQueryOptions(profile_name="ea_sys")
        results = store.query(options)
        assert len(results) == 2

    def test_query_by_status(self):
        store = InMemoryProjectionStore()
        store.store(_make_snapshot(status=ProjectionSnapshotStatus.PROJECTED))
        store.store(_make_snapshot(status=ProjectionSnapshotStatus.STALE))

        options = ProjectionQueryOptions(
            status=ProjectionSnapshotStatus.PROJECTED,
        )
        results = store.query(options)
        assert len(results) == 1

    def test_query_by_tier_and_seed(self):
        store = InMemoryProjectionStore()
        store.store(_make_snapshot(tier="t1", seed="my-element"))
        store.store(_make_snapshot(tier="t1", seed="other"))
        store.store(_make_snapshot(tier="t2"))

        options = ProjectionQueryOptions(tier="t1", seed="my-element")
        results = store.query(options)
        assert len(results) == 1

    def test_query_with_time_range(self):
        store = InMemoryProjectionStore()
        store.store(_make_snapshot(projected_at="2025-01-10T10:00:00Z"))
        store.store(_make_snapshot(projected_at="2025-01-15T10:00:00Z"))
        store.store(_make_snapshot(projected_at="2025-01-20T10:00:00Z"))

        options = ProjectionQueryOptions(
            start_time="2025-01-12T00:00:00Z",
            end_time="2025-01-18T00:00:00Z",
        )
        results = store.query(options)
        assert len(results) == 1

    def test_query_with_pagination(self):
        store = InMemoryProjectionStore()
        for i in range(5):
            store.store(_make_snapshot(
                projected_at=f"2025-01-{10+i:02d}T10:00:00Z",
            ))

        options = ProjectionQueryOptions(limit=2, offset=1)
        results = store.query(options)
        assert len(results) == 2

    def test_count(self):
        store = InMemoryProjectionStore()
        store.store(_make_snapshot())
        store.store(_make_snapshot())
        store.store(_make_snapshot())

        assert store.count() == 3

    def test_count_with_options(self):
        store = InMemoryProjectionStore()
        store.store(_make_snapshot(level="l0"))
        store.store(_make_snapshot(level="l0"))
        store.store(_make_snapshot(level="l1", lens="capability"))

        options = ProjectionQueryOptions(level="l0")
        assert store.count(options) == 2

    def test_statistics_by_level(self):
        store = InMemoryProjectionStore()
        store.store(_make_snapshot(level="l0", node_count=10, edge_count=20))
        store.store(_make_snapshot(level="l0", node_count=20, edge_count=40))
        store.store(_make_snapshot(
            level="l0", node_count=15, edge_count=30,
            status=ProjectionSnapshotStatus.STALE,
        ))
        store.store(_make_snapshot(
            level="l1", lens="capability",
            node_count=5, edge_count=10,
        ))

        stats = store.statistics_by_level()
        assert len(stats) == 2

        l0_stats = next(s for s in stats if s.level == "l0")
        assert l0_stats.total_projections == 3
        assert l0_stats.avg_node_count == 15.0
        assert l0_stats.avg_edge_count == 30.0
        assert l0_stats.min_node_count == 10
        assert l0_stats.max_node_count == 20
        assert l0_stats.stale_count == 1

    def test_statistics_empty(self):
        store = InMemoryProjectionStore()
        stats = store.statistics_by_level()
        assert len(stats) == 0


# ── SQLiteProjectionStore Tests ─────────────────────────────────────────

class TestSQLiteProjectionStore:
    def test_store_and_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "projections.db"
            store = SQLiteProjectionStore(db_path)

            snap = _make_snapshot()
            stored = store.store(snap)

            assert stored.storage_id != ""
            assert stored.stored_at != ""

            retrieved = store.get(stored.storage_id)
            assert retrieved is not None
            assert retrieved.profile_name == "ea_sys"
            assert retrieved.level == "l0"
            assert retrieved.node_count == 10

    def test_get_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "projections.db"
            store = SQLiteProjectionStore(db_path)
            assert store.get("nonexistent") is None

    def test_query_by_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "projections.db"
            store = SQLiteProjectionStore(db_path)

            store.store(_make_snapshot(level="l0"))
            store.store(_make_snapshot(level="l0"))
            store.store(_make_snapshot(level="l1", lens="capability"))

            options = ProjectionQueryOptions(level="l0")
            results = store.query(options)
            assert len(results) == 2

    def test_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "projections.db"
            store = SQLiteProjectionStore(db_path)

            store.store(_make_snapshot())
            store.store(_make_snapshot())
            assert store.count() == 2

    def test_statistics_by_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "projections.db"
            store = SQLiteProjectionStore(db_path)

            store.store(_make_snapshot(
                level="l0", node_count=10, edge_count=20,
            ))
            store.store(_make_snapshot(
                level="l0", node_count=20, edge_count=40,
            ))

            stats = store.statistics_by_level()
            assert len(stats) == 1
            assert stats[0].level == "l0"
            assert stats[0].total_projections == 2
            assert stats[0].avg_node_count == 15.0

    def test_metadata_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "projections.db"
            store = SQLiteProjectionStore(db_path)

            snap = StoredProjectionSnapshot(
                storage_id="",
                profile_name="ea_sys",
                level="l0",
                lens="panorama",
                node_count=5,
                edge_count=10,
                metadata=(("key1", "val1"), ("key2", "val2")),
            )
            stored = store.store(snap)
            retrieved = store.get(stored.storage_id)
            assert retrieved is not None
            assert dict(retrieved.metadata) == {"key1": "val1", "key2": "val2"}

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "projections.db"

            store1 = SQLiteProjectionStore(db_path)
            store1.store(_make_snapshot())

            store2 = SQLiteProjectionStore(db_path)
            assert store2.count() == 1
