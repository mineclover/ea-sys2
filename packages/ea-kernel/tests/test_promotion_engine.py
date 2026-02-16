"""Tests for promotion_engine — S5 Evolution promotion workflow.

Extracted from test_governance_phase3.py for module-level focus.

Tests:
- PromotionCriteria evaluation
- RuleChangeProposal voting and resolution
- PromotionEngine candidate identification and proposal lifecycle
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from ea_kernel.governance_types import (
    RuleAsset,
    RuleLifecycle,
    RuleLifecycleState,
    RuleProvenance,
)
from ea_kernel.types import (
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
    return tmp_path / "test_promotion_engine.db"


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
# PromotionCriteria Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPromotionCriteria:
    """Tests for PromotionCriteria."""

    def test_meets_all_criteria(self) -> None:
        from ea_kernel.evidence_analyzer import RuleEffectiveness
        from ea_kernel.promotion_engine import PromotionCriteria

        criteria = PromotionCriteria()

        # Create effectiveness that meets all criteria
        eff = RuleEffectiveness(
            rule_id="rule-001",
            domain="kernel",
            total_evaluations=100,
            match_count=80,
            win_count=70,
            override_count=5,
            shadow_count=10,
            first_eval_at="2026-01-01T00:00:00Z",
            last_eval_at="2026-02-01T00:00:00Z",
        )

        # Old enough rule
        old_created = (datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)).isoformat() + "Z"

        meets, reasons = criteria.evaluate(eff, old_created)
        assert meets is True
        assert len(reasons) == 0

    def test_fails_min_evaluations(self) -> None:
        from ea_kernel.evidence_analyzer import RuleEffectiveness
        from ea_kernel.promotion_engine import PromotionCriteria

        criteria = PromotionCriteria(min_evaluations=100)

        eff = RuleEffectiveness(
            rule_id="rule-001",
            domain="kernel",
            total_evaluations=50,
            match_count=40,
            win_count=30,
            override_count=2,
            shadow_count=5,
            first_eval_at="2026-01-01T00:00:00Z",
            last_eval_at="2026-02-01T00:00:00Z",
        )

        old_created = (datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)).isoformat() + "Z"
        meets, reasons = criteria.evaluate(eff, old_created)

        assert meets is False
        assert any("Insufficient evaluations" in r for r in reasons)


# ═══════════════════════════════════════════════════════════════════════════════
# RuleChangeProposal Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuleChangeProposal:
    """Tests for RuleChangeProposal."""

    def test_create_and_vote(self) -> None:
        from ea_kernel.promotion_engine import (
            ProposalType,
            ProposalVote,
            RuleChangeProposal,
        )

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        proposal = RuleChangeProposal(
            proposal_id="proposal-001",
            proposal_type=ProposalType.PROMOTE,
            rule_id="rule-001",
            proposed_by="human:alice",
            proposed_at=now,
            rationale="Good performance",
            required_approvals=2,
        )

        assert proposal.approval_count == 0
        assert not proposal.can_be_approved

        # Add votes
        vote1 = ProposalVote(
            voter="human:bob",
            approve=True,
            timestamp=now,
        )
        proposal = proposal.with_vote(vote1)

        vote2 = ProposalVote(
            voter="human:carol",
            approve=True,
            timestamp=now,
        )
        proposal = proposal.with_vote(vote2)

        assert proposal.approval_count == 2
        assert proposal.can_be_approved

    def test_resolve_proposal(self) -> None:
        from ea_kernel.promotion_engine import (
            ProposalStatus,
            ProposalType,
            RuleChangeProposal,
        )

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        proposal = RuleChangeProposal(
            proposal_id="proposal-001",
            proposal_type=ProposalType.DEPRECATE,
            rule_id="rule-001",
            proposed_by="human:alice",
            proposed_at=now,
        )

        resolved = proposal.resolve(
            ProposalStatus.APPROVED,
            "human:admin",
            "Approved after review",
        )

        assert resolved.status == ProposalStatus.APPROVED
        assert resolved.is_resolved
        assert resolved.resolved_by == "human:admin"


# ═══════════════════════════════════════════════════════════════════════════════
# PromotionEngine Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPromotionEngine:
    """Tests for PromotionEngine."""

    def test_identify_promotion_candidates(self, db_path: Path) -> None:
        from ea_kernel.evidence_analyzer import (
            AnalysisReport,
            RuleEffectiveness,
        )
        from ea_kernel.promotion_engine import PromotionEngine
        from ea_kernel.rule_asset_store import SQLiteRuleAssetStore

        # Setup stores
        asset_store = SQLiteRuleAssetStore(db_path)

        # Create a rule in REVIEW state (manually since we need REVIEW)
        asset = make_asset("rule-candidate-001", days_old=30)
        asset_store.create(asset)
        asset_store.transition(
            asset.id,
            RuleLifecycleState.REVIEW,
            "human:reviewer",
        )

        # Create mock analysis report
        eff = RuleEffectiveness(
            rule_id="rule-candidate-001",
            domain="kernel",
            total_evaluations=100,
            match_count=80,
            win_count=70,
            override_count=3,
            shadow_count=5,
            first_eval_at="2026-01-01T00:00:00Z",
            last_eval_at="2026-02-01T00:00:00Z",
        )

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        report = AnalysisReport(
            report_id="report-001",
            corpus_version_id="v1",
            created_at=now,
            rule_effectiveness=(eff,),
        )

        # Run promotion engine
        engine = PromotionEngine(asset_store)
        candidates = engine.identify_promotion_candidates(report)

        assert len(candidates) >= 1
        assert candidates[0].rule_id == "rule-candidate-001"

    def test_create_and_apply_proposal(self, db_path: Path) -> None:
        from ea_kernel.promotion_engine import (
            PromotionEngine,
            ProposalStatus,
            ProposalType,
        )
        from ea_kernel.rule_asset_store import SQLiteRuleAssetStore

        asset_store = SQLiteRuleAssetStore(db_path)

        # Create a rule and move to REVIEW
        asset = make_asset("rule-to-promote", days_old=30)
        asset_store.create(asset)
        asset_store.transition(
            asset.id,
            RuleLifecycleState.REVIEW,
            "human:reviewer",
        )

        # Create proposal
        engine = PromotionEngine(asset_store)
        proposal = engine.create_proposal(
            ProposalType.PROMOTE,
            "rule-to-promote",
            "human:proposer",
            "Rule has proven effective",
        )

        assert proposal.status == ProposalStatus.PENDING

        # Vote and approve
        engine.vote(proposal.proposal_id, "human:voter1", True)
        approved = engine.approve_proposal(
            proposal.proposal_id,
            "human:admin",
        )

        assert approved.status == ProposalStatus.APPROVED

        # Apply
        applied = engine.apply_proposal(proposal.proposal_id, "human:admin")

        assert applied.status == ProposalStatus.APPLIED

        # Verify rule is now APPROVED
        rule = asset_store.get("rule-to-promote")
        assert rule is not None
        assert rule.lifecycle.current_state == RuleLifecycleState.APPROVED
