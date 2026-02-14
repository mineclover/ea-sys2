from ea_flow.spec import FlowGenerationRule, FlowTopology
from ea_governance.meta_model import MetaGenerator


def test_concretization_chain_strict_separation():
    # 1. Setup the Generator
    engine = MetaGenerator()

    # 2. Register a Flow Topology with Logic Encapsulation
    approval_flow = FlowTopology(
        name="PaymentApproval",
        generation_rules=[
            FlowGenerationRule(
                source_kernel_type="Rule",
                target_flow_type="ApprovalFlow",
                naming_pattern="Approval for {source_name}",
                # Logic Condition: "This flow applies when amount >= 100k"
                logic_conditions={"amount": {">=": 100000}}
            )
        ]
    )
    engine.register_flow_topology(approval_flow)

    # 3. Simulate User Intent
    intent = "We need an ApprovalFlow for high-value payments (over 100k)."

    # 4. Verify Suggestions
    suggestion = engine.suggest_from_intent(intent)

    # Assertion 1: Kernel Action is purely structural ("Define Rule")
    # It does NOT say "Define Rule where amount > 100k"
    assert "Define Rule for ApprovalFlow" in suggestion.suggested_kernel_actions[0]

    # Assertion 2: Flow Suggestion is correct
    assert suggestion.suggested_flow_topology == "PaymentApproval"

    # In a real scenario, we would assert that the returned FlowSpec contains the logic
    # derived from the FlowGenerationRule.logic_conditions
