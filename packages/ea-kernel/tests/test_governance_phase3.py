"""Phase 3 End-to-End Integration Tests — Governance (S1 + S5).

Module-level unit tests have been extracted to:
- test_rule_asset_store.py
- test_promotion_engine.py
- test_what_if_simulator.py

This file retains only the end-to-end integration tests.

References:
- governance_lifecycle.toml: S1 Authoring + S5 Evolution
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from ea_kernel.governance_types import (
    EvidenceSummaryItem,
    RuleAsset,
    RuleLifecycle,
    RuleLifecycleState,
    RuleProvenance,
)
from ea_kernel.types import (
    DecisionRecord,
    JudgmentReport,
    KernelValidityRule,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleGroup,
    RuleMetadata,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Temporary database path."""
    return tmp_path / "test_phase3.db"


def make_rule_entry(
    rule_id: str,
    domain: str = "kernel",
    priority: int = 100,
    valid: bool = True,
) -> RuleCorpusEntry:
    """Helper to create RuleCorpusEntry."""
    rule = KernelValidityRule(
        id=rule_id,
        source_pattern="Source",
        target_pattern="Target",
        relationship_name="relates",
        valid=valid,
        priority=priority,
    )
    meta = RuleMetadata(
        domain=domain,
        tags=(domain,),
        category=RuleCategory.STRUCTURAL,
        confidence=RuleConfidence.UNIVERSAL,
        source="test",
        established_version="1.0.0",
        rationale="Test",
        group=RuleGroup.FLOW,
    )
    return RuleCorpusEntry(rule=rule, metadata=meta)


def make_asset(
    rule_id: str,
    state: RuleLifecycleState = RuleLifecycleState.DRAFT,
    domain: str = "kernel",
    days_old: int = 0,
) -> RuleAsset:
    """Helper to create RuleAsset."""
    created = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_old)
    now = datetime.now(UTC).replace(tzinfo=None)

    provenance = RuleProvenance(
        author="human:tester",
        source_type="manual",
        source_reference="test",
        created_at=created.isoformat() + "Z",
        updated_at=now.isoformat() + "Z",
        version=1,
    )

    lifecycle = RuleLifecycle(
        current_state=state,
        state_history=(),
    )

    return RuleAsset(
        entry=make_rule_entry(rule_id, domain),
        provenance=provenance,
        lifecycle=lifecycle,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# End-to-End Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase3EndToEnd:
    """End-to-end tests for Phase 3 Governance."""

    def test_full_rule_lifecycle(self, db_path: Path) -> None:
        """Test complete rule lifecycle: Draft -> Review -> Approved -> Deprecated."""
        from ea_kernel.rule_asset_store import SQLiteRuleAssetStore

        store = SQLiteRuleAssetStore(db_path)

        # Create draft rule
        asset = make_asset("rule-lifecycle", days_old=0)
        store.create(asset)

        # Verify initial state
        rule = store.get("rule-lifecycle")
        assert rule is not None
        assert rule.lifecycle.current_state == RuleLifecycleState.DRAFT

        # Submit for review
        store.transition("rule-lifecycle", RuleLifecycleState.REVIEW, "human:author")
        rule = store.get("rule-lifecycle")
        assert rule.lifecycle.current_state == RuleLifecycleState.REVIEW

        # Approve
        store.transition("rule-lifecycle", RuleLifecycleState.APPROVED, "human:approver")
        rule = store.get("rule-lifecycle")
        assert rule.lifecycle.current_state == RuleLifecycleState.APPROVED
        assert rule.is_active

        # Deprecate
        store.transition("rule-lifecycle", RuleLifecycleState.DEPRECATED, "human:admin")
        rule = store.get("rule-lifecycle")
        assert rule.lifecycle.current_state == RuleLifecycleState.DEPRECATED
        assert not rule.is_active

        # Verify history
        history = store.history("rule-lifecycle")
        assert len(history) >= 1
        assert history[-1].lifecycle.current_state == RuleLifecycleState.DEPRECATED
        assert len(history[-1].lifecycle.state_history) == 3

    def test_promotion_workflow(self, db_path: Path) -> None:
        """Test complete promotion workflow with analysis and proposal."""
        from ea_kernel.evidence_analyzer import AnalysisReport, RuleEffectiveness
        from ea_kernel.promotion_engine import (
            PromotionEngine,
            ProposalType,
        )
        from ea_kernel.rule_asset_store import SQLiteRuleAssetStore

        # Setup stores
        asset_store = SQLiteRuleAssetStore(db_path)

        # Create a rule eligible for promotion
        asset = make_asset("rule-promote-test", days_old=14)
        asset_store.create(asset)
        asset_store.transition(
            "rule-promote-test",
            RuleLifecycleState.REVIEW,
            "human:author",
        )

        # Create effectiveness data
        eff = RuleEffectiveness(
            rule_id="rule-promote-test",
            domain="kernel",
            total_evaluations=100,
            match_count=90,
            win_count=85,
            override_count=2,
            shadow_count=5,
            first_eval_at="2026-01-01T00:00:00Z",
            last_eval_at="2026-02-01T00:00:00Z",
        )

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        report = AnalysisReport(
            report_id="report-test",
            corpus_version_id="v1",
            created_at=now,
            rule_effectiveness=(eff,),
        )

        # Use promotion engine
        engine = PromotionEngine(asset_store)

        # Identify candidates
        candidates = engine.identify_promotion_candidates(report)
        assert len(candidates) >= 1

        candidate = candidates[0]
        assert candidate.score > 50  # Good score

        # Create proposal
        proposal = engine.create_proposal(
            ProposalType.PROMOTE,
            candidate.rule_id,
            "human:analyst",
            "High win rate and low override rate",
            report.report_id,
        )

        # Approve and apply
        engine.vote(proposal.proposal_id, "human:reviewer", True)
        engine.approve_proposal(proposal.proposal_id, "human:admin")
        engine.apply_proposal(proposal.proposal_id, "human:admin")

        # Verify promotion
        rule = asset_store.get("rule-promote-test")
        assert rule.lifecycle.current_state == RuleLifecycleState.APPROVED

    def test_impact_simulation_before_deprecation(self, db_path: Path) -> None:
        """Test what-if simulation before deprecating a rule."""
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.what_if_simulator import WhatIfSimulator

        store = SQLiteDecisionStore(db_path)

        # Create decision history that uses a specific rule
        for i in range(20):
            judgment = JudgmentReport(
                verdict=True,
                evidence=(),
                confidence=RuleConfidence.UNIVERSAL,
                domains=("kernel",),
                conflicts=(),
            )
            record = DecisionRecord(
                id=f"dec-sim-{i:03d}",
                timestamp=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
                actor="ai:validator",
                decision_type="validate",
                subject_triple=("Entity", f"Item-{i}", "links"),
                judgment=judgment,
            )
            # Half use rule-alpha, half use rule-beta
            if i < 10:
                evidence_summary = (
                    EvidenceSummaryItem(
                        rule_id="rule-alpha",
                        domain="kernel",
                        matched=True,
                        is_winner=True,
                    ),
                )
            else:
                evidence_summary = (
                    EvidenceSummaryItem(
                        rule_id="rule-beta",
                        domain="kernel",
                        matched=True,
                        is_winner=True,
                    ),
                )
            store.store(record, evidence_summary=evidence_summary)

        # Simulate removing rule-alpha
        simulator = WhatIfSimulator(store)
        result = simulator.simulate_rule_removal("rule-alpha")

        # Should show analysis was performed
        assert result.total_decisions_analyzed == 20
        assert result.simulation_id.startswith("sim-")
        assert result.impact_level is not None

        # Removing rule-beta should also produce a valid result
        result2 = simulator.simulate_rule_removal("rule-beta")
        assert result2.total_decisions_analyzed == 20
