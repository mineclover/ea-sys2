"""Tests for ea_flow.runtime — P3 Realization execution engine."""

from __future__ import annotations

from typing import Any

import pytest

from ea_flow.runtime import (
    FlowExecutionResult,
    FlowRuntime,
    StepExecutionResult,
    StepImplementer,
    StepInterpretationResult,
)
from ea_flow.spec import ExecutionContext, FlowTopology, StepSpec, WorkflowSpec
from ea_flow.topology import DataFlowEdge, LogicCondition, ProcessSpec, StepDefinition
from ea_flow.types import FlowStepCategory


# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures — Concrete StepSpec / WorkflowSpec
# ═══════════════════════════════════════════════════════════════════════════════


class SimpleStep(StepSpec):
    def __init__(self, step_name: str, anchor: str | None = None):
        self._name = step_name
        self._anchor = anchor

    @property
    def name(self) -> str:
        return self._name

    @property
    def kernel_anchor(self) -> str | None:
        return self._anchor


class SimpleWorkflow(WorkflowSpec):
    def __init__(self, wf_name: str, steps: list[StepSpec]):
        self._name = wf_name
        self._steps = steps

    @property
    def name(self) -> str:
        return self._name

    @property
    def kernel_anchor(self) -> str | None:
        return None

    @property
    def input_schema(self):
        return None

    @property
    def output_schema(self):
        return None

    def get_steps(self) -> list[StepSpec]:
        return self._steps


class SuccessImplementer(StepImplementer):
    def __init__(self, intent: Any = "done"):
        self._intent = intent
        self.executed: list[str] = []
        self.rolled_back: list[str] = []

    def execute(self, spec: StepSpec, context: ExecutionContext) -> StepExecutionResult:
        self.executed.append(spec.name)
        return StepExecutionResult(accepted=True, intent=self._intent, logs=[f"{spec.name} ok"])

    def rollback(self, spec: StepSpec, context: ExecutionContext) -> bool:
        self.rolled_back.append(spec.name)
        return True


class FailImplementer(StepImplementer):
    def execute(self, spec: StepSpec, context: ExecutionContext) -> StepExecutionResult:
        return StepExecutionResult(accepted=False, intent=None, logs=[f"{spec.name} failed"])

    def rollback(self, spec: StepSpec, context: ExecutionContext) -> bool:
        return True


class RollbackFailImplementer(StepImplementer):
    def execute(self, spec: StepSpec, context: ExecutionContext) -> StepExecutionResult:
        return StepExecutionResult(accepted=True, intent="partial", logs=[])

    def rollback(self, spec: StepSpec, context: ExecutionContext) -> bool:
        raise RuntimeError("rollback exploded")


# ═══════════════════════════════════════════════════════════════════════════════
# StepInterpretationResult / StepExecutionResult
# ═══════════════════════════════════════════════════════════════════════════════


class TestStepInterpretationResult:
    def test_success_properties(self):
        r = StepInterpretationResult(accepted=True, intent="data", logs=["ok"])
        assert r.success is True
        assert r.output == "data"

    def test_failure_properties(self):
        r = StepInterpretationResult(accepted=False, intent=None, logs=["err"])
        assert r.success is False
        assert r.output is None

    def test_frozen(self):
        r = StepInterpretationResult(accepted=True, intent=1, logs=[])
        with pytest.raises(AttributeError):
            r.accepted = False  # type: ignore[misc]

    def test_execution_result_is_subclass(self):
        r = StepExecutionResult(accepted=True, intent="x", logs=[])
        assert isinstance(r, StepInterpretationResult)
        assert r.success is True


# ═══════════════════════════════════════════════════════════════════════════════
# FlowExecutionResult
# ═══════════════════════════════════════════════════════════════════════════════


class TestFlowExecutionResult:
    def test_defaults(self):
        r = FlowExecutionResult(
            workflow_name="wf", execution_id="e1", success=True, step_results={}
        )
        assert r.logs == []
        assert r.interpreted_intents == []
        assert r.rollback_occurred is False

    def test_frozen(self):
        r = FlowExecutionResult(
            workflow_name="wf", execution_id="e1", success=True, step_results={}
        )
        with pytest.raises(AttributeError):
            r.success = False  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════════════
# FlowRuntime — interpret / execute
# ═══════════════════════════════════════════════════════════════════════════════


class TestFlowRuntime:
    def test_successful_workflow(self):
        impl = SuccessImplementer(intent="result")
        steps = [SimpleStep("stepA"), SimpleStep("stepB")]
        wf = SimpleWorkflow("wf1", steps)
        runtime = FlowRuntime({"stepA": impl, "stepB": impl})

        res = runtime.interpret(wf, {"key": "val"})

        assert res.success is True
        assert res.workflow_name == "wf1"
        assert res.execution_id == "exec-wf1"
        assert set(res.step_results.keys()) == {"stepA", "stepB"}
        assert res.interpreted_intents == ["result", "result"]
        assert res.rollback_occurred is False

    def test_execute_is_alias_for_interpret(self):
        impl = SuccessImplementer()
        wf = SimpleWorkflow("wf", [SimpleStep("s")])
        runtime = FlowRuntime({"s": impl})

        r1 = runtime.interpret(wf, {})
        r2 = runtime.execute(wf, {})

        assert r1.success == r2.success
        assert r1.workflow_name == r2.workflow_name

    def test_missing_implementer_stops_workflow(self):
        wf = SimpleWorkflow("wf", [SimpleStep("unknown")])
        runtime = FlowRuntime({})

        res = runtime.interpret(wf, {})

        assert res.success is False
        assert any("No implementer" in log for log in res.logs)
        assert res.step_results == {}

    def test_prefix_implementer_resolution(self):
        impl = SuccessImplementer(intent="pfx")
        wf = SimpleWorkflow("wf", [SimpleStep("validate:schema")])
        runtime = FlowRuntime({"validate": impl})

        res = runtime.interpret(wf, {})

        assert res.success is True
        assert "validate:schema" in res.step_results
        assert res.interpreted_intents == ["pfx"]

    def test_failed_step_triggers_rollback(self):
        ok_impl = SuccessImplementer(intent="ok")
        fail_impl = FailImplementer()
        steps = [SimpleStep("a"), SimpleStep("b"), SimpleStep("c")]
        wf = SimpleWorkflow("wf", steps)
        runtime = FlowRuntime({"a": ok_impl, "b": fail_impl, "c": ok_impl})

        res = runtime.interpret(wf, {})

        assert res.success is False
        assert res.rollback_occurred is True
        # step 'a' succeeded, 'b' failed → rollback 'a'
        assert "a" in ok_impl.rolled_back
        assert any("rejected" in log.lower() for log in res.logs)

    def test_rollback_exception_is_logged(self):
        rb_fail = RollbackFailImplementer()
        fail_impl = FailImplementer()
        steps = [SimpleStep("s1"), SimpleStep("s2")]
        wf = SimpleWorkflow("wf", steps)
        runtime = FlowRuntime({"s1": rb_fail, "s2": fail_impl})

        res = runtime.interpret(wf, {})

        assert res.success is False
        assert res.rollback_occurred is True
        assert any("exception" in log.lower() for log in res.logs)
        assert any("rollback exploded" in log for log in res.logs)

    def test_none_intent_not_collected(self):
        none_impl = SuccessImplementer(intent=None)
        wf = SimpleWorkflow("wf", [SimpleStep("s")])
        runtime = FlowRuntime({"s": none_impl})

        res = runtime.interpret(wf, {})

        assert res.success is True
        assert res.interpreted_intents == []

    def test_empty_workflow(self):
        runtime = FlowRuntime({})
        wf = SimpleWorkflow("empty", [])

        res = runtime.interpret(wf, {})

        assert res.success is True
        assert res.step_results == {}
        assert res.interpreted_intents == []


# ═══════════════════════════════════════════════════════════════════════════════
# Additional fixture — context-capturing implementer
# ═══════════════════════════════════════════════════════════════════════════════


class ContextCapturingImplementer(StepImplementer):
    """Captures context.variables at execution time for test assertions."""

    def __init__(self) -> None:
        self.last_variables: dict[str, Any] = {}

    def execute(self, spec: StepSpec, context: ExecutionContext) -> StepExecutionResult:
        self.last_variables = dict(context.variables)
        return StepExecutionResult(accepted=True, intent="captured", logs=[])

    def rollback(self, spec: StepSpec, context: ExecutionContext) -> bool:
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# FlowRuntime — interpret_process (P2 ProcessSpec graph execution)
# ═══════════════════════════════════════════════════════════════════════════════


def _action(
    step_id: str,
    name: str,
    *,
    next_ids: list[str] | None = None,
    on_failure: str | None = None,
) -> StepDefinition:
    """Shortcut to build an ACTION StepDefinition."""
    return StepDefinition(
        id=step_id,
        name=name,
        category=FlowStepCategory.ACTION,
        description="",
        next_step_ids=next_ids or [],
        on_failure_step_id=on_failure,
    )


def _decision(
    step_id: str,
    name: str,
    *,
    condition: LogicCondition | None = None,
    next_ids: list[str] | None = None,
) -> StepDefinition:
    """Shortcut to build a DECISION StepDefinition."""
    return StepDefinition(
        id=step_id,
        name=name,
        category=FlowStepCategory.DECISION,
        description="",
        condition=condition,
        next_step_ids=next_ids or [],
    )


class TestFlowRuntimeProcess:
    def test_sequential_execution(self):
        """Steps A → B → C executed in graph order."""
        steps = [
            _action("s1", "stepA", next_ids=["s2"]),
            _action("s2", "stepB", next_ids=["s3"]),
            _action("s3", "stepC"),
        ]
        process = ProcessSpec(id="p1", name="proc", version="1.0", steps=steps)

        impl = SuccessImplementer(intent="ok")
        runtime = FlowRuntime({"stepA": impl, "stepB": impl, "stepC": impl})

        res = runtime.interpret_process(process, {})

        assert res.success is True
        assert len(res.step_results) == 3
        assert impl.executed == ["stepA", "stepB", "stepC"]
        assert res.execution_id == "exec-proc-1.0"

    def test_empty_process(self):
        process = ProcessSpec(id="p1", name="empty", version="1.0", steps=[])
        runtime = FlowRuntime({})

        res = runtime.interpret_process(process, {})

        assert res.success is True
        assert res.step_results == {}

    def test_data_flow_passing(self):
        """DataFlowEdge transfers data between steps via context."""
        steps = [
            _action("s1", "produce", next_ids=["s2"]),
            _action("s2", "consume"),
        ]
        edges = [
            DataFlowEdge(
                source_step_id="s1", target_step_id="s2",
                source_field="userId", target_field="id",
            ),
        ]
        process = ProcessSpec(
            id="p1", name="proc", version="1.0",
            steps=steps, data_flow_edges=edges,
        )

        producer = SuccessImplementer(intent={"userId": 42})
        consumer = ContextCapturingImplementer()
        runtime = FlowRuntime({"produce": producer, "consume": consumer})

        res = runtime.interpret_process(process, {})

        assert res.success is True
        assert consumer.last_variables.get("id") == 42

    def test_data_flow_with_transformation(self):
        """DataFlowEdge applies transformation_rule."""
        steps = [
            _action("s1", "produce", next_ids=["s2"]),
            _action("s2", "consume"),
        ]
        edges = [
            DataFlowEdge(
                source_step_id="s1", target_step_id="s2",
                source_field="count", target_field="count_str",
                transformation_rule="toString()",
            ),
        ]
        process = ProcessSpec(
            id="p1", name="proc", version="1.0",
            steps=steps, data_flow_edges=edges,
        )

        producer = SuccessImplementer(intent={"count": 100})
        consumer = ContextCapturingImplementer()
        runtime = FlowRuntime({"produce": producer, "consume": consumer})

        res = runtime.interpret_process(process, {})

        assert res.success is True
        assert consumer.last_variables.get("count_str") == "100"

    def test_data_flow_nested_field(self):
        """DataFlowEdge resolves dotted source_field paths."""
        steps = [
            _action("s1", "produce", next_ids=["s2"]),
            _action("s2", "consume"),
        ]
        edges = [
            DataFlowEdge(
                source_step_id="s1", target_step_id="s2",
                source_field="user.name", target_field="target_name",
            ),
        ]
        process = ProcessSpec(
            id="p1", name="proc", version="1.0",
            steps=steps, data_flow_edges=edges,
        )

        producer = SuccessImplementer(intent={"user": {"name": "Alice"}})
        consumer = ContextCapturingImplementer()
        runtime = FlowRuntime({"produce": producer, "consume": consumer})

        res = runtime.interpret_process(process, {})

        assert res.success is True
        assert consumer.last_variables.get("target_name") == "Alice"

    def test_decision_branching_true(self):
        """DECISION with true condition follows first next_step_id."""
        steps = [
            _decision(
                "d1", "check",
                condition=LogicCondition(expression="amount >= 1000"),
                next_ids=["s_approve", "s_reject"],
            ),
            _action("s_approve", "approve"),
            _action("s_reject", "reject"),
        ]
        process = ProcessSpec(id="p1", name="proc", version="1.0", steps=steps)

        impl = SuccessImplementer()
        runtime = FlowRuntime({"approve": impl, "reject": impl})

        res = runtime.interpret_process(process, {"amount": 5000})

        assert res.success is True
        assert "s_approve" in res.step_results
        assert "s_reject" not in res.step_results

    def test_decision_branching_false(self):
        """DECISION with false condition follows second next_step_id."""
        steps = [
            _decision(
                "d1", "check",
                condition=LogicCondition(expression="amount >= 1000"),
                next_ids=["s_approve", "s_reject"],
            ),
            _action("s_approve", "approve"),
            _action("s_reject", "reject"),
        ]
        process = ProcessSpec(id="p1", name="proc", version="1.0", steps=steps)

        impl = SuccessImplementer()
        runtime = FlowRuntime({"approve": impl, "reject": impl})

        res = runtime.interpret_process(process, {"amount": 100})

        assert res.success is True
        assert "s_reject" in res.step_results
        assert "s_approve" not in res.step_results

    def test_decision_no_condition_follows_first(self):
        """DECISION without condition defaults to first path."""
        steps = [
            _decision("d1", "gate", next_ids=["s2"]),
            _action("s2", "proceed"),
        ]
        process = ProcessSpec(id="p1", name="proc", version="1.0", steps=steps)

        impl = SuccessImplementer()
        runtime = FlowRuntime({"proceed": impl})

        res = runtime.interpret_process(process, {})

        assert res.success is True
        assert "s2" in res.step_results

    def test_on_failure_redirect(self):
        """Failed step redirects to on_failure_step_id."""
        steps = [
            _action("s1", "risky", next_ids=["s2"], on_failure="s_err"),
            _action("s2", "happy"),
            _action("s_err", "error_handler"),
        ]
        process = ProcessSpec(id="p1", name="proc", version="1.0", steps=steps)

        fail = FailImplementer()
        ok = SuccessImplementer()
        runtime = FlowRuntime({"risky": fail, "happy": ok, "error_handler": ok})

        res = runtime.interpret_process(process, {})

        assert "s_err" in res.step_results
        assert "s2" not in res.step_results
        assert any("failure handler" in log.lower() for log in res.logs)

    def test_rollback_on_failure(self):
        """Failed step triggers compensation for prior successful steps."""
        steps = [
            _action("s1", "first", next_ids=["s2"]),
            _action("s2", "second", next_ids=["s3"]),
            _action("s3", "third"),
        ]
        process = ProcessSpec(id="p1", name="proc", version="1.0", steps=steps)

        ok = SuccessImplementer(intent="ok")
        fail = FailImplementer()
        runtime = FlowRuntime({"first": ok, "second": ok, "third": fail})

        res = runtime.interpret_process(process, {})

        assert res.success is False
        assert res.rollback_occurred is True
        assert "first" in ok.rolled_back
        assert "second" in ok.rolled_back

    def test_missing_implementer(self):
        """Process fails when step has no implementer."""
        steps = [_action("s1", "unknown")]
        process = ProcessSpec(id="p1", name="proc", version="1.0", steps=steps)
        runtime = FlowRuntime({})

        res = runtime.interpret_process(process, {})

        assert res.success is False
        assert any("No implementer" in log for log in res.logs)

    def test_implementer_resolved_by_step_id(self):
        """Implementer can be registered by step id as fallback."""
        steps = [_action("my-step-id", "unknown_name")]
        process = ProcessSpec(id="p1", name="proc", version="1.0", steps=steps)

        impl = SuccessImplementer()
        runtime = FlowRuntime({"my-step-id": impl})

        res = runtime.interpret_process(process, {})

        assert res.success is True

    def test_cycle_detection(self):
        """Infinite cycle is stopped by max_steps limit."""
        steps = [
            _action("s1", "loop_a", next_ids=["s2"]),
            _action("s2", "loop_b", next_ids=["s1"]),
        ]
        process = ProcessSpec(id="p1", name="proc", version="1.0", steps=steps)

        impl = SuccessImplementer()
        runtime = FlowRuntime({"loop_a": impl, "loop_b": impl})

        res = runtime.interpret_process(process, {})

        assert res.success is False
        assert any("limit" in log.lower() for log in res.logs)


# ═══════════════════════════════════════════════════════════════════════════════
# FlowRuntime — interpret_topology (P2 FlowTopology graph execution)
# ═══════════════════════════════════════════════════════════════════════════════


class TestFlowRuntimeTopology:
    def test_basic_topology_execution(self):
        """Steps follow transition_rules instead of sequential order."""
        steps = [SimpleStep("A"), SimpleStep("B"), SimpleStep("C")]
        topology = FlowTopology(
            name="topo",
            steps=steps,
            entry_point="A",
            transition_rules={"A": "C", "C": "B"},
            exit_points=["B"],
        )

        impl = SuccessImplementer(intent="x")
        runtime = FlowRuntime({"A": impl, "B": impl, "C": impl})

        res = runtime.interpret_topology(topology, {})

        assert res.success is True
        assert impl.executed == ["A", "C", "B"]
        assert res.execution_id == "exec-topo"

    def test_topology_entry_point(self):
        """Execution starts at entry_point, not first step."""
        steps = [SimpleStep("X"), SimpleStep("Y")]
        topology = FlowTopology(
            name="topo",
            steps=steps,
            entry_point="Y",
            exit_points=["Y"],
        )

        impl = SuccessImplementer()
        runtime = FlowRuntime({"X": impl, "Y": impl})

        res = runtime.interpret_topology(topology, {})

        assert res.success is True
        assert impl.executed == ["Y"]

    def test_topology_default_entry(self):
        """Without entry_point, first step is used."""
        steps = [SimpleStep("first"), SimpleStep("second")]
        topology = FlowTopology(
            name="topo",
            steps=steps,
            transition_rules={"first": "second"},
        )

        impl = SuccessImplementer()
        runtime = FlowRuntime({"first": impl, "second": impl})

        res = runtime.interpret_topology(topology, {})

        assert res.success is True
        assert impl.executed == ["first", "second"]

    def test_topology_exit_point_stops(self):
        """Execution stops at exit_points even if transition_rules continue."""
        steps = [SimpleStep("A"), SimpleStep("B"), SimpleStep("C")]
        topology = FlowTopology(
            name="topo",
            steps=steps,
            entry_point="A",
            transition_rules={"A": "B", "B": "C"},
            exit_points=["B"],
        )

        impl = SuccessImplementer()
        runtime = FlowRuntime({"A": impl, "B": impl, "C": impl})

        res = runtime.interpret_topology(topology, {})

        assert res.success is True
        assert impl.executed == ["A", "B"]
        assert "C" not in [s for s in impl.executed]

    def test_topology_rollback(self):
        """Topology failure triggers compensation in reverse."""
        steps = [SimpleStep("ok1"), SimpleStep("ok2"), SimpleStep("fail")]
        topology = FlowTopology(
            name="topo",
            steps=steps,
            entry_point="ok1",
            transition_rules={"ok1": "ok2", "ok2": "fail"},
        )

        ok = SuccessImplementer()
        fail = FailImplementer()
        runtime = FlowRuntime({"ok1": ok, "ok2": ok, "fail": fail})

        res = runtime.interpret_topology(topology, {})

        assert res.success is False
        assert res.rollback_occurred is True
        assert "ok1" in ok.rolled_back
        assert "ok2" in ok.rolled_back

    def test_topology_missing_transition_stops(self):
        """Execution stops when transition_rules has no entry for current step."""
        steps = [SimpleStep("A"), SimpleStep("B")]
        topology = FlowTopology(
            name="topo",
            steps=steps,
            entry_point="A",
            # No transition from A → next
        )

        impl = SuccessImplementer()
        runtime = FlowRuntime({"A": impl, "B": impl})

        res = runtime.interpret_topology(topology, {})

        assert res.success is True
        assert impl.executed == ["A"]


# ═══════════════════════════════════════════════════════════════════════════════
# Condition evaluation
# ═══════════════════════════════════════════════════════════════════════════════


class TestConditionEvaluation:
    def _eval(self, expr: str, variables: dict[str, Any] | None = None) -> bool:
        runtime = FlowRuntime({})
        cond = LogicCondition(expression=expr)
        return runtime._evaluate_condition(cond, variables or {})

    def test_greater_than_or_equal(self):
        assert self._eval("amount >= 100", {"amount": 100}) is True
        assert self._eval("amount >= 100", {"amount": 99}) is False

    def test_less_than(self):
        assert self._eval("x < 10", {"x": 5}) is True
        assert self._eval("x < 10", {"x": 10}) is False

    def test_equality(self):
        assert self._eval("status == 'approved'", {"status": "approved"}) is True
        assert self._eval("status == 'approved'", {"status": "pending"}) is False

    def test_not_equal(self):
        assert self._eval("flag != true", {"flag": False}) is True

    def test_boolean_variable(self):
        assert self._eval("enabled", {"enabled": True}) is True
        assert self._eval("enabled", {"enabled": False}) is False

    def test_empty_expression_is_true(self):
        assert self._eval("") is True

    def test_literal_true_false(self):
        assert self._eval("true") is True
        assert self._eval("false") is False

    def test_condition_parameters_merged(self):
        runtime = FlowRuntime({})
        cond = LogicCondition(
            expression="threshold <= 50",
            parameters={"threshold": 30},
        )
        assert runtime._evaluate_condition(cond, {}) is True
