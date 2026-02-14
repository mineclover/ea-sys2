from ea_flow.kernel_actions import AddRuleStepSpec, DeprecateRuleStepSpec
from ea_flow.runtime import StepExecutionResult, StepImplementer
from ea_flow.spec import ExecutionContext, StepSpec


class AddRuleImplementer(StepImplementer):
    """How to actually add a rule to the kernel."""

    def execute(self, spec: StepSpec, context: ExecutionContext) -> StepExecutionResult:
        if not isinstance(spec, AddRuleStepSpec):
            return StepExecutionResult(False, None, ["Error: invalid step type for AddRuleImplementer"])

        system = context.variables.get("governance_system")
        if not system:
            return StepExecutionResult(False, None, ["Error: governance_system not found in context"])

        # In a real system, we'd call system.submit_rule(spec.rule_data)
        logs = [f"Submitting rule {spec.rule_data.get('id')} to kernel"]
        return StepExecutionResult(True, {"rule_id": spec.rule_data.get("id")}, logs)

    def rollback(self, spec: StepSpec, context: ExecutionContext) -> bool:
        if not isinstance(spec, AddRuleStepSpec):
            return False
        print(f"[Rollback] Removing rule {spec.rule_data.get('id')}")
        return True


class DeprecateRuleImplementer(StepImplementer):
    """How to actually deprecate a rule in the kernel."""

    def execute(self, spec: StepSpec, context: ExecutionContext) -> StepExecutionResult:
        if not isinstance(spec, DeprecateRuleStepSpec):
            return StepExecutionResult(False, None, ["Error: invalid step type for DeprecateRuleImplementer"])

        logs = [f"Deprecating rule {spec.rule_id}"]
        return StepExecutionResult(True, {"deprecated_id": spec.rule_id}, logs)

    def rollback(self, spec: StepSpec, context: ExecutionContext) -> bool:
        if not isinstance(spec, DeprecateRuleStepSpec):
            return False
        print(f"[Rollback] Restoring rule {spec.rule_id}")
        return True
