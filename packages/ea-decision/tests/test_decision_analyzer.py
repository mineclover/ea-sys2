"""Tests for DecisionAnalyzer — S4 Analysis."""

from __future__ import annotations

from ea_decision.decision_analyzer import (
    DecisionAnalysisReport,
    DecisionAnalyzer,
    EvaluationConsistency,
    PatternEffectiveness,
    PatternEffectivenessGrade,
)
from ea_decision.topic_store import (
    DecisionSnapshotStatus,
    InMemoryTopicStore,
    StoredDecisionSnapshot,
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
    )


def _populated_store() -> InMemoryTopicStore:
    """Create a store with diverse test data."""
    store = InMemoryTopicStore()

    # TradeOff: 10 decisions, 8 accepted, 2 rejected, good scores
    for i in range(8):
        store.store(_make_snapshot(
            topic_id=f"to-{i}", pattern_name="TradeOff",
            evaluation_score=0.8, status=DecisionSnapshotStatus.ACCEPTED,
            decided_at=f"2025-01-{10 + i:02d}T10:00:00Z",
        ))
    for i in range(2):
        store.store(_make_snapshot(
            topic_id=f"to-rej-{i}", pattern_name="TradeOff",
            evaluation_score=0.3, status=DecisionSnapshotStatus.REJECTED,
            decided_at=f"2025-01-{20 + i:02d}T10:00:00Z",
        ))

    # Compliance: 3 decisions, all accepted, high scores
    for i in range(3):
        store.store(_make_snapshot(
            topic_id=f"co-{i}", pattern_name="Compliance",
            evaluation_score=0.9, status=DecisionSnapshotStatus.ACCEPTED,
        ))

    # Deprecated pattern: 5 decisions, 1 accepted, 4 rejected, low scores
    store.store(_make_snapshot(
        topic_id="dep-ok", pattern_name="Legacy",
        evaluation_score=0.4, status=DecisionSnapshotStatus.ACCEPTED,
    ))
    for i in range(4):
        store.store(_make_snapshot(
            topic_id=f"dep-{i}", pattern_name="Legacy",
            evaluation_score=0.2, status=DecisionSnapshotStatus.REJECTED,
        ))

    return store


# ── PatternEffectiveness Tests ──────────────────────────────────────────

class TestPatternEffectiveness:
    def test_grade_unused(self):
        eff = PatternEffectiveness(pattern_name="Empty")
        assert eff.grade == PatternEffectivenessGrade.UNUSED
        assert eff.acceptance_rate == 0.0

    def test_grade_highly_effective(self):
        eff = PatternEffectiveness(
            pattern_name="Great",
            total_decisions=20,
            accepted_count=18,
            rejected_count=2,
            avg_evaluation_score=0.85,
        )
        assert eff.grade == PatternEffectivenessGrade.HIGHLY_EFFECTIVE
        assert eff.acceptance_rate == 0.9

    def test_grade_effective(self):
        eff = PatternEffectiveness(
            pattern_name="Good",
            total_decisions=10,
            accepted_count=6,
            rejected_count=4,
            avg_evaluation_score=0.5,
        )
        assert eff.grade == PatternEffectivenessGrade.EFFECTIVE

    def test_grade_marginally_effective(self):
        eff = PatternEffectiveness(
            pattern_name="New",
            total_decisions=3,
            accepted_count=2,
            rejected_count=1,
            avg_evaluation_score=0.3,
        )
        assert eff.grade == PatternEffectivenessGrade.MARGINALLY_EFFECTIVE

    def test_grade_ineffective(self):
        eff = PatternEffectiveness(
            pattern_name="Bad",
            total_decisions=10,
            accepted_count=2,
            rejected_count=8,
            avg_evaluation_score=0.2,
        )
        assert eff.grade == PatternEffectivenessGrade.INEFFECTIVE

    def test_revision_rate(self):
        eff = PatternEffectiveness(
            pattern_name="Rev",
            total_decisions=10,
            deprecated_count=3,
        )
        assert eff.revision_rate == 0.3

    def test_execution_success_rate(self):
        eff = PatternEffectiveness(
            pattern_name="Cross",
            total_decisions=10,
            accepted_count=8,
            execution_linked_count=6,
            execution_success_count=5,
        )
        assert eff.execution_success_rate == 5 / 6

    def test_execution_success_rate_no_links(self):
        eff = PatternEffectiveness(pattern_name="NoLink")
        assert eff.execution_success_rate == 0.0


# ── EvaluationConsistency Tests ─────────────────────────────────────────

class TestEvaluationConsistency:
    def test_consistency_score_perfect(self):
        ec = EvaluationConsistency(
            pattern_name="Perfect",
            high_score_accepted=10,
            low_score_rejected=5,
            total_analyzed=15,
        )
        assert ec.consistency_score == 1.0

    def test_consistency_score_zero(self):
        ec = EvaluationConsistency(
            pattern_name="Random",
            high_score_rejected=5,
            low_score_accepted=5,
            total_analyzed=10,
        )
        assert ec.consistency_score == 0.0

    def test_consistency_score_empty(self):
        ec = EvaluationConsistency(pattern_name="Empty")
        assert ec.consistency_score == 0.0


# ── DecisionAnalyzer Tests ──────────────────────────────────────────────

class TestDecisionAnalyzer:
    def test_analyze_pattern_effectiveness(self):
        store = _populated_store()
        analyzer = DecisionAnalyzer(store)

        results = analyzer.analyze_pattern_effectiveness()
        assert len(results) == 3

        # Sorted by total_decisions desc
        assert results[0].pattern_name == "TradeOff"
        assert results[0].total_decisions == 10
        assert results[0].accepted_count == 8

    def test_analyze_evaluation_consistency(self):
        store = _populated_store()
        analyzer = DecisionAnalyzer(store)

        results = analyzer.analyze_evaluation_consistency()
        assert len(results) >= 1

        # TradeOff has both high-score-accepted and low-score-rejected
        trade_off = next(
            (r for r in results if r.pattern_name == "TradeOff"), None,
        )
        assert trade_off is not None
        assert trade_off.total_analyzed > 0

    def test_generate_report(self):
        store = _populated_store()
        analyzer = DecisionAnalyzer(store)

        report = analyzer.generate_report()
        assert report.report_id.startswith("decision-report-")
        assert report.created_at != ""
        assert report.total_decisions_analyzed == 18
        assert len(report.pattern_effectiveness) == 3
        assert report.health_score > 0

    def test_generate_report_custom_id(self):
        store = _populated_store()
        analyzer = DecisionAnalyzer(store)

        report = analyzer.generate_report(report_id="custom-id")
        assert report.report_id == "custom-id"

    def test_generate_report_empty_store(self):
        store = InMemoryTopicStore()
        analyzer = DecisionAnalyzer(store)

        report = analyzer.generate_report()
        assert report.total_decisions_analyzed == 0
        assert len(report.pattern_effectiveness) == 0
        assert report.health_score == 0.0

    def test_report_identifies_deprecation_candidates(self):
        store = _populated_store()
        analyzer = DecisionAnalyzer(store)

        report = analyzer.generate_report()
        # Legacy pattern should be flagged for deprecation
        assert "Legacy" in report.patterns_for_deprecation

    def test_cross_layer_execution_feedback(self):
        """S5/S6: Analyzer populates execution metrics from snapshot execution_success."""
        store = InMemoryTopicStore()
        # 3 snapshots with execution feedback
        store.store(_make_snapshot(
            topic_id="exec-1", pattern_name="TradeOff",
            status=DecisionSnapshotStatus.ACCEPTED,
        ))
        store.store(StoredDecisionSnapshot(
            storage_id="", topic_id="exec-2", pattern_name="TradeOff",
            complexity="structural", option_count=3, evaluation_score=0.8,
            decided_at="2025-01-16T10:00:00Z",
            status=DecisionSnapshotStatus.ACCEPTED,
            execution_success=True,
        ))
        store.store(StoredDecisionSnapshot(
            storage_id="", topic_id="exec-3", pattern_name="TradeOff",
            complexity="structural", option_count=2, evaluation_score=0.6,
            decided_at="2025-01-17T10:00:00Z",
            status=DecisionSnapshotStatus.REJECTED,
            execution_success=False,
        ))

        analyzer = DecisionAnalyzer(store)
        results = analyzer.analyze_pattern_effectiveness()
        assert len(results) == 1

        trade_off = results[0]
        assert trade_off.execution_linked_count == 2
        assert trade_off.execution_success_count == 1
        assert trade_off.execution_success_rate == 0.5

    def test_report_period_range(self):
        store = _populated_store()
        analyzer = DecisionAnalyzer(store)

        report = analyzer.generate_report()
        assert report.analysis_period_start != ""
        assert report.analysis_period_end != ""
        assert report.analysis_period_start <= report.analysis_period_end
