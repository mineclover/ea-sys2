import pytest
from ea_flow.kernel_actions import AddRuleStepSpec, DeprecateRuleStepSpec

def test_add_rule_step_spec():
    data = {"id": "R1", "description": "Test Rule"}
    step = AddRuleStepSpec("action_1", data)
    
    assert step.name == "add_rule:action_1"
    assert step.kernel_anchor == "ea:kernel:rule_creation"
    assert step.rule_data == data

def test_deprecate_rule_step_spec():
    step = DeprecateRuleStepSpec("R1")
    
    assert step.name == "deprecate_rule:R1"
    assert step.kernel_anchor == "ea:kernel:rule:R1"
    assert step.rule_id == "R1"
