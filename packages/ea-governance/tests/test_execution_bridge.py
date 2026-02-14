
import pytest
from pathlib import Path
from ea_decision.topic import Topic, DesignDecision
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
    
    # 3. Execute via Service
    service = ExecutionService(mock_kernel)
    success = service.execute_report(report)
    
    # 4. Assertions
    assert success is True
    assert report.executed_at is not None
    assert any("Submitting rule cost-limit-rule" in log for log in report.execution_log)
    assert report.modeling_actions[0].status == "completed"
