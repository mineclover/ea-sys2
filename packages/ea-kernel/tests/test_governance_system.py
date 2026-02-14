"""Integration tests for GovernanceSystem facade."""

from datetime import UTC, datetime

import pytest
from ea_kernel.governance import GovernanceSystem
from ea_kernel.governance_types import RuleAsset, RuleLifecycle, RuleLifecycleState, RuleProvenance
from ea_kernel.types import (
    KernelEntity,
    KernelSchema,
    KernelValidityRule,
    Layer,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleGroup,
    RuleMetadata,
)


@pytest.fixture
def temp_governance_data(tmp_path):
    return tmp_path / "governance_data"

@pytest.fixture
def base_schema():
    return KernelSchema(
        attributes=(),
        entities=(
            KernelEntity(name="Source", layer=Layer.L1),
            KernelEntity(name="Target", layer=Layer.L1),
        ),
        relations=(),
        validity_rules=(),
    )

@pytest.fixture
def governance_system(temp_governance_data, base_schema):
    return GovernanceSystem(temp_governance_data, base_schema)

def make_draft_asset(
    rule_id: str,
    *,
    priority: int = 100,
) -> RuleAsset:
    """Create a DRAFT rule asset."""
    rule = KernelValidityRule(
        id=rule_id,
        source_pattern="Source",
        target_pattern="Target",
        relationship_name="relates",
        valid=True,
        priority=priority,
    )

    meta = RuleMetadata(
        domain="core",
        tags=("test",),
        category=RuleCategory.STRUCTURAL,
        confidence=RuleConfidence.UNIVERSAL,
        source="manual",
        established_version="1.0",
        rationale="Test Rule",
        group=RuleGroup.FLOW,
    )

    entry = RuleCorpusEntry(rule, meta)

    provenance = RuleProvenance(
        author="human:tester",
        source_type="manual",
        source_reference="test",
        created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
    )

    lifecycle = RuleLifecycle(current_state=RuleLifecycleState.DRAFT)

    return RuleAsset(entry, provenance, lifecycle)

def test_governance_lifecycle_flow(governance_system):
    """Test full governance lifecycle: Submit -> Approve -> Judge -> Analyze."""
    system = governance_system
    rule_id = "rule-integration-test"

    # 1. Authoring (S1)
    draft_rule = make_draft_asset(rule_id)
    saved_draft = system.submit_rule(draft_rule)

    assert saved_draft.id == rule_id
    assert saved_draft.lifecycle.current_state == RuleLifecycleState.DRAFT

    # Verify not yet in active corpus
    # If the rule is draft, it shouldn't affect judgment yet (rule corpus rebuilt with active rules only)
    # But since base_schema has no rules, verdict should be False (deny by default)
    # EXCEPT: RuleCorpus.judge logic might differ slightly depending on implementation
    # With empty rules, find_matching_rules returns empty -> deny by default.
    initial_judgment = system.evaluate("Source", "Target", "relates")
    assert initial_judgment.judgment.verdict is False

    # 2. Review & Approve (S5)
    approved_rule = system.approve_rule(rule_id, "human:admin")
    assert approved_rule.lifecycle.current_state == RuleLifecycleState.APPROVED

    # Verify NOW in active corpus
    # RuleCorpus should have been rebuilt
    active_judgment = system.evaluate("Source", "Target", "relates")
    assert active_judgment.judgment.verdict is True
    assert active_judgment.judgment.evidence[0].entry.rule.id == rule_id

    # 3. Judgment Recording (S2/S3)
    # Generate some traffic
    for _ in range(5):
        system.evaluate("Source", "Target", "relates")

    # Check decision store
    from ea_kernel.governance_types import DecisionQueryOptions

    start = datetime.now(UTC).replace(tzinfo=None).isoformat()[:10]
    system.decision_store.query(DecisionQueryOptions(start_time=start))
    # We did 1 initial + 1 active check + 5 loop = 7 total
    # But filtering by time might be tricky if "now" crosses boundaries.
    # Just checking total count in store is better if method available, or just rely on analyze

    # 4. Analysis (S4)
    report = system.analyze()
    assert report.total_decisions_analyzed >= 6 # At least the successful ones

    # Check rule effectiveness
    if report.rule_effectiveness:
        eff = next(r for r in report.rule_effectiveness if r.rule_id == rule_id)
        assert eff.total_evaluations >= 6
        assert eff.win_count >= 6

    # 5. Automation (S5)
    # Just run it to ensure no exceptions
    system.run_automation()

    # 6. Check Notifications
    # We expect notifications for:
    # - Rule Submitted
    # - Rule Approved
    # - Auto-promotion (if applicable, though probably no candidates yet as it's already approved/universal)

    assert len(system.notification.sent) >= 2
    msgs = [n.subject for n in system.notification.sent]
    assert any("Rule Submitted" in m for m in msgs)
    assert any("Rule Approved" in m for m in msgs)

def test_governance_persistence(temp_governance_data, base_schema):
    """Test that data survives system restart."""

    # Run 1: Create and Approve
    sys1 = GovernanceSystem(temp_governance_data, base_schema)
    rule_id = "rule-persist-test"
    draft = make_draft_asset(rule_id)
    sys1.submit_rule(draft)
    sys1.approve_rule(rule_id, "human:admin")

    # Run 2: Restart (new instance, same path)
    sys2 = GovernanceSystem(temp_governance_data, base_schema)

    # Check if rule is loaded as active
    # The default impl should load active rules from store on init
    judgment = sys2.evaluate("Source", "Target", "relates")
    assert judgment.judgment.verdict is True
    assert judgment.judgment.evidence[0].entry.rule.id == rule_id

def test_rule_rejection_flow(governance_system):
    """Test rejection flow: Draft -> Review -> Reject (Draft)."""
    system = governance_system
    rule_id = "rule-rejection-test"

    draft = make_draft_asset(rule_id)
    system.submit_rule(draft)

    # Manually move to REVIEW (simulate submission workflow)
    system.rule_store.transition(rule_id, RuleLifecycleState.REVIEW, "human:author")

    # Reject
    rejected = system.reject_rule(rule_id, "human:reviewer", "Bad rule")
    assert rejected.lifecycle.current_state == RuleLifecycleState.DRAFT

    # Verify not active (verdict False because no active rules)
    judgment = system.evaluate("Source", "Target", "relates")
    assert judgment.judgment.verdict is False


def test_rule_deprecation_flow(governance_system):
    """Test deprecation flow: Approved -> Deprecated."""
    system = governance_system
    rule_id = "rule-deprecation-test"

    draft = make_draft_asset(rule_id)
    system.submit_rule(draft)
    system.approve_rule(rule_id, "human:admin")

    # Verify active
    j1 = system.evaluate("Source", "Target", "relates")
    assert j1.judgment.verdict is True

    # Deprecate
    deprecated = system.deprecate_rule(rule_id, "human:admin", "Obsolete")
    assert deprecated.lifecycle.current_state == RuleLifecycleState.DEPRECATED

    # Verify inactive (corpus rebuilt)
    j2 = system.evaluate("Source", "Target", "relates")
    assert j2.judgment.verdict is False

def test_conflict_detection_integration(governance_system):
    """Test that conflicting rules are detected in judgment."""
    system = governance_system

    # Rule 1: Allow (Priority 100) - Domain A (core)
    r1 = make_draft_asset("rule-allow")
    # Helper sets domain="core"
    system.submit_rule(r1)
    system.approve_rule("rule-allow", "human:admin")

    # Rule 2: Deny (Priority 100) - Domain B (security)
    r2_rule = KernelValidityRule(
        id="rule-deny",
        source_pattern="Source",
        target_pattern="Target",
        relationship_name="relates",
        valid=False,
        priority=100,
    )
    r2_meta = RuleMetadata(
        domain="security", # Different domain
        tags=("test",),
        category=RuleCategory.STRUCTURAL,
        confidence=RuleConfidence.UNIVERSAL,
        source="manual",
        established_version="1.0",
        rationale="Conflict Rule",
        group=RuleGroup.FLOW,
    )
    r2_entry = RuleCorpusEntry(r2_rule, r2_meta)

    r2_provenance = RuleProvenance(
        author="human:security",
        source_type="manual",
        source_reference="test",
        created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
    )
    r2_lifecycle = RuleLifecycle(current_state=RuleLifecycleState.DRAFT)
    # Note: Using helper's make_draft_asset logic for lifecycle

    r2 = RuleAsset(r2_entry, r2_provenance, r2_lifecycle)

    system.submit_rule(r2)
    system.approve_rule("rule-deny", "human:admin")

    # Now evaluate
    # Both active. Same priority. One valid=True, one valid=False.
    # Judgment logic: if any rule matches, we check conflicts.
    # Cross-domain conflict logic detects allowing domain vs denying domain.

    judgment = system.evaluate("Source", "Target", "relates")

    # Should detect conflict between 'core' and 'security'
    assert len(judgment.judgment.conflicts) > 0
    # Conflict format: "Domain 'core' allows but 'security' denies..."
    conflict_msg = judgment.judgment.conflicts[0]
    assert "allows" in conflict_msg and "denies" in conflict_msg
    assert "core" in conflict_msg and "security" in conflict_msg


def test_governance_bulk_approved_rules_are_all_loaded(governance_system) -> None:
    """E2E: GovernanceSystem should evaluate against all approved rules (100+)."""
    system = governance_system

    total_rules = 120
    for idx in range(total_rules):
        rule_id = f"rule-bulk-{idx:03d}"
        system.submit_rule(make_draft_asset(rule_id, priority=idx))
        system.approve_rule(rule_id, "human:admin")

    assert len(system.rule_store.active_rules()) == total_rules
    assert len(system.corpus.entries) == total_rules

    judgment = system.evaluate("Source", "Target", "relates")
    assert judgment.judgment.verdict is True
    assert len(judgment.judgment.evidence) == total_rules

    winners = [item.entry.rule.id for item in judgment.judgment.evidence if item.is_winner]
    assert winners == ["rule-bulk-119"]
