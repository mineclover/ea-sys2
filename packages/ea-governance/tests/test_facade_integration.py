
import pytest
from ea_governance.facade import GovernanceContainer, KernelSchema
from ea_governance.transaction import TransactionStatus
from ea_kernel.governance import GovernanceSystem

# Fix KernelSchema mock as before
@pytest.fixture
def mock_container(tmp_path):
    schema = KernelSchema(attributes=(), entities=(), relations=())
    return GovernanceContainer(tmp_path, schema)

def test_facade_initiative_proposal(mock_container):
    # 1. Propose Initiative
    result = mock_container.propose_initiative("Modernize Stack", "Move to Python 3.12")
    
    # 2. Check Response
    assert "topic" in result
    assert "transaction_id" in result
    
    tx_id = result["transaction_id"]
    topic = result["topic"]
    
    assert topic.title == "Modernize Stack"
    
    # 3. Check Transaction Status via Facade
    status = mock_container.get_transaction_status(tx_id)
    assert status["status"] == TransactionStatus.COMMITTED
    
    # 4. Check Logs
    logs = mock_container.get_transaction_logs(tx_id)
    assert len(logs) > 0

def test_facade_decision_execution(mock_container):
    # 1. Setup Topic & Report
    topic = mock_container.create_topic("Test Decision", "Desc")
    topic.add_option("Opt1", "Desc")
    report = topic.finalize_plan("Plan", "Summary", topic.options[0].id, "Ratio")
    report.add_action("create_rule", "rule:x", "desc", payload={"id":"x"})
    
    # 2. Execute via Facade
    result = mock_container.execute_decision(report.id, topic)
    
    # 3. Check Response
    assert result["success"] is True
    assert "transaction_id" in result
    
    tx_id = result["transaction_id"]
    
    # 4. Verify Status
    status = mock_container.get_transaction_status(tx_id)
    assert status["status"] == TransactionStatus.COMMITTED
