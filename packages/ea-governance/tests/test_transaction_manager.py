
import pytest
from ea_decision.topic import Topic
from ea_flow.runtime import StepExecutionResult, StepImplementer
from ea_flow.spec import ExecutionContext, StepSpec
from ea_governance.execution_service import ExecutionService
from ea_governance.transaction import TransactionStatus
from ea_kernel.governance import GovernanceSystem
from ea_kernel.types import KernelSchema


class MockFailStepSpec(StepSpec):
    @property
    def name(self) -> str:
        return "fail_trigger"

    @property
    def kernel_anchor(self) -> str:
        return "mock_fail_anchor"


class MockFailImplementer(StepImplementer):
    def execute(self, spec: StepSpec, context: ExecutionContext) -> StepExecutionResult:
        return StepExecutionResult(False, None, ["Step failed intentionally"])

    def rollback(self, spec: StepSpec, context: ExecutionContext) -> bool:
        return True


@pytest.fixture
def mock_kernel(tmp_path):
    schema = KernelSchema(attributes=(), entities=(), relations=())
    return GovernanceSystem(tmp_path / "kernel", schema)


def test_transaction_lifecycle_success(mock_kernel):
    # 1. Setup Service
    service = ExecutionService(mock_kernel)

    # 2. Setup Report
    topic = Topic("Test Tx", "Desc")
    topic.add_option("Opt1", "Desc")
    report = topic.finalize_plan("Plan", "Summary", topic.options[0].id, "Rationale")
    report.add_action("create_rule", "rule:test", "desc", payload={"id": "r1"})

    # 3. Interpret
    success = service.interpret_report(report)

    # 4. Verification
    assert success is True
    assert report.transaction_id is not None

    # Check Manager
    tx = service.tx_manager.get_transaction(report.transaction_id)
    assert tx is not None
    assert tx.status == TransactionStatus.COMMITTED
    assert "Transaction committed successfully." in tx.logs[-1]


def test_transaction_lifecycle_rollback(mock_kernel):
    # 1. Setup Service with a failing step implementer
    class TestService(ExecutionService):
        def _map_action_to_step(self, action, index_key):
            if action.action_type == "fail_trigger":
                return MockFailStepSpec()
            return super()._map_action_to_step(action, index_key)

    from ea_flow.kernel_implementers import AddRuleImplementer, DeprecateRuleImplementer
    from ea_flow.runtime import FlowRuntime

    implementers = {
        "add_rule": AddRuleImplementer(),
        "deprecate_rule": DeprecateRuleImplementer(),
        "fail_trigger": MockFailImplementer(),
    }
    runtime = FlowRuntime(implementers=implementers)
    service = TestService(mock_kernel, runtime=runtime)

    # 2. Setup Report
    topic = Topic("Test Fail", "Desc")
    topic.add_option("Opt1", "Desc")
    report = topic.finalize_plan("Plan", "Summary", topic.options[0].id, "Rationale")
    report.add_action("create_rule", "rule:test", "desc", payload={"id": "r1"})
    report.add_action("fail_trigger", "target:fail", "desc")  # This triggers failure

    # 3. Interpret
    success = service.interpret_report(report)

    # 4. Verification
    assert success is False
    assert report.transaction_id is not None

    # Check Manager
    tx = service.tx_manager.get_transaction(report.transaction_id)
    assert tx is not None
    assert tx.status == TransactionStatus.ROLLED_BACK
    assert "Transaction rolled back" in tx.logs[-1]
