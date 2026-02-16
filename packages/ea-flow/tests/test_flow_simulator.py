"""Tests for FlowSimulator — S5 Evolution What-If."""

from __future__ import annotations

from ea_flow.execution_store import (
    InMemoryExecutionStore,
    StepResultSummary,
    StoredExecutionRecord,
)
from ea_flow.flow_simulator import (
    AffectedExecution,
    FlowSimulator,
    ImpactLevel,
    TopologyChange,
    TopologyChangeType,
    TopologySimulationResult,
)


# ── Factory ─────────────────────────────────────────────────────────────

def _make_record(
    workflow_name: str = "validate-model",
    success: bool = True,
    failed_step: str = "",
    rollback_occurred: bool = False,
    executed_at: str = "2025-01-15T10:00:00Z",
    step_results: tuple[StepResultSummary, ...] | None = None,
    execution_id: str = "",
) -> StoredExecutionRecord:
    if step_results is None:
        step_results = (
            StepResultSummary("step-a", accepted=True),
            StepResultSummary("step-b", accepted=True),
            StepResultSummary("step-c", accepted=success),
        )
    return StoredExecutionRecord(
        storage_id="",
        workflow_name=workflow_name,
        success=success,
        total_steps=len(step_results),
        completed_steps=sum(1 for s in step_results if s.accepted),
        failed_step=failed_step,
        rollback_occurred=rollback_occurred,
        duration_ms=100,
        executed_at=executed_at,
        step_results=step_results,
        execution_id=execution_id,
    )


def _populated_store() -> InMemoryExecutionStore:
    store = InMemoryExecutionStore()
    # 8 successful runs of validate-model
    for i in range(8):
        store.store(_make_record(
            execution_id=f"exec-{i}",
            executed_at=f"2025-01-{10 + i:02d}T10:00:00Z",
        ))
    # 3 runs of deploy-flow
    for i in range(3):
        store.store(_make_record(
            workflow_name="deploy-flow",
            execution_id=f"deploy-{i}",
            step_results=(
                StepResultSummary("deploy-a", accepted=True),
                StepResultSummary("deploy-b", accepted=True),
            ),
        ))
    return store


# ── FlowSimulator Tests ────────────────────────────────────────────────

class TestFlowSimulator:
    def test_simulate_no_changes(self):
        store = _populated_store()
        sim = FlowSimulator(store)

        result = sim.simulate([])
        assert result.total_executions_analyzed == 11
        assert result.affected_executions == 0
        assert result.impact_level == ImpactLevel.NONE
        assert result.safe_to_apply is True

    def test_simulate_step_removal(self):
        store = _populated_store()
        sim = FlowSimulator(store)

        result = sim.simulate_step_removal("step-b", "validate-model")
        assert result.affected_executions == 8
        assert result.broken_workflows >= 1

    def test_simulate_step_removal_global(self):
        store = _populated_store()
        sim = FlowSimulator(store)

        # Remove step-a from all workflows (empty workflow_name = global)
        result = sim.simulate_step_removal("step-a", "")
        # step-a exists in validate-model (8 runs)
        assert result.affected_executions == 8

    def test_simulate_reorder(self):
        store = _populated_store()
        sim = FlowSimulator(store)

        change = TopologyChange(
            change_type=TopologyChangeType.REORDER_STEP,
            step_name="step-b",
            workflow_name="validate-model",
            new_position=0,
        )
        result = sim.simulate([change])
        assert result.step_dependency_violations > 0
        assert result.affected_executions > 0

    def test_simulate_add_step_no_impact(self):
        store = _populated_store()
        sim = FlowSimulator(store)

        change = TopologyChange(
            change_type=TopologyChangeType.ADD_STEP,
            step_name="new-step",
            workflow_name="validate-model",
        )
        result = sim.simulate([change])
        assert result.affected_executions == 0
        assert result.impact_level == ImpactLevel.NONE

    def test_simulate_multiple_removals(self):
        store = _populated_store()
        sim = FlowSimulator(store)

        changes = [
            TopologyChange(
                change_type=TopologyChangeType.REMOVE_STEP,
                step_name="step-a",
                workflow_name="validate-model",
            ),
            TopologyChange(
                change_type=TopologyChangeType.REMOVE_STEP,
                step_name="deploy-a",
                workflow_name="deploy-flow",
            ),
        ]
        result = sim.simulate(changes)
        assert result.affected_executions == 11
        assert result.impact_level in (ImpactLevel.HIGH, ImpactLevel.CRITICAL)

    def test_change_rate(self):
        store = _populated_store()
        sim = FlowSimulator(store)

        result = sim.simulate_step_removal("deploy-a", "deploy-flow")
        assert result.change_rate == 3 / 11

    def test_safe_to_apply_false_for_high_impact(self):
        store = _populated_store()
        sim = FlowSimulator(store)

        changes = [
            TopologyChange(
                change_type=TopologyChangeType.REMOVE_STEP,
                step_name="step-a",
                workflow_name="validate-model",
            ),
            TopologyChange(
                change_type=TopologyChangeType.REMOVE_STEP,
                step_name="step-b",
                workflow_name="validate-model",
            ),
            TopologyChange(
                change_type=TopologyChangeType.REMOVE_STEP,
                step_name="step-c",
                workflow_name="validate-model",
            ),
            TopologyChange(
                change_type=TopologyChangeType.REMOVE_STEP,
                step_name="deploy-a",
                workflow_name="deploy-flow",
            ),
        ]
        result = sim.simulate(changes)
        assert result.safe_to_apply is False

    def test_simulation_result_has_id_and_timestamp(self):
        store = _populated_store()
        sim = FlowSimulator(store)

        result = sim.simulate([])
        assert result.simulation_id.startswith("sim-")
        assert result.created_at.endswith("Z")

    def test_empty_store(self):
        store = InMemoryExecutionStore()
        sim = FlowSimulator(store)

        result = sim.simulate_step_removal("any", "any")
        assert result.total_executions_analyzed == 0
        assert result.impact_level == ImpactLevel.NONE
