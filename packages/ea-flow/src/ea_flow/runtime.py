import operator
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ea_flow.spec import ExecutionContext, FlowTopology, StepSpec, WorkflowSpec
from ea_flow.topology import DataFlowEdge, LogicCondition, ProcessSpec, StepDefinition
from ea_flow.types import FlowStepCategory


# ── Module-level helpers ───────────────────────────────────────────────


def _resolve_field(obj: Any, field_path: str) -> Any:
    """Resolve a dotted field path from a dict or object."""
    current = obj
    for part in field_path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return None
        if current is None:
            return None
    return current


def _set_field(target: dict[str, Any], field_path: str, value: Any) -> None:
    """Set a value at a dotted field path in a nested dict."""
    parts = field_path.split(".")
    current = target
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _apply_transformation(value: Any, rule: str) -> Any:
    """Apply a named transformation rule to a value."""
    rule = rule.strip()
    if rule == "toString()":
        return str(value)
    if rule == "toInt()":
        return int(value)
    if rule == "toFloat()":
        return float(value)
    if rule == "toUpper()":
        return str(value).upper()
    if rule == "toLower()":
        return str(value).lower()
    return value


def _coerce_token(token: str, variables: dict[str, Any]) -> Any:
    """Resolve a token as a variable reference or literal value."""
    if token in variables:
        return variables[token]
    if "." in token:
        val = _resolve_field(variables, token)
        if val is not None:
            return val
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    if len(token) >= 2 and token[0] in ("'", '"') and token[-1] == token[0]:
        return token[1:-1]
    low = token.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    return token


# Comparison operators ordered so multi-char ops are checked first.
_COMPARISON_OPS: tuple[tuple[str, Any], ...] = (
    (">=", operator.ge),
    ("<=", operator.le),
    ("!=", operator.ne),
    ("==", operator.eq),
    (">", operator.gt),
    ("<", operator.lt),
)


class _StepDefinitionAdapter(StepSpec):
    """Adapts a topology StepDefinition to the StepSpec interface."""

    def __init__(self, step_def: StepDefinition) -> None:
        self._step_def = step_def

    @property
    def name(self) -> str:
        return self._step_def.name

    @property
    def kernel_anchor(self) -> str | None:
        return None


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

    # ── P2 Coordination: ProcessSpec graph execution ───────────────────

    def _evaluate_condition(
        self, condition: LogicCondition, variables: dict[str, Any],
    ) -> bool:
        """Evaluate a LogicCondition against variables."""
        merged = {**variables, **condition.parameters}
        expr = condition.expression.strip()
        if not expr:
            return True

        for op_str, op_fn in _COMPARISON_OPS:
            if op_str in expr:
                lhs_raw, _, rhs_raw = expr.partition(op_str)
                lhs_val = _coerce_token(lhs_raw.strip(), merged)
                rhs_val = _coerce_token(rhs_raw.strip(), merged)
                return bool(op_fn(lhs_val, rhs_val))

        val = merged.get(expr)
        if val is not None:
            return bool(val)
        low = expr.lower()
        if low == "true":
            return True
        if low == "false":
            return False
        return False

    def _apply_data_flow(
        self,
        edges: list[DataFlowEdge],
        results: dict[str, StepInterpretationResult],
        context: ExecutionContext,
    ) -> None:
        """Apply DataFlowEdge transformations, injecting data into context."""
        for edge in edges:
            source_result = results.get(edge.source_step_id)
            if not source_result or source_result.intent is None:
                continue
            value = _resolve_field(source_result.intent, edge.source_field)
            if value is None:
                continue
            if edge.transformation_rule:
                value = _apply_transformation(value, edge.transformation_rule)
            _set_field(context.variables, edge.target_field, value)

    def _resolve_process_implementer(
        self, step_def: StepDefinition,
    ) -> tuple[StepImplementer | None, _StepDefinitionAdapter]:
        """Resolve an implementer for a StepDefinition, returning adapter too."""
        adapter = _StepDefinitionAdapter(step_def)
        impl = self._resolve_implementer(adapter)
        if impl is None:
            impl = self.implementers.get(step_def.id)
        return impl, adapter

    def interpret_process(
        self, process: ProcessSpec, variables: dict[str, Any],
    ) -> FlowExecutionResult:
        """
        Interpret a ProcessSpec using graph-based step traversal.

        Follows StepDefinition.next_step_ids for navigation, applies
        DataFlowEdge for inter-step data passing, and evaluates
        LogicCondition for DECISION/GATEWAY branching.
        """
        execution_id = f"exec-{process.name}-{process.version}"
        context = ExecutionContext(execution_id, dict(variables))
        results: dict[str, StepInterpretationResult] = {}
        all_logs: list[str] = []
        interpreted_intents: list[Any] = []
        executed_step_ids: list[str] = []
        overall_success = True
        rollback_occurred = False

        if not process.steps:
            return FlowExecutionResult(
                workflow_name=process.name,
                execution_id=execution_id,
                success=True,
                step_results={},
            )

        step_map: dict[str, StepDefinition] = {s.id: s for s in process.steps}

        # Index data flow edges by target step id.
        edge_index: dict[str, list[DataFlowEdge]] = {}
        for edge in process.data_flow_edges:
            edge_index.setdefault(edge.target_step_id, []).append(edge)

        current_step_id: str | None = process.steps[0].id
        max_steps = len(process.steps) * 2  # safety limit against cycles

        for _ in range(max_steps):
            if current_step_id is None:
                break

            step_def = step_map.get(current_step_id)
            if step_def is None:
                all_logs.append(f"Step '{current_step_id}' not found in process.")
                overall_success = False
                break

            # Inject data from prior step outputs via DataFlowEdge.
            self._apply_data_flow(
                edge_index.get(current_step_id, []), results, context,
            )

            # DECISION / GATEWAY: condition-based routing, no implementer required.
            if step_def.category in (
                FlowStepCategory.DECISION, FlowStepCategory.GATEWAY,
            ):
                branch = True
                if step_def.condition:
                    branch = self._evaluate_condition(
                        step_def.condition, context.variables,
                    )
                if branch and step_def.next_step_ids:
                    current_step_id = step_def.next_step_ids[0]
                elif not branch and len(step_def.next_step_ids) > 1:
                    current_step_id = step_def.next_step_ids[1]
                elif step_def.next_step_ids:
                    current_step_id = step_def.next_step_ids[0]
                else:
                    current_step_id = None
                continue

            # ACTION / EVENT / TRANSFORMATION: execute via implementer.
            impl, adapter = self._resolve_process_implementer(step_def)
            if impl is None:
                all_logs.append(f"No implementer found for '{step_def.name}'.")
                overall_success = False
                break

            res = self._interpret_step(impl, adapter, context)
            results[step_def.id] = res
            all_logs.extend(res.logs)

            if res.intent is not None:
                interpreted_intents.append(res.intent)

            if res.success:
                executed_step_ids.append(step_def.id)
                current_step_id = (
                    step_def.next_step_ids[0] if step_def.next_step_ids else None
                )
            else:
                overall_success = False
                all_logs.append(
                    f"Step '{step_def.name}' rejected. Planning compensation...",
                )

                if step_def.on_failure_step_id:
                    all_logs.append(
                        f"Redirecting to failure handler "
                        f"'{step_def.on_failure_step_id}'.",
                    )
                    current_step_id = step_def.on_failure_step_id
                    overall_success = True  # give error handler a chance
                    continue

                for prev_id in reversed(executed_step_ids):
                    prev_def = step_map.get(prev_id)
                    if prev_def is None:
                        continue
                    prev_impl, prev_adapter = self._resolve_process_implementer(
                        prev_def,
                    )
                    if prev_impl:
                        try:
                            rb_ok = prev_impl.rollback(prev_adapter, context)
                            status = "succeeded" if rb_ok else "failed"
                            all_logs.append(
                                f"Compensation plan '{prev_def.name}': {status}",
                            )
                        except Exception as e:
                            all_logs.append(
                                f"Compensation plan '{prev_def.name}' "
                                f"exception: {e!s}",
                            )
                rollback_occurred = True
                break
        else:
            all_logs.append("Max step execution limit reached (possible cycle).")
            overall_success = False

        return FlowExecutionResult(
            workflow_name=process.name,
            execution_id=execution_id,
            success=overall_success,
            step_results=results,
            logs=all_logs,
            interpreted_intents=interpreted_intents,
            rollback_occurred=rollback_occurred,
        )

    # ── P2 Coordination: FlowTopology graph execution ─────────────────

    def interpret_topology(
        self, topology: FlowTopology, variables: dict[str, Any],
    ) -> FlowExecutionResult:
        """
        Interpret a FlowTopology using transition_rules for step navigation.

        Follows topology.transition_rules (step_name → next_step_name) instead
        of sequential iteration.  Stops at exit_points.
        """
        execution_id = f"exec-{topology.name}"
        context = ExecutionContext(execution_id, dict(variables))
        results: dict[str, StepInterpretationResult] = {}
        all_logs: list[str] = []
        interpreted_intents: list[Any] = []
        interpreted_specs: list[StepSpec] = []
        overall_success = True
        rollback_occurred = False

        step_map: dict[str, StepSpec] = {s.name: s for s in topology.steps}

        current_name: str | None = topology.entry_point
        if current_name is None and topology.steps:
            current_name = topology.steps[0].name

        max_steps = len(topology.steps) * 2 if topology.steps else 1

        for _ in range(max_steps):
            if current_name is None:
                break

            spec = step_map.get(current_name)
            if spec is None:
                all_logs.append(f"Step '{current_name}' not found in topology.")
                overall_success = False
                break

            implementer = self._resolve_implementer(spec)
            if implementer is None:
                all_logs.append(f"No implementer found for '{spec.name}'.")
                overall_success = False
                break

            res = self._interpret_step(implementer, spec, context)
            results[spec.name] = res
            all_logs.extend(res.logs)

            if res.intent is not None:
                interpreted_intents.append(res.intent)

            if res.success:
                interpreted_specs.append(spec)
                if current_name in topology.exit_points:
                    current_name = None
                else:
                    current_name = topology.transition_rules.get(current_name)
            else:
                overall_success = False
                all_logs.append(
                    f"Step '{spec.name}' rejected. Planning compensation...",
                )
                for prev_spec in reversed(interpreted_specs):
                    impl = self._resolve_implementer(prev_spec)
                    if impl:
                        try:
                            rb_ok = impl.rollback(prev_spec, context)
                            status = "succeeded" if rb_ok else "failed"
                            all_logs.append(
                                f"Compensation plan '{prev_spec.name}': {status}",
                            )
                        except Exception as e:
                            all_logs.append(
                                f"Compensation plan '{prev_spec.name}' "
                                f"exception: {e!s}",
                            )
                rollback_occurred = True
                break
        else:
            all_logs.append("Max step execution limit reached (possible cycle).")
            overall_success = False

        return FlowExecutionResult(
            workflow_name=topology.name,
            execution_id=execution_id,
            success=overall_success,
            step_results=results,
            logs=all_logs,
            interpreted_intents=interpreted_intents,
            rollback_occurred=rollback_occurred,
        )
