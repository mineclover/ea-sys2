"""Tests for FlowAnalyzer — S4 Analysis."""

from __future__ import annotations

from ea_flow.execution_store import (
    InMemoryExecutionStore,
    StepResultSummary,
    StoredExecutionRecord,
)
from ea_flow.flow_analyzer import (
    BottleneckHotspot,
    BottleneckSeverity,
    FlowAnalysisReport,
    FlowAnalyzer,
    StepEffectiveness,
    StepEffectivenessGrade,
)


# ── Factory ─────────────────────────────────────────────────────────────

def _make_record(
    workflow_name: str = "validate-model",
    success: bool = True,
    total_steps: int = 3,
    completed_steps: int = 3,
    failed_step: str = "",
    rollback_occurred: bool = False,
    duration_ms: int = 100,
    executed_at: str = "2025-01-15T10:00:00Z",
    step_results: tuple[StepResultSummary, ...] | None = None,
) -> StoredExecutionRecord:
    if step_results is None:
        step_results = (
            StepResultSummary("step-a", accepted=True, kernel_anchor="el"),
            StepResultSummary("step-b", accepted=True, kernel_anchor="ft"),
            StepResultSummary("step-c", accepted=success, kernel_anchor="ty"),
        )
    return StoredExecutionRecord(
        storage_id="",
        workflow_name=workflow_name,
        success=success,
        total_steps=total_steps,
        completed_steps=completed_steps,
        failed_step=failed_step,
        rollback_occurred=rollback_occurred,
        duration_ms=duration_ms,
        executed_at=executed_at,
        step_results=step_results,
    )


def _populated_store() -> InMemoryExecutionStore:
    """Create store with diverse test data."""
    store = InMemoryExecutionStore()

    # 8 successful runs
    for i in range(8):
        store.store(_make_record(
            executed_at=f"2025-01-{10 + i:02d}T10:00:00Z",
        ))

    # 3 failures at step-c with rollback
    for i in range(3):
        store.store(_make_record(
            success=False,
            completed_steps=2,
            failed_step="step-c",
            rollback_occurred=True,
            executed_at=f"2025-01-{20 + i:02d}T10:00:00Z",
            step_results=(
                StepResultSummary("step-a", accepted=True),
                StepResultSummary("step-b", accepted=True),
                StepResultSummary("step-c", accepted=False),
            ),
        ))

    # 2 failures at step-a (early failure)
    for i in range(2):
        store.store(_make_record(
            workflow_name="other-flow",
            success=False,
            completed_steps=0,
            failed_step="step-a",
            rollback_occurred=True,
            total_steps=2,
            executed_at=f"2025-02-{10 + i:02d}T10:00:00Z",
            step_results=(
                StepResultSummary("step-a", accepted=False),
            ),
        ))

    return store


# ── StepEffectiveness Tests ─────────────────────────────────────────────

class TestStepEffectiveness:
    def test_grade_unused(self):
        eff = StepEffectiveness(step_name="empty")
        assert eff.grade == StepEffectivenessGrade.UNUSED
        assert eff.success_rate == 0.0

    def test_grade_highly_reliable(self):
        eff = StepEffectiveness(
            step_name="rock-solid",
            total_executions=100,
            success_count=98,
            failure_count=2,
        )
        assert eff.grade == StepEffectivenessGrade.HIGHLY_RELIABLE

    def test_grade_reliable(self):
        eff = StepEffectiveness(
            step_name="ok",
            total_executions=10,
            success_count=8,
            failure_count=2,
        )
        assert eff.grade == StepEffectivenessGrade.RELIABLE

    def test_grade_fragile(self):
        eff = StepEffectiveness(
            step_name="shaky",
            total_executions=10,
            success_count=5,
            failure_count=5,
        )
        assert eff.grade == StepEffectivenessGrade.FRAGILE

    def test_grade_broken(self):
        eff = StepEffectiveness(
            step_name="dead",
            total_executions=10,
            success_count=1,
            failure_count=9,
        )
        assert eff.grade == StepEffectivenessGrade.BROKEN

    def test_rollback_trigger_rate(self):
        eff = StepEffectiveness(
            step_name="trigger",
            total_executions=10,
            rollback_trigger_count=3,
        )
        assert eff.rollback_trigger_rate == 0.3


# ── BottleneckHotspot Tests ─────────────────────────────────────────────

class TestBottleneckHotspot:
    def test_severity_critical(self):
        h = BottleneckHotspot(
            step_name="bad", workflow_name="wf",
            failure_count=10, rollback_trigger_count=5,
        )
        assert h.severity == BottleneckSeverity.CRITICAL

    def test_severity_high(self):
        h = BottleneckHotspot(
            step_name="bad", workflow_name="wf",
            failure_count=5, rollback_trigger_count=2,
        )
        assert h.severity == BottleneckSeverity.HIGH

    def test_severity_medium(self):
        h = BottleneckHotspot(
            step_name="bad", workflow_name="wf",
            failure_count=3,
        )
        assert h.severity == BottleneckSeverity.MEDIUM

    def test_severity_low(self):
        h = BottleneckHotspot(
            step_name="bad", workflow_name="wf",
            failure_count=1,
        )
        assert h.severity == BottleneckSeverity.LOW


# ── FlowAnalyzer Tests ──────────────────────────────────────────────────

class TestFlowAnalyzer:
    def test_analyze_step_effectiveness(self):
        store = _populated_store()
        analyzer = FlowAnalyzer(store)

        results = analyzer.analyze_step_effectiveness()
        assert len(results) >= 2

        step_a = next(s for s in results if s.step_name == "step-a")
        assert step_a.total_executions > 0
        assert step_a.success_count > 0

    def test_step_effectiveness_tracks_failures(self):
        store = _populated_store()
        analyzer = FlowAnalyzer(store)

        results = analyzer.analyze_step_effectiveness()
        step_c = next(s for s in results if s.step_name == "step-c")
        assert step_c.failure_count == 3
        assert step_c.rollback_trigger_count == 3

    def test_detect_bottleneck_hotspots(self):
        store = _populated_store()
        analyzer = FlowAnalyzer(store)

        hotspots = analyzer.detect_bottleneck_hotspots(min_failures=2)
        assert len(hotspots) >= 1

        # step-c should be detected
        step_c_hotspot = next(
            (h for h in hotspots if h.step_name == "step-c"), None,
        )
        assert step_c_hotspot is not None
        assert step_c_hotspot.failure_count == 3

    def test_detect_bottleneck_min_failures_filter(self):
        store = _populated_store()
        analyzer = FlowAnalyzer(store)

        # High threshold should filter more
        hotspots = analyzer.detect_bottleneck_hotspots(min_failures=5)
        assert len(hotspots) == 0

    def test_generate_report(self):
        store = _populated_store()
        analyzer = FlowAnalyzer(store)

        report = analyzer.generate_report()
        assert report.report_id.startswith("flow-report-")
        assert report.created_at != ""
        assert report.total_executions_analyzed == 13
        assert len(report.step_effectiveness) >= 2
        assert report.health_score > 0

    def test_generate_report_empty_store(self):
        store = InMemoryExecutionStore()
        analyzer = FlowAnalyzer(store)

        report = analyzer.generate_report()
        assert report.total_executions_analyzed == 0
        assert report.health_score == 0.0

    def test_report_identifies_broken_steps(self):
        store = InMemoryExecutionStore()
        # All failures for step-x
        for i in range(10):
            store.store(StoredExecutionRecord(
                storage_id="",
                workflow_name="wf",
                success=False,
                total_steps=1,
                completed_steps=0,
                failed_step="step-x",
                rollback_occurred=True,
                duration_ms=10,
                executed_at=f"2025-01-{10 + i:02d}T00:00:00Z",
                step_results=(
                    StepResultSummary("step-x", accepted=False),
                ),
            ))

        analyzer = FlowAnalyzer(store)
        report = analyzer.generate_report()
        assert "step-x" in report.broken_steps

    def test_report_period_range(self):
        store = _populated_store()
        analyzer = FlowAnalyzer(store)

        report = analyzer.generate_report()
        assert report.analysis_period_start != ""
        assert report.analysis_period_end != ""
        assert report.analysis_period_start <= report.analysis_period_end
