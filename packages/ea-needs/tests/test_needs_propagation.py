"""Tests for NeedsPropagationEngine — S6 Propagation."""

from __future__ import annotations

from ea_needs.needs_propagation import (
    AffectedNeedSnapshot,
    NeedsChange,
    NeedsChangeAction,
    NeedsChangeSet,
    NeedsPropagationEngine,
    NeedsPropagationReport,
    PropagationSeverity,
)
from ea_needs.needs_store import (
    InMemoryNeedStore,
    NeedSnapshotStatus,
    StoredNeedSnapshot,
)


def _snap(
    stakeholder: str = "sh-001",
    status: NeedSnapshotStatus = NeedSnapshotStatus.EXPRESSED,
    priority: str = "high",
    expressed_at: str = "2025-01-15T10:00:00Z",
) -> StoredNeedSnapshot:
    return StoredNeedSnapshot(
        storage_id="",
        need_id=f"need-{stakeholder}",
        lineage_id=f"lineage-{stakeholder}",
        stakeholder_id=stakeholder,
        status=status,
        priority=priority,
        complexity="medium",
        expressed_at=expressed_at,
    )


def _changeset(
    changes: tuple[NeedsChange, ...],
    changeset_id: str = "cs-001",
) -> NeedsChangeSet:
    return NeedsChangeSet(
        changeset_id=changeset_id,
        from_version="v1",
        to_version="v2",
        created_at="2025-01-20T10:00:00Z",
        changes=changes,
    )


class TestNeedsPropagationEngine:

    def test_empty_changeset(self):
        store = InMemoryNeedStore()
        engine = NeedsPropagationEngine(store)

        cs = _changeset(())
        report = engine.evaluate(cs)

        assert report.severity == PropagationSeverity.NONE
        assert report.safe_to_apply is True
        assert len(report.affected_needs) == 0

    def test_no_matching_records(self):
        store = InMemoryNeedStore()
        store.store(_snap("sh-other"))

        engine = NeedsPropagationEngine(store)
        cs = _changeset((
            NeedsChange("c1", NeedsChangeAction.STAKEHOLDER_REMOVED, stakeholder_id="sh-xyz"),
        ))

        report = engine.evaluate(cs)

        assert report.severity == PropagationSeverity.NONE
        assert report.total_needs_scanned == 1

    def test_stakeholder_removal_affects_needs(self):
        store = InMemoryNeedStore()
        store.store(_snap("sh-001"))
        store.store(_snap("sh-001", expressed_at="2025-01-16T10:00:00Z"))
        store.store(_snap("sh-002"))

        engine = NeedsPropagationEngine(store)
        cs = _changeset((
            NeedsChange("c1", NeedsChangeAction.STAKEHOLDER_REMOVED, stakeholder_id="sh-001"),
        ))

        report = engine.evaluate(cs)

        assert report.total_needs_scanned == 3
        assert len(report.affected_needs) == 2
        assert report.needs_with_status_change == 2
        assert all(a.potential_status_change for a in report.affected_needs)

    def test_priority_change_affects_needs(self):
        store = InMemoryNeedStore()
        store.store(_snap("sh-001", priority="high"))
        store.store(_snap("sh-002", priority="low"))

        engine = NeedsPropagationEngine(store)
        cs = _changeset((
            NeedsChange("c1", NeedsChangeAction.PRIORITY_CHANGED, priority="high"),
        ))

        report = engine.evaluate(cs)

        assert len(report.affected_needs) == 1
        assert report.affected_needs[0].original_priority == "high"
        assert report.needs_with_status_change == 0

    def test_severity_low(self):
        store = InMemoryNeedStore()
        for i in range(20):
            store.store(_snap(f"sh-{i}", expressed_at=f"2025-01-{i+1:02d}T10:00:00Z"))
        store.store(_snap("sh-target"))

        engine = NeedsPropagationEngine(store)
        cs = _changeset((
            NeedsChange("c1", NeedsChangeAction.STATUS_CHANGED, stakeholder_id="sh-target"),
        ))

        report = engine.evaluate(cs)

        assert report.severity == PropagationSeverity.LOW
        assert report.safe_to_apply is True

    def test_severity_critical_high_rate(self):
        store = InMemoryNeedStore()
        for i in range(5):
            store.store(_snap("sh-001", expressed_at=f"2025-01-{i+1:02d}T10:00:00Z"))

        engine = NeedsPropagationEngine(store)
        cs = _changeset((
            NeedsChange("c1", NeedsChangeAction.STAKEHOLDER_REMOVED, stakeholder_id="sh-001"),
        ))

        report = engine.evaluate(cs)

        assert report.severity == PropagationSeverity.CRITICAL
        assert report.safe_to_apply is False

    def test_analysis_period(self):
        store = InMemoryNeedStore()
        store.store(_snap("sh-001", expressed_at="2025-01-01T10:00:00Z"))
        store.store(_snap("sh-001", expressed_at="2025-01-31T10:00:00Z"))

        engine = NeedsPropagationEngine(store)
        cs = _changeset((
            NeedsChange("c1", NeedsChangeAction.STATUS_CHANGED, stakeholder_id="sh-001"),
        ))

        report = engine.evaluate(cs)

        assert report.analysis_period_start == "2025-01-01T10:00:00Z"
        assert report.analysis_period_end == "2025-01-31T10:00:00Z"

    def test_affected_priorities(self):
        store = InMemoryNeedStore()
        store.store(_snap("sh-001", priority="high"))
        store.store(_snap("sh-001", priority="low"))

        engine = NeedsPropagationEngine(store)
        cs = _changeset((
            NeedsChange("c1", NeedsChangeAction.STAKEHOLDER_REMOVED, stakeholder_id="sh-001"),
        ))

        report = engine.evaluate(cs)

        assert "high" in report.affected_priorities
        assert "low" in report.affected_priorities

    def test_unique_stakeholders_affected(self):
        store = InMemoryNeedStore()
        store.store(_snap("sh-001"))
        store.store(_snap("sh-002"))

        engine = NeedsPropagationEngine(store)
        cs = _changeset((
            NeedsChange("c1", NeedsChangeAction.STAKEHOLDER_REMOVED, stakeholder_id="sh-001"),
            NeedsChange("c2", NeedsChangeAction.STAKEHOLDER_REMOVED, stakeholder_id="sh-002"),
        ))

        report = engine.evaluate(cs)

        assert report.unique_stakeholders_affected == 2

    def test_risk_factors_multiple_removals(self):
        store = InMemoryNeedStore()
        for i in range(5):
            store.store(_snap(f"sh-{i}"))

        engine = NeedsPropagationEngine(store)
        changes = tuple(
            NeedsChange(f"c{i}", NeedsChangeAction.STAKEHOLDER_REMOVED, stakeholder_id=f"sh-{i}")
            for i in range(5)
        )
        cs = _changeset(changes)

        report = engine.evaluate(cs)

        assert any("removed" in r.lower() for r in report.risk_factors)


class TestNeedsChangeSet:

    def test_is_empty(self):
        cs = _changeset(())
        assert cs.is_empty is True

    def test_categorized_properties(self):
        changes = (
            NeedsChange("c1", NeedsChangeAction.STAKEHOLDER_ADDED, stakeholder_id="s1"),
            NeedsChange("c2", NeedsChangeAction.STAKEHOLDER_REMOVED, stakeholder_id="s2"),
            NeedsChange("c3", NeedsChangeAction.PRIORITY_CHANGED, priority="high"),
        )
        cs = _changeset(changes)

        assert len(cs.stakeholder_removals) == 1
        assert len(cs.priority_changes) == 1
        assert cs.is_empty is False


class TestNeedsPropagationReport:

    def test_impact_rate_zero_division(self):
        report = NeedsPropagationReport(
            report_id="r1",
            changeset_id="cs1",
            created_at="now",
            total_needs_scanned=0,
        )
        assert report.impact_rate == 0.0
