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
from ea_flow.spec import ExecutionContext, StepSpec, WorkflowSpec


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
