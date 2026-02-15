from ea_flow.kernel_actions import AddRuleStepSpec, DeprecateRuleStepSpec
from ea_flow.runtime import StepExecutionResult, StepImplementer
from ea_flow.spec import ExecutionContext, StepSpec


class AddRuleImplementer(StepImplementer):
    """Interpret add-rule specs into declarative kernel intents."""

    def execute(self, spec: StepSpec, context: ExecutionContext) -> StepExecutionResult:
        if not isinstance(spec, AddRuleStepSpec):
            return StepExecutionResult(False, None, ["Error: invalid step type for AddRuleImplementer"])

        rule_id = str(spec.rule_data.get("id", "")).strip()
        if not rule_id:
            return StepExecutionResult(False, None, ["Error: rule id is required"])

        intent = {
            "intent_type": "kernel.submit_rule",
            "rule_id": rule_id,
            "rule_payload": dict(spec.rule_data),
            "kernel_anchor": spec.kernel_anchor,
        }
        logs = [f"Planned kernel rule submission intent: {rule_id}"]
        return StepExecutionResult(True, intent, logs)

    def rollback(self, spec: StepSpec, context: ExecutionContext) -> bool:
        # Intent planning is side-effect free; rollback only confirms compensation feasibility.
        return isinstance(spec, AddRuleStepSpec)


class DeprecateRuleImplementer(StepImplementer):
    """Interpret deprecate-rule specs into declarative kernel intents."""

    def execute(self, spec: StepSpec, context: ExecutionContext) -> StepExecutionResult:
        if not isinstance(spec, DeprecateRuleStepSpec):
            return StepExecutionResult(False, None, ["Error: invalid step type for DeprecateRuleImplementer"])

        rule_id = spec.rule_id.strip()
        if not rule_id:
            return StepExecutionResult(False, None, ["Error: rule id is required"])

        intent = {
            "intent_type": "kernel.deprecate_rule",
            "rule_id": rule_id,
            "kernel_anchor": spec.kernel_anchor,
        }
        logs = [f"Planned kernel rule deprecation intent: {rule_id}"]
        return StepExecutionResult(True, intent, logs)

    def rollback(self, spec: StepSpec, context: ExecutionContext) -> bool:
        # Intent planning is side-effect free; rollback only confirms compensation feasibility.
        return isinstance(spec, DeprecateRuleStepSpec)
