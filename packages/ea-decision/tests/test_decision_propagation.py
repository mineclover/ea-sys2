"""Tests for DecisionPropagationEngine — S6 Propagation."""

from __future__ import annotations

from ea_decision.decision_propagation import (
    AffectedDecisionSnapshot,
    DecisionPropagationEngine,
    DecisionPropagationReport,
    PatternChange,
    PatternChangeAction,
    PatternChangeSet,
    PropagationSeverity,
)
from ea_decision.topic_store import (
    DecisionSnapshotStatus,
    InMemoryTopicStore,
    StoredDecisionSnapshot,
)


def _snap(
    pattern: str,
    status: DecisionSnapshotStatus = DecisionSnapshotStatus.ACCEPTED,
    complexity: str = "medium",
    decided_at: str = "2025-01-15T10:00:00Z",
) -> StoredDecisionSnapshot:
    return StoredDecisionSnapshot(
        storage_id="",
        topic_id=f"topic-{pattern}",
        pattern_name=pattern,
        complexity=complexity,
        option_count=3,
        evaluation_score=0.8,
        decided_at=decided_at,
        status=status,
    )


def _changeset(
    changes: tuple[PatternChange, ...],
    changeset_id: str = "cs-001",
) -> PatternChangeSet:
    return PatternChangeSet(
        changeset_id=changeset_id,
        from_version="v1",
        to_version="v2",
        created_at="2025-01-20T10:00:00Z",
        changes=changes,
    )


class TestDecisionPropagationEngine:

    def test_empty_changeset(self):
        store = InMemoryTopicStore()
        engine = DecisionPropagationEngine(store)

        cs = _changeset(())
        report = engine.evaluate(cs)

        assert report.severity == PropagationSeverity.NONE
        assert report.safe_to_apply is True
        assert len(report.affected_decisions) == 0
        assert "No changes" in report.recommendation

    def test_no_matching_records(self):
        store = InMemoryTopicStore()
        store.store(_snap("pattern-A"))

        engine = DecisionPropagationEngine(store)
        cs = _changeset((
            PatternChange("pattern-X", PatternChangeAction.REMOVED),
        ))

        report = engine.evaluate(cs)

        assert report.severity == PropagationSeverity.NONE
        assert len(report.affected_decisions) == 0
        assert report.total_decisions_scanned == 1

    def test_pattern_removal_affects_decisions(self):
        store = InMemoryTopicStore()
        store.store(_snap("binary-choice"))
        store.store(_snap("binary-choice", decided_at="2025-01-16T10:00:00Z"))
        store.store(_snap("multi-criteria"))

        engine = DecisionPropagationEngine(store)
        cs = _changeset((
            PatternChange("binary-choice", PatternChangeAction.REMOVED),
        ))

        report = engine.evaluate(cs)

        assert report.total_decisions_scanned == 3
        assert len(report.affected_decisions) == 2
        assert report.decisions_with_status_change == 2
        assert report.decisions_with_pattern_involvement == 2
        assert all(a.potential_status_change for a in report.affected_decisions)
        assert report.severity != PropagationSeverity.NONE

    def test_pattern_modification_no_status_change(self):
        store = InMemoryTopicStore()
        store.store(_snap("binary-choice"))

        engine = DecisionPropagationEngine(store)
        cs = _changeset((
            PatternChange(
                "binary-choice",
                PatternChangeAction.MODIFIED,
                description="Updated evaluation criteria",
            ),
        ))

        report = engine.evaluate(cs)

        assert len(report.affected_decisions) == 1
        assert report.decisions_with_status_change == 0
        assert not report.affected_decisions[0].potential_status_change

    def test_severity_low(self):
        store = InMemoryTopicStore()
        for i in range(20):
            store.store(_snap(f"pattern-{i}", decided_at=f"2025-01-{i+1:02d}T10:00:00Z"))
        store.store(_snap("target-pattern"))

        engine = DecisionPropagationEngine(store)
        cs = _changeset((
            PatternChange("target-pattern", PatternChangeAction.MODIFIED),
        ))

        report = engine.evaluate(cs)

        assert report.severity == PropagationSeverity.LOW
        assert report.safe_to_apply is True

    def test_severity_critical_high_rate(self):
        store = InMemoryTopicStore()
        for i in range(5):
            store.store(_snap("same-pattern", decided_at=f"2025-01-{i+1:02d}T10:00:00Z"))

        engine = DecisionPropagationEngine(store)
        cs = _changeset((
            PatternChange("same-pattern", PatternChangeAction.REMOVED),
        ))

        report = engine.evaluate(cs)

        assert report.severity == PropagationSeverity.CRITICAL
        assert report.safe_to_apply is False

    def test_analysis_period(self):
        store = InMemoryTopicStore()
        store.store(_snap("p1", decided_at="2025-01-01T10:00:00Z"))
        store.store(_snap("p1", decided_at="2025-01-31T10:00:00Z"))

        engine = DecisionPropagationEngine(store)
        cs = _changeset((
            PatternChange("p1", PatternChangeAction.MODIFIED),
        ))

        report = engine.evaluate(cs)

        assert report.analysis_period_start == "2025-01-01T10:00:00Z"
        assert report.analysis_period_end == "2025-01-31T10:00:00Z"

    def test_affected_complexities(self):
        store = InMemoryTopicStore()
        store.store(_snap("p1", complexity="low"))
        store.store(_snap("p1", complexity="high"))

        engine = DecisionPropagationEngine(store)
        cs = _changeset((
            PatternChange("p1", PatternChangeAction.REMOVED),
        ))

        report = engine.evaluate(cs)

        assert "low" in report.affected_complexities
        assert "high" in report.affected_complexities

    def test_risk_factors_multiple_removals(self):
        store = InMemoryTopicStore()
        for i in range(5):
            store.store(_snap(f"p-{i}"))

        engine = DecisionPropagationEngine(store)
        changes = tuple(
            PatternChange(f"p-{i}", PatternChangeAction.REMOVED)
            for i in range(5)
        )
        cs = _changeset(changes)

        report = engine.evaluate(cs)

        assert any("removed" in r.lower() for r in report.risk_factors)

    def test_impact_rate(self):
        store = InMemoryTopicStore()
        store.store(_snap("p1"))
        store.store(_snap("p2"))
        store.store(_snap("p3"))
        store.store(_snap("p4"))

        engine = DecisionPropagationEngine(store)
        cs = _changeset((
            PatternChange("p1", PatternChangeAction.MODIFIED),
        ))

        report = engine.evaluate(cs)

        assert report.impact_rate == 0.25


class TestPatternChangeSet:

    def test_is_empty(self):
        cs = _changeset(())
        assert cs.is_empty is True

    def test_categorized_properties(self):
        changes = (
            PatternChange("a", PatternChangeAction.ADDED),
            PatternChange("b", PatternChangeAction.REMOVED),
            PatternChange("c", PatternChangeAction.MODIFIED),
            PatternChange("d", PatternChangeAction.EFFECTIVENESS_CHANGED),
        )
        cs = _changeset(changes)

        assert len(cs.added_patterns) == 1
        assert len(cs.removed_patterns) == 1
        assert len(cs.modified_patterns) == 1
        assert cs.is_empty is False


class TestPropagationReport:

    def test_impact_rate_zero_division(self):
        report = DecisionPropagationReport(
            report_id="r1",
            changeset_id="cs1",
            created_at="now",
            total_decisions_scanned=0,
        )
        assert report.impact_rate == 0.0
