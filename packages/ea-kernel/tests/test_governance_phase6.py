"""Integration tests for Governance Phase 6: Multi-tenancy."""

import pytest
from pathlib import Path
from ea_kernel.governance import GovernanceSystem
from ea_kernel.types import (
    KernelSchema, KernelEntity, Layer, KernelValidityRule,
    RuleMetadata, RuleCategory, RuleConfidence, RuleGroup, RuleCorpusEntry
)
from ea_kernel.governance_types import (
    RuleAsset, RuleProvenance, RuleLifecycle, RuleLifecycleState
)
from datetime import UTC, datetime

# --- Mocking Utilities ---

def make_simple_schema():
    return KernelSchema(
        attributes=(),
        entities=(
            KernelEntity(name="Source", layer=Layer.L1),
            KernelEntity(name="Target", layer=Layer.L1),
        ),
        relations=(),
        validity_rules=(),
    )

def make_rule_asset(rule_id: str, valid: bool = True) -> RuleAsset:
    rule = KernelValidityRule(
        id=rule_id,
        source_pattern="Source",
        target_pattern="Target",
        relationship_name="relates",
        valid=valid,
        priority=100,
    )
    meta = RuleMetadata(
        domain="core",
        tags=("test",),
        category=RuleCategory.STRUCTURAL,
        confidence=RuleConfidence.UNIVERSAL,
        source="manual",
        established_version="1.0",
        rationale="Test",
        group=RuleGroup.FLOW,
    )
    entry = RuleCorpusEntry(rule, meta)
    provenance = RuleProvenance(
        author="tester", source_type="manual", source_reference="ref",
        created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
    )
    lifecycle = RuleLifecycle(current_state=RuleLifecycleState.DRAFT)
    return RuleAsset(entry, provenance, lifecycle)

from ea_kernel.multi_tenancy import MultiTenantManager

# --- Mocking Utilities ---

# --- Tests ---

def test_tenant_isolation(tmp_path):
    """Test that tenants have isolated rule sets."""
    base_dir = tmp_path / "mt_data"
    schema = make_simple_schema()
    manager = MultiTenantManager(base_dir, schema)
    
    # 1. Tenant A Setup
    tenant_a = manager.get_tenant("tenant-a")
    rule_a = make_rule_asset("rule-for-a")
    tenant_a.submit_rule(rule_a)
    tenant_a.approve_rule("rule-for-a", "admin-a")
    
    # 2. Tenant B Setup
    tenant_b = manager.get_tenant("tenant-b")
    
    # 3. Isolation Check
    # A should allow
    res_a = tenant_a.evaluate("Source", "Target", "relates")
    assert res_a.judgment.verdict is True
    
    # B should deny (default) because it doesn't have the rule
    res_b = tenant_b.evaluate("Source", "Target", "relates")
    assert res_b.judgment.verdict is False
    
    # 4. Independent Evolution
    rule_b = make_rule_asset("rule-for-b")
    tenant_b.submit_rule(rule_b)
    tenant_b.approve_rule("rule-for-b", "admin-b")
    
    res_b2 = tenant_b.evaluate("Source", "Target", "relates")
    assert res_b2.judgment.verdict is True
    # Verify B is using Rule B, not Rule A
    assert res_b2.judgment.evidence[0].entry.rule.id == "rule-for-b"

def test_cross_tenant_aggregation(tmp_path):
    """Test aggregation of data across tenants."""
    base_dir = tmp_path / "mt_agg"
    schema = make_simple_schema()
    manager = MultiTenantManager(base_dir, schema)
    
    # Tenant A
    ta = manager.get_tenant("A")
    ta.submit_rule(make_rule_asset("shared-rule"))
    ta.approve_rule("shared-rule", "admin")
    ta.evaluate("Source", "Target", "relates") # 1 judgment
    
    # Tenant B
    tb = manager.get_tenant("B")
    tb.submit_rule(make_rule_asset("shared-rule")) # Adoption of same rule ID
    tb.approve_rule("shared-rule", "admin")
    tb.evaluate("Source", "Target", "relates") # 1 judgment
    tb.evaluate("Source", "Target", "relates") # 2 judgments
    
    # Analysis
    # report = manager.global_analysis() # Removed method
    adoption = manager.aggregate_rule_adoption()
    
    # assert report["total_tenants"] == 2
    # assert report["total_judgments"] == 3
    assert adoption["shared-rule"] == 2
    
    # Optional: Common Patterns
    standards = manager.find_common_patterns(min_adoption=2)
    assert "shared-rule" in standards
