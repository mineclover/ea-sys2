import pytest
from pathlib import Path
from ea_governance.facade import GovernanceContainer, KernelSchema
from ea_decision.registry import registry, DecisionPattern

def test_facade_extra_cases(tmp_path):
    schema = KernelSchema(attributes=(), entities=(), relations=())
    container = GovernanceContainer(tmp_path, schema)
    
    # 1. get_transaction_status None
    assert container.get_transaction_status("non-existent") is None
    
    # 2. get_flow_spec for rule_creation
    spec = container.get_flow_spec("ea:kernel:rule_creation")
    assert spec is not None
    assert spec["name"] == "AddRuleStep"
    
    # 3. get_flow_spec None
    assert container.get_flow_spec("invalid") is None
    
    # 4. execute_decision invalid report
    from ea_decision.topic import Topic
    topic = Topic("T", "D")
    res = container.execute_decision("wrong-id", topic)
    assert res["success"] is False
    assert res["error"] == "Invalid Report ID"

def test_facade_propose_initiative_with_pattern(tmp_path):
    schema = KernelSchema(attributes=(), entities=(), relations=())
    container = GovernanceContainer(tmp_path, schema)
    
    # Register dummy pattern
    from ea_decision.pattern import DecisionComplexity
    pattern = DecisionPattern(name="TestPattern", description="Des", complexity=DecisionComplexity.LOW if hasattr(DecisionComplexity, 'LOW') else DecisionComplexity.TRIVIAL)
    registry.register(pattern)
    
    res = container.propose_initiative("P1", "D1", pattern_name="TestPattern")
    assert res["topic"].pattern_name == "TestPattern"
    
def test_facade_propose_initiative_exception(tmp_path):
    # Mock execution_service to fail
    schema = KernelSchema(attributes=(), entities=(), relations=())
    container = GovernanceContainer(tmp_path, schema)
    
    # Force failure by closing tx manager or something? 
    # Let's just mock the begin_transaction to raise
    container.execution_service.tx_manager.begin_transaction = lambda *a, **k: exec('raise(Exception("Force Fail"))')
    
    with pytest.raises(Exception) as exc:
        container.propose_initiative("P1", "D1")
    assert "Force Fail" in str(exc.value)
