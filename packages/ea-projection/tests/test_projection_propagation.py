"""Tests for ProjectionPropagationEngine — S6 Propagation."""

from __future__ import annotations

from ea_projection.projection_propagation import (
    AffectedProjectionSnapshot,
    ProjectionChange,
    ProjectionChangeAction,
    ProjectionChangeSet,
    ProjectionPropagationEngine,
    ProjectionPropagationReport,
    PropagationSeverity,
)
from ea_projection.projection_store import (
    InMemoryProjectionStore,
    ProjectionSnapshotStatus,
    StoredProjectionSnapshot,
)


def _snap(
    level: str = "l0",
    lens: str = "structural",
    profile: str = "archimate",
    projected_at: str = "2025-01-15T10:00:00Z",
) -> StoredProjectionSnapshot:
    return StoredProjectionSnapshot(
        storage_id="",
        profile_name=profile,
        level=level,
        lens=lens,
        node_count=10,
        edge_count=5,
        projected_at=projected_at,
    )


def _changeset(
    changes: tuple[ProjectionChange, ...],
    changeset_id: str = "cs-001",
) -> ProjectionChangeSet:
    return ProjectionChangeSet(
        changeset_id=changeset_id,
        from_version="v1",
        to_version="v2",
        created_at="2025-01-20T10:00:00Z",
        changes=changes,
    )


class TestProjectionPropagationEngine:

    def test_empty_changeset(self):
        store = InMemoryProjectionStore()
        engine = ProjectionPropagationEngine(store)

        cs = _changeset(())
        report = engine.evaluate(cs)

        assert report.severity == PropagationSeverity.NONE
        assert report.safe_to_apply is True
        assert len(report.affected_projections) == 0

    def test_no_matching_records(self):
        store = InMemoryProjectionStore()
        store.store(_snap("l0"))

        engine = ProjectionPropagationEngine(store)
        cs = _changeset((
            ProjectionChange("c1", ProjectionChangeAction.LEVEL_REMOVED, level="l3"),
        ))

        report = engine.evaluate(cs)

        assert report.severity == PropagationSeverity.NONE
        assert report.total_projections_scanned == 1

    def test_level_removal_affects_projections(self):
        store = InMemoryProjectionStore()
        store.store(_snap("l0"))
        store.store(_snap("l0", projected_at="2025-01-16T10:00:00Z"))
        store.store(_snap("l1"))

        engine = ProjectionPropagationEngine(store)
        cs = _changeset((
            ProjectionChange("c1", ProjectionChangeAction.LEVEL_REMOVED, level="l0"),
        ))

        report = engine.evaluate(cs)

        assert report.total_projections_scanned == 3
        assert len(report.affected_projections) == 2
        assert report.projections_becoming_stale == 2
        assert all(a.potential_staleness for a in report.affected_projections)

    def test_filter_change_marks_stale(self):
        store = InMemoryProjectionStore()
        store.store(_snap("l0"))

        engine = ProjectionPropagationEngine(store)
        cs = _changeset((
            ProjectionChange("c1", ProjectionChangeAction.FILTER_CHANGED, level="l0"),
        ))

        report = engine.evaluate(cs)

        assert len(report.affected_projections) == 1
        assert report.projections_becoming_stale == 1
        assert report.affected_projections[0].potential_staleness is True

    def test_lens_change_affects_matching_projections(self):
        store = InMemoryProjectionStore()
        store.store(_snap("l0", lens="structural"))
        store.store(_snap("l0", lens="behavioral"))

        engine = ProjectionPropagationEngine(store)
        cs = _changeset((
            ProjectionChange("c1", ProjectionChangeAction.LENS_CHANGED, lens="structural"),
        ))

        report = engine.evaluate(cs)

        assert len(report.affected_projections) == 1
        assert report.affected_projections[0].lens == "structural"

    def test_severity_low(self):
        store = InMemoryProjectionStore()
        for i in range(20):
            store.store(_snap(f"l{i}", projected_at=f"2025-01-{i+1:02d}T10:00:00Z"))
        store.store(_snap("l-target"))

        engine = ProjectionPropagationEngine(store)
        cs = _changeset((
            ProjectionChange("c1", ProjectionChangeAction.LENS_CHANGED, level="l-target"),
        ))

        report = engine.evaluate(cs)

        assert report.severity == PropagationSeverity.LOW
        assert report.safe_to_apply is True

    def test_severity_critical_high_rate(self):
        store = InMemoryProjectionStore()
        for i in range(5):
            store.store(_snap("l0", projected_at=f"2025-01-{i+1:02d}T10:00:00Z"))

        engine = ProjectionPropagationEngine(store)
        cs = _changeset((
            ProjectionChange("c1", ProjectionChangeAction.LEVEL_REMOVED, level="l0"),
        ))

        report = engine.evaluate(cs)

        assert report.severity == PropagationSeverity.CRITICAL
        assert report.safe_to_apply is False

    def test_analysis_period(self):
        store = InMemoryProjectionStore()
        store.store(_snap("l0", projected_at="2025-01-01T10:00:00Z"))
        store.store(_snap("l0", projected_at="2025-01-31T10:00:00Z"))

        engine = ProjectionPropagationEngine(store)
        cs = _changeset((
            ProjectionChange("c1", ProjectionChangeAction.FILTER_CHANGED, level="l0"),
        ))

        report = engine.evaluate(cs)

        assert report.analysis_period_start == "2025-01-01T10:00:00Z"
        assert report.analysis_period_end == "2025-01-31T10:00:00Z"

    def test_affected_lenses(self):
        store = InMemoryProjectionStore()
        store.store(_snap("l0", lens="structural"))
        store.store(_snap("l0", lens="behavioral"))

        engine = ProjectionPropagationEngine(store)
        cs = _changeset((
            ProjectionChange("c1", ProjectionChangeAction.LEVEL_REMOVED, level="l0"),
        ))

        report = engine.evaluate(cs)

        assert "structural" in report.affected_lenses
        assert "behavioral" in report.affected_lenses

    def test_unique_levels_affected(self):
        store = InMemoryProjectionStore()
        store.store(_snap("l0"))
        store.store(_snap("l1"))

        engine = ProjectionPropagationEngine(store)
        cs = _changeset((
            ProjectionChange("c1", ProjectionChangeAction.LEVEL_REMOVED, level="l0"),
            ProjectionChange("c2", ProjectionChangeAction.LEVEL_REMOVED, level="l1"),
        ))

        report = engine.evaluate(cs)

        assert report.unique_levels_affected == 2

    def test_risk_factors_multiple_level_removals(self):
        store = InMemoryProjectionStore()
        for i in range(5):
            store.store(_snap(f"l{i}"))

        engine = ProjectionPropagationEngine(store)
        changes = tuple(
            ProjectionChange(f"c{i}", ProjectionChangeAction.LEVEL_REMOVED, level=f"l{i}")
            for i in range(5)
        )
        cs = _changeset(changes)

        report = engine.evaluate(cs)

        assert any("removed" in r.lower() for r in report.risk_factors)


class TestProjectionChangeSet:

    def test_is_empty(self):
        cs = _changeset(())
        assert cs.is_empty is True

    def test_categorized_properties(self):
        changes = (
            ProjectionChange("c1", ProjectionChangeAction.LEVEL_ADDED, level="l3"),
            ProjectionChange("c2", ProjectionChangeAction.LEVEL_REMOVED, level="l2"),
            ProjectionChange("c3", ProjectionChangeAction.FILTER_CHANGED, level="l0"),
            ProjectionChange("c4", ProjectionChangeAction.LENS_CHANGED, lens="behavioral"),
        )
        cs = _changeset(changes)

        assert len(cs.level_removals) == 1
        assert len(cs.filter_changes) == 1
        assert cs.is_empty is False


class TestProjectionPropagationReport:

    def test_impact_rate_zero_division(self):
        report = ProjectionPropagationReport(
            report_id="r1",
            changeset_id="cs1",
            created_at="now",
            total_projections_scanned=0,
        )
        assert report.impact_rate == 0.0
