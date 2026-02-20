

import pytest
from ea_decision.topic import Topic
from ea_decision.types import DecisionStatus
from ea_governance.execution_service import ExecutionService
from ea_kernel.governance import GovernanceSystem
from ea_kernel.types import KernelSchema


@pytest.fixture
def mock_kernel(tmp_path):
    schema = KernelSchema(attributes=(), entities=(), relations=())
    return GovernanceSystem(tmp_path / "kernel", schema)

def test_full_execution_bridge(mock_kernel):
    # 1. Setup Decision Topic
    topic = Topic(
        title="Scaling Limit Policy",
        description="We need a hard limit on horizontal scaling to control costs."
    )
    topic.add_option("Limit to 5", "Hard limit of 5 instances")
    opt_id = topic.options[0].id

    # 2. Finalize a Plan (Report) with Modeling Actions
    report = topic.finalize_plan(
        title="Cost Control Plan",
        summary="Implement rule-cost-limit",
        selected_option_id=opt_id,
        rationale="Budget constraints"
    )

    # Add a modeling action with payload
    report.add_action(
        action_type="create_rule",
        target="rule:cost-limit",
        description="Limit instances to 5",
        payload={"id": "cost-limit-rule", "limit": 5}
    )

    # 3. Interpret via Service
    service = ExecutionService(mock_kernel)
    success = service.interpret_report(report)

    # 4. Assertions
    assert success is True
    assert report.executed_at is not None
    assert any("Planned kernel rule submission intent: cost-limit-rule" in log for log in report.execution_log)
    assert report.modeling_actions[0].status == "interpreted"


def test_execution_bridge_updates_topic_decision_status(mock_kernel):
    """GAP-1: Verify that flow execution updates the decision status back."""
    topic = Topic(title="Policy Change", description="Need a new rule")
    topic.add_option("Add rule", "Add a governance rule")
    opt_id = topic.options[0].id

    report = topic.finalize_plan(
        title="Rule Plan", summary="Add rule", selected_option_id=opt_id, rationale="Required"
    )
    report.add_action(
        action_type="create_rule", target="rule:new-policy",
        description="New policy rule", payload={"id": "new-policy-rule"},
    )

    assert topic.report.decision.status == DecisionStatus.PROPOSED

    service = ExecutionService(mock_kernel)
    success = service.interpret_report(report, topic=topic)

    assert success is True
    # Decision status must be ACCEPTED after successful execution
    assert topic.report.decision.status == DecisionStatus.ACCEPTED
    assert topic.report.transaction_id is not None
    assert topic.status == "completed"


def test_execution_bridge_failure_rejects_decision(mock_kernel):
    """GAP-1: Failed execution rejects the decision and re-opens topic."""
    topic = Topic(title="Bad Action", description="Will fail")
    topic.add_option("Unknown action", "Action that cannot map")
    opt_id = topic.options[0].id

    report = topic.finalize_plan(
        title="Failing Plan", summary="Will fail", selected_option_id=opt_id, rationale="Test"
    )
    # Add an action with an unmappable type to force failure path
    from ea_decision.topic import ModelingAction
    report.modeling_actions.append(
        ModelingAction(action_type="unknown_action", target="x", description="bad")
    )

    service = ExecutionService(mock_kernel)
    # No mappable steps → returns False
    success = service.interpret_report(report, topic=topic)

    assert success is False


def test_execution_bridge_propagates_trace_id(mock_kernel):
    """GAP-5: trace_id from Topic propagates to the transaction."""
    topic = Topic(title="Traced", description="Test trace")
    topic.add_option("Opt", "Desc")
    opt_id = topic.options[0].id

    report = topic.finalize_plan("Plan", "S", opt_id, "R")
    report.add_action("create_rule", "rule:traced", "desc", payload={"id": "traced-rule"})

    service = ExecutionService(mock_kernel)
    success = service.interpret_report(report, topic=topic)

    assert success is True
    # Transaction should carry topic's trace_id
    tx = service.tx_manager.get_transaction(report.transaction_id)
    assert tx is not None
    assert tx.trace_id == topic.trace_id
    assert tx.trace_id.startswith("trace-")


def test_execution_bridge_backward_compat_without_topic(mock_kernel):
    """Calling interpret_report without topic still works (backward compat)."""
    topic = Topic(title="Test", description="Test")
    topic.add_option("Opt", "Desc")
    report = topic.finalize_plan("Plan", "S", topic.options[0].id, "R")
    report.add_action("create_rule", "rule:x", "desc", payload={"id": "rule-x"})

    service = ExecutionService(mock_kernel)
    success = service.interpret_report(report)  # no topic argument

    assert success is True
    # Decision status should NOT be updated without topic
    assert report.decision.status == DecisionStatus.PROPOSED
