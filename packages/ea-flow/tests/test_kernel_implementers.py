from ea_flow.kernel_actions import AddRuleStepSpec, DeprecateRuleStepSpec
from ea_flow.kernel_implementers import AddRuleImplementer, DeprecateRuleImplementer
from ea_flow.spec import ExecutionContext


def test_add_rule_implementer_rejects_wrong_spec_type() -> None:
    implementer = AddRuleImplementer()
    context = ExecutionContext("exec-1", {})
    wrong_spec = DeprecateRuleStepSpec("rule-1")

    result = implementer.execute(wrong_spec, context)

    assert not result.success
    assert "invalid step type" in result.logs[0]


def test_add_rule_implementer_requires_governance_system() -> None:
    implementer = AddRuleImplementer()
    context = ExecutionContext("exec-1", {})
    spec = AddRuleStepSpec("act-1", {"id": "rule-1"})

    result = implementer.execute(spec, context)

    assert not result.success
    assert "governance_system not found" in result.logs[0]


def test_add_rule_implementer_success_path() -> None:
    implementer = AddRuleImplementer()
    context = ExecutionContext("exec-1", {"governance_system": object()})
    spec = AddRuleStepSpec("act-1", {"id": "rule-1"})

    result = implementer.execute(spec, context)

    assert result.success
    assert result.output == {"rule_id": "rule-1"}


def test_deprecate_rule_implementer_success_and_rollback() -> None:
    implementer = DeprecateRuleImplementer()
    context = ExecutionContext("exec-1", {})
    spec = DeprecateRuleStepSpec("rule-1")

    result = implementer.execute(spec, context)

    assert result.success
    assert result.output == {"deprecated_id": "rule-1"}
    assert implementer.rollback(spec, context) is True
