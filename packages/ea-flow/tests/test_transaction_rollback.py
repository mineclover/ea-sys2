from ea_flow.runtime import FlowRuntime, StepExecutionResult, StepImplementer
from ea_flow.spec import ExecutionContext, StepSpec, WorkflowSpec


class StatefulMockImplementer(StepImplementer):
    def __init__(self):
        self.executed = []
        self.rolled_back = []
        self.should_fail_at = None

    def execute(self, spec: StepSpec, context: ExecutionContext) -> StepExecutionResult:
        if spec.name == self.should_fail_at:
            return StepExecutionResult(False, None, [f"Step {spec.name} failed"])

        self.executed.append(spec.name)
        return StepExecutionResult(True, f"output:{spec.name}", [f"Step {spec.name} logic"])

    def rollback(self, spec: StepSpec, context: ExecutionContext) -> bool:
        self.rolled_back.append(spec.name)
        return True

class SimpleStepSpec(StepSpec):
    def __init__(self, name): self._name = name
    @property
    def name(self) -> str: return self._name
    @property
    def kernel_anchor(self) -> str: return None

class DummyWorkflowSpec(WorkflowSpec):
    def __init__(self, steps): self.steps = steps
    @property
    def name(self) -> str: return "rollback_wf"
    @property
    def kernel_anchor(self) -> str: return None
    @property
    def input_schema(self) -> str: return None
    @property
    def output_schema(self) -> str: return None
    def get_steps(self): return self.steps

def test_rollback_sequence():
    step1 = SimpleStepSpec("S1")
    step2 = SimpleStepSpec("S2")
    step3 = SimpleStepSpec("S3")

    impl = StatefulMockImplementer()
    impl.should_fail_at = "S3"

    runtime = FlowRuntime(implementers={
        "S1": impl, "S2": impl, "S3": impl
    })

    wf = DummyWorkflowSpec([step1, step2, step3])
    result = runtime.execute(wf, {})

    assert not result.success
    assert result.rollback_occurred

    # S1 and S2 should have executed
    assert impl.executed == ["S1", "S2"]
    # S2 and then S1 should have rolled back (reverse order)
    assert impl.rolled_back == ["S2", "S1"]
    assert "StepSpec 'S3' rejected. Planning compensation..." in result.logs
