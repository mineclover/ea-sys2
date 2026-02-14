import pytest
from ea_flow.spec import FlowMetaStep, KernelGroundedStepSpec, ExecutionContext, WorkflowSpec, StepSpec
from ea_flow.runtime import FlowRuntime, StepImplementer, StepExecutionResult

class MockImplementer(StepImplementer):
    def execute(self, spec: StepSpec, context: ExecutionContext) -> StepExecutionResult:
        return StepExecutionResult(True, f"executed:{spec.name}", ["Mock log"])
    def rollback(self, spec: StepSpec, context: ExecutionContext) -> bool:
        return True

def test_kernel_grounded_step_spec_properties():
    meta = FlowMetaStep(name="TestStep", description="A test step")
    step = KernelGroundedStepSpec(anchor="ea:kernel:entity:1", meta_type=meta)
    
    assert step.name == "TestStep on ea:kernel:entity:1"
    assert step.kernel_anchor == "ea:kernel:entity:1"
    assert step.meta_type == meta

def test_kernel_grounded_step_execution_via_runtime():
    meta = FlowMetaStep(name="TestStep", description="A test step")
    step = KernelGroundedStepSpec(anchor="ea:kernel:entity:1", meta_type=meta)
    
    class SimpleWF(WorkflowSpec):
        @property
        def name(self) -> str: return "test_wf"
        @property
        def kernel_anchor(self) -> str: return None
        @property
        def input_schema(self) -> str: return None
        @property
        def output_schema(self) -> str: return None
        def get_steps(self): return [step]

    runtime = FlowRuntime(implementers={step.name: MockImplementer()})
    result = runtime.execute(SimpleWF(), {})
    
    assert result.success == True
    assert step.name in result.step_results
    assert result.step_results[step.name].output == "executed:TestStep on ea:kernel:entity:1"
