from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from ea_flow.spec import WorkflowSpec, ExecutionContext, StepSpec

@dataclass(frozen=True)
class StepExecutionResult:
    """Result of a single step execution at runtime."""
    success: bool
    output: Any
    logs: List[str]

@dataclass(frozen=True)
class FlowExecutionResult:
    """Result of a full workflow/use-case execution."""
    workflow_name: str
    execution_id: str
    success: bool
    step_results: Dict[str, StepExecutionResult]
    logs: List[str] = field(default_factory=list)
    rollback_occurred: bool = False

class StepImplementer(ABC):
    """
    Interface for the actual implementation of a StepSpec.
    This is where the 'How' lives.
    """
    @abstractmethod
    def execute(self, spec: StepSpec, context: ExecutionContext) -> StepExecutionResult:
        pass

    @abstractmethod
    def rollback(self, spec: StepSpec, context: ExecutionContext) -> bool:
        pass

class FlowRuntime:
    """
    The engine that fulfills WorkflowSpecs using a set of Implementers.
    Reflects the 'Coordination' of procedural physics.
    """
    def __init__(self, implementers: Dict[str, StepImplementer]):
        self.implementers = implementers

    def execute(self, workflow: WorkflowSpec, variables: Dict[str, Any]) -> FlowExecutionResult:
        execution_id = f"exec-{workflow.name}"
        context = ExecutionContext(execution_id, variables)
        results = {}
        all_logs = []
        executed_specs = []
        overall_success = True
        rollback_occurred = False
        
        steps = workflow.get_steps()
        
        for spec in steps:
            # Resolve implementer for this spec (try exact match, then prefix match)
            implementer = self.implementers.get(spec.name)
            if not implementer:
                prefix = spec.name.split(":")[0]
                implementer = self.implementers.get(prefix)
            if not implementer:
                # Fallback to a generic or mock implementer if needed
                all_logs.append(f"No implementer found for {spec.name}. Skipping or failing.")
                overall_success = False
                break
            
            res = implementer.execute(spec, context)
            results[spec.name] = res
            all_logs.extend(res.logs)
            
            if res.success:
                executed_specs.append(spec)
            else:
                overall_success = False
                all_logs.append(f"StepSpec '{spec.name}' failed. Initiating rollback...")
                
                # Rollback in reverse order
                for completed_spec in reversed(executed_specs):
                    impl = self.implementers.get(completed_spec.name)
                    if impl:
                        try:
                            rb_success = impl.rollback(completed_spec, context)
                            status = "succeeded" if rb_success else "failed"
                            all_logs.append(f"Rollback '{completed_spec.name}': {status}")
                        except Exception as e:
                            all_logs.append(f"Rollback '{completed_spec.name}' exception: {str(e)}")
                
                rollback_occurred = True
                break
                
        return FlowExecutionResult(
            workflow_name=workflow.name,
            execution_id=execution_id,
            success=overall_success,
            step_results=results,
            logs=all_logs,
            rollback_occurred=rollback_occurred
        )
