"""Tests for impact_evaluator — S6 Propagation impact evaluation.

Extracted from test_governance_phase4.py for module-level focus.

Tests:
- RuleChangeSet properties
- ImpactEvaluator evaluation with various change scenarios
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from ea_kernel.governance_types import (
    EvidenceSummaryItem,
    StoredDecisionRecord,
)
from ea_kernel.types import (
    DecisionRecord,
    JudgmentReport,
    RuleConfidence,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Temporary database path."""
    return tmp_path / "test_impact_evaluator.db"


def make_stored_records(
    store,
    count: int,
    rule_ids: tuple[str, ...],
    verdict: bool = True,
) -> list[StoredDecisionRecord]:
    """Helper to populate decision store with records."""
    stored = []
    for i in range(count):
        judgment = JudgmentReport(
            verdict=verdict,
            evidence=(),
            confidence=RuleConfidence.UNIVERSAL,
            domains=("kernel",),
            conflicts=(),
        )
        record = DecisionRecord(
            id=f"dec-{i:03d}",
            timestamp=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            actor="ai:validator",
            decision_type="validate",
            subject_triple=("Source", f"Target-{i}", "relates"),
            judgment=judgment,
        )
        # Assign rules in round-robin
        rule_id = rule_ids[i % len(rule_ids)]
        evidence_summary = (
            EvidenceSummaryItem(
                rule_id=rule_id,
                domain="kernel",
                matched=True,
                is_winner=True,
            ),
        )
        s = store.store(record, evidence_summary=evidence_summary)
        stored.append(s)
    return stored


def evaluator_eval(store, cs):
    """Helper to create evaluator and evaluate."""
    from ea_kernel.impact_evaluator import ImpactEvaluator
    evaluator = ImpactEvaluator(store)
    return evaluator.evaluate(cs)


# ═══════════════════════════════════════════════════════════════════════════════
# RuleChangeSet Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuleChangeSet:
    """Tests for RuleChangeSet."""

    def test_empty_changeset(self) -> None:
        from ea_kernel.impact_evaluator import RuleChangeSet

        cs = RuleChangeSet(
            changeset_id="cs-001",
            from_version="v1",
            to_version="v2",
            created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            changes=(),
        )
        assert cs.is_empty
        assert len(cs.added_rules) == 0
        assert len(cs.removed_rules) == 0

    def test_changeset_properties(self) -> None:
        from ea_kernel.impact_evaluator import (
            RuleChange,
            RuleChangeAction,
            RuleChangeSet,
        )

        changes = (
            RuleChange(rule_id="r1", action=RuleChangeAction.ADDED),
            RuleChange(rule_id="r2", action=RuleChangeAction.REMOVED),
            RuleChange(rule_id="r3", action=RuleChangeAction.MODIFIED),
            RuleChange(rule_id="r4", action=RuleChangeAction.STATE_CHANGED),
        )

        cs = RuleChangeSet(
            changeset_id="cs-002",
            from_version="v1",
            to_version="v2",
            created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            changes=changes,
        )

        assert not cs.is_empty
        assert len(cs.added_rules) == 1
        assert len(cs.removed_rules) == 1
        assert len(cs.modified_rules) == 1
        assert len(cs.state_changes) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# ImpactEvaluator Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestImpactEvaluator:
    """Tests for ImpactEvaluator."""

    def test_empty_changeset_evaluation(self, db_path: Path) -> None:
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.impact_evaluator import ImpactEvaluator, RuleChangeSet

        store = SQLiteDecisionStore(db_path)
        evaluator = ImpactEvaluator(store)

        cs = RuleChangeSet(
            changeset_id="cs-empty",
            from_version="v1",
            to_version="v2",
            created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            changes=(),
        )

        report = evaluator.evaluate(cs)
        assert report.report_id.startswith("impact-")
        assert report.total_decisions_scanned == 0
        assert report.recommendation == "No changes to evaluate."

    def test_rule_removal_impact(self, db_path: Path) -> None:
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.impact_evaluator import (
            ImpactSeverity,
            RuleChange,
            RuleChangeAction,
            RuleChangeSet,
        )

        store = SQLiteDecisionStore(db_path)

        # Populate with decisions using rule-alpha
        make_stored_records(store, 10, ("rule-alpha",))

        # Create changeset removing rule-alpha
        cs = RuleChangeSet(
            changeset_id="cs-remove",
            from_version="v1",
            to_version="v2",
            created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            changes=(
                RuleChange(
                    rule_id="rule-alpha",
                    action=RuleChangeAction.REMOVED,
                    description="Removing outdated rule",
                ),
            ),
        )

        report = evaluator_eval(store, cs)

        assert report.total_decisions_scanned == 10
        assert len(report.affected_decisions) > 0
        assert report.decisions_with_verdict_change > 0
        assert report.severity != ImpactSeverity.NONE

    def test_unrelated_change_no_impact(self, db_path: Path) -> None:
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.impact_evaluator import (
            ImpactEvaluator,
            ImpactSeverity,
            RuleChange,
            RuleChangeAction,
            RuleChangeSet,
        )

        store = SQLiteDecisionStore(db_path)

        # Populate with decisions using rule-alpha
        make_stored_records(store, 10, ("rule-alpha",))

        # Change unrelated rule
        cs = RuleChangeSet(
            changeset_id="cs-unrelated",
            from_version="v1",
            to_version="v2",
            created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            changes=(
                RuleChange(
                    rule_id="rule-gamma",
                    action=RuleChangeAction.REMOVED,
                ),
            ),
        )

        evaluator = ImpactEvaluator(store)
        report = evaluator.evaluate(cs)

        assert report.total_decisions_scanned == 10
        assert len(report.affected_decisions) == 0
        assert report.severity == ImpactSeverity.NONE
        assert report.safe_to_apply is True

    def test_impact_report_properties(self, db_path: Path) -> None:
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.impact_evaluator import (
            ImpactEvaluator,
            RuleChange,
            RuleChangeAction,
            RuleChangeSet,
        )

        store = SQLiteDecisionStore(db_path)

        # Create mixed decisions
        make_stored_records(store, 20, ("rule-a", "rule-b"))

        # Remove rule-a
        cs = RuleChangeSet(
            changeset_id="cs-mixed",
            from_version="v1",
            to_version="v2",
            created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            changes=(
                RuleChange(rule_id="rule-a", action=RuleChangeAction.REMOVED),
            ),
        )

        evaluator = ImpactEvaluator(store)
        report = evaluator.evaluate(cs)

        assert report.impact_rate >= 0.0
        assert len(report.affected_domains) >= 0
        assert report.unique_triples_affected >= 0
