from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ea_flow.spec import ExecutionContext, StepSpec, WorkflowSpec


@dataclass(frozen=True)
class StepInterpretationResult:
    """Declarative interpretation result for a single step."""
    accepted: bool
    intent: Any
    logs: list[str]

    @property
    def success(self) -> bool:
        return self.accepted

    @property
    def output(self) -> Any:
        return self.intent


@dataclass(frozen=True)
class StepExecutionResult(StepInterpretationResult):
    """Backward-compatible alias for interpretation result."""


@dataclass(frozen=True)
class FlowExecutionResult:
    """Result of interpreting a full workflow/use-case."""
    workflow_name: str
    execution_id: str
    success: bool
    step_results: dict[str, StepInterpretationResult]
    logs: list[str] = field(default_factory=list)
    interpreted_intents: list[Any] = field(default_factory=list)
    rollback_occurred: bool = False


class StepImplementer(ABC):
    """
    Interface for environment-specific interpretation of a StepSpec.
    Implementations should return declarative intent data, not perform side effects.
    """
    @abstractmethod
    def execute(self, spec: StepSpec, context: ExecutionContext) -> StepExecutionResult:
        pass

    @abstractmethod
    def rollback(self, spec: StepSpec, context: ExecutionContext) -> bool:
        pass


class FlowRuntime:
    """
    Interprets WorkflowSpecs into ordered intent outputs.
    `execute()` is kept as a backward-compatible alias of `interpret()`.
    """
    def __init__(self, implementers: dict[str, StepImplementer]):
        self.implementers = implementers

    def _resolve_implementer(self, spec: StepSpec) -> StepImplementer | None:
        implementer = self.implementers.get(spec.name)
        if implementer:
            return implementer
        prefix = spec.name.split(":")[0]
        return self.implementers.get(prefix)

    def _interpret_step(
        self, implementer: StepImplementer, spec: StepSpec, context: ExecutionContext
    ) -> StepInterpretationResult:
        raw_result = implementer.execute(spec, context)
        return StepInterpretationResult(
            accepted=raw_result.success,
            intent=raw_result.output,
            logs=list(raw_result.logs),
        )

    def interpret(self, workflow: WorkflowSpec, variables: dict[str, Any]) -> FlowExecutionResult:
        execution_id = f"exec-{workflow.name}"
        context = ExecutionContext(execution_id, variables)
        results: dict[str, StepInterpretationResult] = {}
        all_logs: list[str] = []
        interpreted_intents: list[Any] = []
        interpreted_specs: list[StepSpec] = []
        overall_success = True
        rollback_occurred = False

        steps = workflow.get_steps()

        for spec in steps:
            implementer = self._resolve_implementer(spec)
            if not implementer:
                all_logs.append(f"No implementer found for {spec.name}.")
                overall_success = False
                break

            res = self._interpret_step(implementer, spec, context)
            results[spec.name] = res
            all_logs.extend(res.logs)

            if res.intent is not None:
                interpreted_intents.append(res.intent)

            if res.success:
                interpreted_specs.append(spec)
            else:
                overall_success = False
                all_logs.append(f"StepSpec '{spec.name}' rejected. Planning compensation...")

                # Plan compensation in reverse order to preserve transactional semantics.
                for interpreted_spec in reversed(interpreted_specs):
                    impl = self._resolve_implementer(interpreted_spec)
                    if impl:
                        try:
                            rb_success = impl.rollback(interpreted_spec, context)
                            status = "succeeded" if rb_success else "failed"
                            all_logs.append(f"Compensation plan '{interpreted_spec.name}': {status}")
                        except Exception as e:
                            all_logs.append(
                                f"Compensation plan '{interpreted_spec.name}' exception: {str(e)}"
                            )

                rollback_occurred = True
                break

        return FlowExecutionResult(
            workflow_name=workflow.name,
            execution_id=execution_id,
            success=overall_success,
            step_results=results,
            logs=all_logs,
            interpreted_intents=interpreted_intents,
            rollback_occurred=rollback_occurred
        )

    def execute(self, workflow: WorkflowSpec, variables: dict[str, Any]) -> FlowExecutionResult:
        return self.interpret(workflow, variables)
