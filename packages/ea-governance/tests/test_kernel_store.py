from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ea_governance.facade import GovernanceContainer, KernelSchema
from ea_kernel.governance_types import RuleAsset, RuleLifecycle, RuleLifecycleState, RuleProvenance
from ea_kernel.types import (
    KernelEntity,
    KernelValidityRule,
    Layer,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleGroup,
    RuleMetadata,
)


def _schema() -> KernelSchema:
    return KernelSchema(
        attributes=(),
        entities=(
            KernelEntity(name="Source", layer=Layer.L1),
            KernelEntity(name="Target", layer=Layer.L1),
        ),
        relations=(),
        validity_rules=(),
    )


def _draft_asset(rule_id: str) -> RuleAsset:
    rule = KernelValidityRule(
        id=rule_id,
        source_pattern="Source",
        target_pattern="Target",
        relationship_name="relates",
        valid=True,
        priority=100,
    )
    metadata = RuleMetadata(
        domain="kernel",
        tags=("test",),
        category=RuleCategory.STRUCTURAL,
        confidence=RuleConfidence.UNIVERSAL,
        source="unit-test",
        established_version="1.0.0",
        rationale="governance refactor test",
        group=RuleGroup.FLOW,
    )
    entry = RuleCorpusEntry(rule=rule, metadata=metadata)
    provenance = RuleProvenance(
        author="human:tester",
        source_type="manual",
        source_reference="tests/test_kernel_store.py",
        created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
    )
    lifecycle = RuleLifecycle(current_state=RuleLifecycleState.DRAFT)
    return RuleAsset(entry=entry, provenance=provenance, lifecycle=lifecycle)


def test_governance_container_kernel_lifecycle_and_snapshots(tmp_path: Path):
    container = GovernanceContainer(tmp_path, _schema())

    submitted_result = container.submit_kernel_rule(
        _draft_asset("rule:governance:kernel"),
        actor="architect",
        return_transaction=True,
    )
    submitted = submitted_result["rule"]
    submit_tx = submitted_result["transaction_id"]
    assert submitted.id == "rule:governance:kernel"
    assert submitted.lifecycle.current_state == RuleLifecycleState.DRAFT

    approved_result = container.approve_kernel_rule(
        submitted.id,
        actor="architect",
        return_transaction=True,
    )
    approved = approved_result["rule"]
    approve_tx = approved_result["transaction_id"]
    assert approved.lifecycle.current_state == RuleLifecycleState.APPROVED

    judged_result = container.evaluate_kernel(
        "Source",
        "Target",
        "relates",
        actor="architect",
        return_transaction=True,
    )
    judgment = judged_result["judgment"]
    decision_id = judged_result["decision_id"]
    judgment_tx = judged_result["transaction_id"]
    assert judgment.judgment.verdict is True

    assert str(container.get_transaction_status(submit_tx)["status"]) == "committed"
    assert str(container.get_transaction_status(approve_tx)["status"]) == "committed"
    assert str(container.get_transaction_status(judgment_tx)["status"]) == "committed"

    approve_events = container.get_transaction_events(approve_tx)
    assert any(event["event_type"] == "kernel_rule_approved" for event in approve_events)

    rule_snapshot = container.get_kernel_rule_snapshot(submitted.id)
    assert rule_snapshot is not None
    assert rule_snapshot["kind"] == "kernel_rule_asset"
    assert rule_snapshot["lifecycle"]["state"] == "approved"

    rule_snapshots = container.list_kernel_rule_snapshots()
    assert len(rule_snapshots) == 1
    assert rule_snapshots[0]["payload"]["rule_id"] == submitted.id

    judgment_snapshot = container.get_kernel_judgment_snapshot(decision_id)
    assert judgment_snapshot is not None
    assert judgment_snapshot["kind"] == "kernel_judgment"
    assert judgment_snapshot["judgment"]["verdict"] is True

    approved_rules = container.list_kernel_rules("approved")
    assert len(approved_rules) == 1
    assert approved_rules[0].id == submitted.id


def test_governance_container_kernel_snapshot_projection(tmp_path: Path):
    container = GovernanceContainer(tmp_path, _schema())
    container.submit_kernel_rule(_draft_asset("rule:governance:snapshot"), actor="architect")
    container.approve_kernel_rule("rule:governance:snapshot", actor="architect")

    snapshot_result = container.create_kernel_snapshot(
        "kernel-reference",
        "kernel version projection",
        actor="architect",
        return_transaction=True,
    )
    version = snapshot_result["version"]
    tx_id = snapshot_result["transaction_id"]
    assert version.corpus_name == "kernel-reference"
    assert version.rule_count == 1

    assert str(container.get_transaction_status(tx_id)["status"]) == "committed"

    versions = container.list_kernel_versions("kernel-reference")
    assert len(versions) == 1
    assert versions[0].version_id == version.version_id

    version_snapshot = container.get_kernel_corpus_version_snapshot(version.version_id)
    assert version_snapshot is not None
    assert version_snapshot["kind"] == "kernel_corpus_version"
    assert version_snapshot["version_id"] == version.version_id

    version_snapshots = container.list_kernel_corpus_version_snapshots()
    assert len(version_snapshots) == 1
