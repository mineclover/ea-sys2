"""Phase 6: Integration Demo of Governance Lifecycle."""

from __future__ import annotations

import shutil
from pathlib import Path
from datetime import UTC, datetime

from ea_kernel.governance import GovernanceSystem
from ea_kernel.types import (
    KernelEntity, 
    KernelSchema, 
    KernelValidityRule, 
    Layer,
    RuleCategory, 
    RuleConfidence, 
    RuleCorpusEntry, 
    RuleGroup, 
    RuleMetadata
)
from ea_kernel.governance_types import (
    RuleAsset, 
    RuleLifecycle, 
    RuleLifecycleState,
    RuleProvenance
)

def make_draft_asset(rule_id: str) -> RuleAsset:
    """Create a DRAFT rule asset."""
    rule = KernelValidityRule(
        id=rule_id,
        source_pattern="Source",
        target_pattern="Target",
        relationship_name="relates",
        valid=True,
        priority=100,
    )
    
    meta = RuleMetadata(
        domain="core",
        tags=("demo",),
        category=RuleCategory.STRUCTURAL,
        confidence=RuleConfidence.UNIVERSAL,
        source="manual",
        established_version="1.0",
        rationale="Demo Rule",
        group=RuleGroup.FLOW,
    )
    
    entry = RuleCorpusEntry(rule, meta)
    
    provenance = RuleProvenance(
        author="human:alice",
        source_type="manual",
        source_reference="demo_script",
        created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
    )
    
    lifecycle = RuleLifecycle(current_state=RuleLifecycleState.DRAFT)
    
    return RuleAsset(entry, provenance, lifecycle)

def main() -> None:
    # Setup data directory
    data_dir = Path("./data/governance_demo")
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)
    
    # Initialize Schema (Kernel Base)
    schema = KernelSchema(
        attributes=(),
        entities=(
            KernelEntity(name="Source", layer=Layer.L1),
            KernelEntity(name="Target", layer=Layer.L1),
        ),
        relations=(),
        validity_rules=(),  # Starts empty
    )
    
    print("--- Initialize Governance System ---")
    system = GovernanceSystem(data_dir, schema)
    
    # 1. Authoring (S1)
    print("\n--- S1: Authoring ---")
    draft_rule = make_draft_asset("rule-001")
    system.submit_rule(draft_rule)
    print(f"Submitted rule: {draft_rule.id} (State: {draft_rule.lifecycle.current_state.value})")
    
    # 2. Review & Approve (S5)
    print("\n--- S5: Review & Approval ---")
    # Transition Draft -> Review -> Approved
    # GovernanceFacade.approve_rule handles transition logic internally for demo
    approved_rule = system.approve_rule("rule-001", "human:bob") 
    print(f"Approved rule: {approved_rule.id} (State: {approved_rule.lifecycle.current_state.value})")
    
    # Check if active in corpus
    verdict = system.evaluate("Source", "Target", "relates")
    print(f"Evaluate newly active rule: Verdict={verdict.judgment.verdict}")
    
    # 3. Judgment Recording (S2/S3)
    print("\n--- S2/S3: Judgment Recording ---")
    # Simulate usage
    for i in range(10):
        # Different contexts to simulate varied usage
        # Here just simple repetitive usage
        system.evaluate("Source", "Target", "relates")
    
    print("Recorded 10 judgments.")
    
    # 4. Analysis (S4)
    print("\n--- S4: Analysis ---")
    report = system.analyze()
    print(f"Analysis Report ID: {report.report_id}")
    print(f"Total Decisions Analyzed: {report.total_decisions_analyzed}")
    if report.rule_effectiveness:
        eff = report.rule_effectiveness[0]
        print(f"Rule {eff.rule_id} Effectiveness: Grade={eff.grade.value}, WinRate={eff.win_rate:.2f}")
    
    # 5. Automation (S5 Auto-Promotion)
    print("\n--- S5: Automation ---")
    # Trigger auto-promotion logic (mocked simulation)
    system.run_automation()
    
    # Check notifications
    if system.notification.sent:
        print(f"Notifications sent: {len(system.notification.sent)}")
        for n in system.notification.sent:
            print(f" - [{n.level.upper()}] To: {n.recipient} | Subject: {n.subject}")
    else:
        print("No notifications sent (expected if no promotion candidates found or conditions not met).")

    print("\n--- Demo Complete ---")

if __name__ == "__main__":
    main()
