"""Tests for FlowPropagationEngine — S6 Propagation."""

from __future__ import annotations

from ea_flow.execution_store import (
    InMemoryExecutionStore,
    StepResultSummary,
    StoredExecutionRecord,
)
from ea_flow.flow_propagation import (
    AffectedExecutionRecord,
    FlowPropagationEngine,
    FlowPropagationReport,
    PropagationSeverity,
    WorkflowChange,
    WorkflowChangeAction,
    WorkflowChangeSet,
)


def _rec(
    workflow: str = "wf-main",
    success: bool = True,
    steps: tuple[str, ...] = ("step-a", "step-b"),
    executed_at: str = "2025-01-15T10:00:00Z",
    failed_step: str = "",
) -> StoredExecutionRecord:
    return StoredExecutionRecord(
        storage_id="",
        workflow_name=workflow,
        success=success,
        total_steps=len(steps),
        completed_steps=len(steps) if success else len(steps) - 1,
        failed_step=failed_step,
        rollback_occurred=not success,
        duration_ms=100,
        executed_at=executed_at,
        step_results=tuple(
            StepResultSummary(step_name=s, accepted=success)
            for s in steps
        ),
    )


def _changeset(
    changes: tuple[WorkflowChange, ...],
    changeset_id: str = "cs-001",
) -> WorkflowChangeSet:
    return WorkflowChangeSet(
        changeset_id=changeset_id,
        from_version="v1",
        to_version="v2",
        created_at="2025-01-20T10:00:00Z",
        changes=changes,
    )


class TestFlowPropagationEngine:

    def test_empty_changeset(self):
        store = InMemoryExecutionStore()
        engine = FlowPropagationEngine(store)

        cs = _changeset(())
        report = engine.evaluate(cs)

        assert report.severity == PropagationSeverity.NONE
        assert report.safe_to_apply is True
        assert len(report.affected_executions) == 0

    def test_no_matching_records(self):
        store = InMemoryExecutionStore()
        store.store(_rec("wf-other"))

        engine = FlowPropagationEngine(store)
        cs = _changeset((
            WorkflowChange("wf-main", WorkflowChangeAction.STEP_REMOVED, step_name="step-x"),
        ))

        report = engine.evaluate(cs)

        assert report.severity == PropagationSeverity.NONE
        assert report.total_executions_scanned == 1

    def test_step_removal_affects_executions(self):
        store = InMemoryExecutionStore()
        store.store(_rec("wf-main", steps=("step-a", "step-b")))
        store.store(_rec("wf-main", steps=("step-a", "step-b"), executed_at="2025-01-16T10:00:00Z"))
        store.store(_rec("wf-other"))

        engine = FlowPropagationEngine(store)
        cs = _changeset((
            WorkflowChange("wf-main", WorkflowChangeAction.STEP_REMOVED, step_name="step-a"),
        ))

        report = engine.evaluate(cs)

        assert report.total_executions_scanned == 3
        assert len(report.affected_executions) == 2
        assert report.executions_with_outcome_change == 2
        assert all(a.potential_outcome_change for a in report.affected_executions)

    def test_step_modification_no_outcome_change(self):
        store = InMemoryExecutionStore()
        store.store(_rec("wf-main", steps=("step-a", "step-b")))

        engine = FlowPropagationEngine(store)
        cs = _changeset((
            WorkflowChange(
                "wf-main",
                WorkflowChangeAction.STEP_MODIFIED,
                step_name="step-a",
            ),
        ))

        report = engine.evaluate(cs)

        assert len(report.affected_executions) == 1
        assert report.executions_with_outcome_change == 0
        assert not report.affected_executions[0].potential_outcome_change

    def test_topology_change_affects_all_workflow_records(self):
        store = InMemoryExecutionStore()
        store.store(_rec("wf-main", steps=("step-a",)))
        store.store(_rec("wf-main", steps=("step-b",), executed_at="2025-01-16T10:00:00Z"))

        engine = FlowPropagationEngine(store)
        cs = _changeset((
            WorkflowChange("wf-main", WorkflowChangeAction.TOPOLOGY_CHANGED),
        ))

        report = engine.evaluate(cs)

        assert len(report.affected_executions) == 2
        assert report.executions_with_outcome_change == 2
        assert all(a.potential_outcome_change for a in report.affected_executions)

    def test_severity_low(self):
        store = InMemoryExecutionStore()
        for i in range(20):
            store.store(_rec(f"wf-{i}", executed_at=f"2025-01-{i+1:02d}T10:00:00Z"))
        store.store(_rec("wf-target", steps=("step-x",)))

        engine = FlowPropagationEngine(store)
        cs = _changeset((
            WorkflowChange("wf-target", WorkflowChangeAction.STEP_MODIFIED, step_name="step-x"),
        ))

        report = engine.evaluate(cs)

        assert report.severity == PropagationSeverity.LOW
        assert report.safe_to_apply is True

    def test_severity_critical_high_rate(self):
        store = InMemoryExecutionStore()
        for i in range(5):
            store.store(_rec("wf-main", steps=("step-a",), executed_at=f"2025-01-{i+1:02d}T10:00:00Z"))

        engine = FlowPropagationEngine(store)
        cs = _changeset((
            WorkflowChange("wf-main", WorkflowChangeAction.STEP_REMOVED, step_name="step-a"),
        ))

        report = engine.evaluate(cs)

        assert report.severity == PropagationSeverity.CRITICAL
        assert report.safe_to_apply is False

    def test_affected_steps_and_workflows(self):
        store = InMemoryExecutionStore()
        store.store(_rec("wf-main", steps=("step-a", "step-b")))

        engine = FlowPropagationEngine(store)
        cs = _changeset((
            WorkflowChange("wf-main", WorkflowChangeAction.STEP_MODIFIED, step_name="step-a"),
            WorkflowChange("wf-main", WorkflowChangeAction.STEP_MODIFIED, step_name="step-b"),
        ))

        report = engine.evaluate(cs)

        assert "step-a" in report.affected_steps
        assert "step-b" in report.affected_steps
        assert report.unique_workflows_affected == 1

    def test_risk_factors_topology_change(self):
        store = InMemoryExecutionStore()
        store.store(_rec("wf-main"))

        engine = FlowPropagationEngine(store)
        cs = _changeset((
            WorkflowChange("wf-main", WorkflowChangeAction.TOPOLOGY_CHANGED),
        ))

        report = engine.evaluate(cs)

        assert any("topology" in r.lower() for r in report.risk_factors)

    def test_analysis_period(self):
        store = InMemoryExecutionStore()
        store.store(_rec("wf-main", steps=("s",), executed_at="2025-01-01T10:00:00Z"))
        store.store(_rec("wf-main", steps=("s",), executed_at="2025-01-31T10:00:00Z"))

        engine = FlowPropagationEngine(store)
        cs = _changeset((
            WorkflowChange("wf-main", WorkflowChangeAction.STEP_MODIFIED, step_name="s"),
        ))

        report = engine.evaluate(cs)

        assert report.analysis_period_start == "2025-01-01T10:00:00Z"
        assert report.analysis_period_end == "2025-01-31T10:00:00Z"


class TestWorkflowChangeSet:

    def test_is_empty(self):
        cs = _changeset(())
        assert cs.is_empty is True

    def test_categorized_properties(self):
        changes = (
            WorkflowChange("w", WorkflowChangeAction.STEP_ADDED, step_name="a"),
            WorkflowChange("w", WorkflowChangeAction.STEP_REMOVED, step_name="b"),
            WorkflowChange("w", WorkflowChangeAction.STEP_MODIFIED, step_name="c"),
            WorkflowChange("w", WorkflowChangeAction.TOPOLOGY_CHANGED),
        )
        cs = _changeset(changes)

        assert len(cs.step_removals) == 1
        assert len(cs.step_modifications) == 1
        assert len(cs.topology_changes) == 1
        assert cs.is_empty is False


class TestFlowPropagationReport:

    def test_impact_rate_zero_division(self):
        report = FlowPropagationReport(
            report_id="r1",
            changeset_id="cs1",
            created_at="now",
            total_executions_scanned=0,
        )
        assert report.impact_rate == 0.0
