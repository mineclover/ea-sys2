"""Integration tests for Model I/O (Export/Import)."""

import json
from datetime import UTC, datetime

from ea_kernel.governance import GovernanceSystem
from ea_kernel.governance_types import RuleAsset, RuleLifecycle, RuleLifecycleState, RuleProvenance
from ea_kernel.model_io import ModelIOManager
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

def make_rule_asset(rule_id: str) -> RuleAsset:
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

def test_export_import_flow(tmp_path):
    """Test full export -> import cycle."""

    # 1. Setup Source System
    src_dir = tmp_path / "source"
    schema = make_simple_schema()
    src_system = GovernanceSystem(src_dir, schema)

    # Create & Approve a rule
    rule_id = "rule-export-01"
    asset = make_rule_asset(rule_id)
    # Note: submit_rule usually sets DRAFT. We'll manually insert APPROVED for this test
    # or use approve_rule workflow.
    src_system.submit_rule(asset)
    src_system.approve_rule(rule_id, "admin")

    # Check it's active
    assert len(src_system.rule_store.active_rules()) == 1

    # 2. Export
    io_manager = ModelIOManager(src_system)
    data = io_manager.export_model()

    # Verify export data structure
    assert data["meta"]["rules_count"] == 1
    exported_rule = data["rules"][0]
    assert exported_rule["entry"]["rule"]["id"] == rule_id
    assert exported_rule["lifecycle"]["current_state"] == "approved"

    # Save to file (simulate file transfer)
    export_file = tmp_path / "export.json"
    with open(export_file, "w") as f:
        json.dump(data, f, default=str) # handling datetime

    # 3. Setup Target System (Empty)
    tgt_dir = tmp_path / "target"
    tgt_system = GovernanceSystem(tgt_dir, schema)
    assert len(tgt_system.rule_store.active_rules()) == 0

    # 4. Import
    tgt_io = ModelIOManager(tgt_system)

    # Load form file
    with open(export_file) as f:
        import_data = json.load(f)

    report = tgt_io.import_model(import_data)

    # 5. Verify Import
    assert report["imported"] == 1
    assert len(tgt_system.rule_store.active_rules()) == 1
    imported_rule = tgt_system.rule_store.get(rule_id)
    assert imported_rule is not None
    assert imported_rule.id == rule_id
    # Note: Import logic might reset to Draft or keep Approved depending on implementation
    # Let's inspect what happens. The current simplified impl just store.create().
    # store.create usually preserves the state passed in the asset object.
    assert imported_rule.lifecycle.current_state == RuleLifecycleState.APPROVED
