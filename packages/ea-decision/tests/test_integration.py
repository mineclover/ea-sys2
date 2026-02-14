import pytest
import uuid
from datetime import datetime, UTC

from ea_decision.types import DecisionResult
from ea_kernel.governance_types import RuleAsset, RuleLifecycle, RuleProvenance, RuleLifecycleState
from ea_kernel.types import RuleCorpusEntry, KernelValidityRule, RuleMetadata, RuleCategory, RuleConfidence, RuleGroup

def test_decision_with_kernel_rule_asset():
    """Verify that a DecisionResult can hold a RuleAsset from ea-kernel."""
    
    # Create a Kernel RuleAsset
    rule = KernelValidityRule(
        id="rule-test-1",
        source_pattern="Source",
        target_pattern="Target",
        relationship_name="relates",
        valid=True
    )
    metadata = RuleMetadata(
        domain="demotest",
        tags=("test",),
        category=RuleCategory.BEHAVIORAL,
        confidence=RuleConfidence.EMPIRICAL,
        source="integration-test",
        established_version="0.0.1",
        rationale="Integration test",
        group=RuleGroup.FLOW
    )
    entry = RuleCorpusEntry(rule=rule, metadata=metadata)
    provenance = RuleProvenance(
        author="tester",
        source_type="manual",
        source_reference="integration-test-ref",
        created_at=datetime.now(UTC).isoformat() + "Z",
        updated_at=datetime.now(UTC).isoformat() + "Z",
        version=1
    )
    lifecycle = RuleLifecycle(current_state=RuleLifecycleState.DRAFT)
    
    asset = RuleAsset(
        entry=entry,
        provenance=provenance,
        lifecycle=lifecycle
    )
    
    # Create DecisionResult holding this asset
    result = DecisionResult(
        id=str(uuid.uuid4()),
        intent_id="intent-1",
        choice_id="choice-1",
        outcome_artifact=asset,
        timestamp=datetime.now(UTC).isoformat()
    )
    
    assert result.outcome_artifact.id == "rule-test-1"
    assert isinstance(result.outcome_artifact, RuleAsset)
