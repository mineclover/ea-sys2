import pytest
from pathlib import Path
from ea_flow.spec import UseCaseSpec, KernelGroundedStepSpec, FlowMetaStep, ExecutionContext
from ea_flow.runtime import StepExecutionResult
from ea_governance.facade import GovernanceContainer, KernelSchema
from ea_governance.transaction import TransactionStatus

def test_use_case_business_modeling(tmp_path):
    # 1. Setup Environment
    schema = KernelSchema(attributes=(), entities=(), relations=())
    container = GovernanceContainer(tmp_path, schema)
    
    # 2. Define a "Business Process" Specification
    meta = FlowMetaStep(
        name="SecurityCompliance", 
        description="Ensures all rules meet ISO27001",
        kernel_type_requirement="rule"
    )
    
    # In this test, we use a generic name that the runtime can't resolve by default
    # but container.runtime has default implementers for "add_rule" etc.
    # Let's use a name that matches physical implementer if we want real logic,
    # or just verify the spec structure.
    
    step1 = KernelGroundedStepSpec("ea:kernel:security", meta)
    
    # For the test to pass execution, we need an implementer for step1.name
    # "SecurityCompliance on ea:kernel:security"
    from ea_flow.runtime import StepImplementer
    class MockImpl(StepImplementer):
        def execute(self, spec, ctx): return StepExecutionResult(True, None, ["Executed"])
        def rollback(self, spec, ctx): return True
    
    container.runtime.implementers[step1.name] = MockImpl()
    
    uc = UseCaseSpec(
        name="ApplySecurityStandard",
        description="Apply corporate security standards to the current kernel state.",
        primary_actor="CISO",
        success_criteria=["Rule defined", "Audit log created"],
        steps=[step1]
    )
    
    # 3. Execute the Use Case Spec via Governance (Coordination Truth)
    variables = {"priority": "high"}
    result = container.execute_use_case(uc, variables)
    
    # 4. Verify Coordination & Integrity
    assert result["success"] is True
    assert "transaction_id" in result
    
    tx_id = result["transaction_id"]
    status = container.get_transaction_status(tx_id)
    assert status["status"] == TransactionStatus.COMMITTED
    
    # Verify the procedural truth metadata was captured
    assert result["metrics"]["specs_processed"] == 1
    
    # Verify modeling identity
    assert uc.primary_actor == "CISO"
    assert "Audit log created" in uc.success_criteria
