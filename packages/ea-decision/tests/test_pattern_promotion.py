"""Tests for PatternPromotionEngine — S5 Evolution."""

from __future__ import annotations

import pytest

from ea_decision.decision_analyzer import (
    DecisionAnalysisReport,
    PatternEffectiveness,
    PatternEffectivenessGrade,
)
from ea_decision.pattern_promotion import (
    DeprecationCandidate,
    PatternChangeProposal,
    PatternPromotionCriteria,
    PatternPromotionEngine,
    PatternProposalStatus,
    PatternProposalType,
    PatternProposalVote,
    PromotionCandidate,
)


# ── Factory ─────────────────────────────────────────────────────────────

def _make_effectiveness(
    pattern_name: str = "TradeOff",
    total_decisions: int = 30,
    accepted_count: int = 25,
    rejected_count: int = 5,
    deprecated_count: int = 0,
    avg_evaluation_score: float = 0.8,
) -> PatternEffectiveness:
    return PatternEffectiveness(
        pattern_name=pattern_name,
        total_decisions=total_decisions,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        deprecated_count=deprecated_count,
        avg_evaluation_score=avg_evaluation_score,
    )


def _make_report(
    effectiveness: tuple[PatternEffectiveness, ...] | None = None,
) -> DecisionAnalysisReport:
    if effectiveness is None:
        effectiveness = (
            _make_effectiveness("Good", 30, 25, 5, 0, 0.8),
            _make_effectiveness("Unused", 0, 0, 0, 0, 0.0),
            _make_effectiveness("Bad", 20, 3, 17, 0, 0.2),
        )
    return DecisionAnalysisReport(
        report_id="test-report",
        created_at="2025-01-01T00:00:00Z",
        total_decisions_analyzed=50,
        pattern_effectiveness=effectiveness,
    )


# ── PatternPromotionCriteria Tests ──────────────────────────────────────

class TestPatternPromotionCriteria:
    def test_evaluate_passes_all(self):
        criteria = PatternPromotionCriteria()
        eff = _make_effectiveness(total_decisions=30, accepted_count=25)
        meets, reasons = criteria.evaluate(eff)
        assert meets is True
        assert len(reasons) == 0

    def test_evaluate_insufficient_decisions(self):
        criteria = PatternPromotionCriteria(min_decisions=50)
        eff = _make_effectiveness(total_decisions=30)
        meets, reasons = criteria.evaluate(eff)
        assert meets is False
        assert any("Insufficient decisions" in r for r in reasons)

    def test_evaluate_low_acceptance_rate(self):
        criteria = PatternPromotionCriteria()
        eff = _make_effectiveness(total_decisions=30, accepted_count=5, rejected_count=25)
        meets, reasons = criteria.evaluate(eff)
        assert meets is False
        assert any("Acceptance rate" in r for r in reasons)

    def test_evaluate_high_revision_rate(self):
        criteria = PatternPromotionCriteria(max_revision_rate=0.1)
        eff = _make_effectiveness(
            total_decisions=30, accepted_count=20,
            deprecated_count=10,
        )
        meets, reasons = criteria.evaluate(eff)
        assert meets is False
        assert any("Revision rate" in r for r in reasons)

    def test_evaluate_low_score(self):
        criteria = PatternPromotionCriteria(min_avg_evaluation_score=0.7)
        eff = _make_effectiveness(avg_evaluation_score=0.3)
        meets, reasons = criteria.evaluate(eff)
        assert meets is False
        assert any("evaluation score" in r for r in reasons)

    def test_evaluate_age_check(self):
        criteria = PatternPromotionCriteria(min_age_days=30)
        eff = _make_effectiveness()
        # Recent creation
        meets, reasons = criteria.evaluate(eff, created_at="2099-01-01T00:00:00Z")
        assert meets is False
        assert any("too young" in r for r in reasons)


# ── PatternPromotionEngine Tests ────────────────────────────────────────

class TestPatternPromotionEngine:
    def test_identify_promotion_candidates(self):
        engine = PatternPromotionEngine()
        report = _make_report()

        candidates = engine.identify_promotion_candidates(report)
        assert len(candidates) == 3

        # Sorted by score descending
        assert candidates[0].pattern_name == "Good"
        assert candidates[0].meets_criteria is True

    def test_identify_deprecation_candidates(self):
        engine = PatternPromotionEngine()
        report = _make_report()

        candidates = engine.identify_deprecation_candidates(report)
        assert len(candidates) >= 1

        # Unused should be flagged
        unused = next(
            (c for c in candidates if c.pattern_name == "Unused"), None,
        )
        assert unused is not None
        assert unused.severity == "high"

    def test_create_proposal(self):
        engine = PatternPromotionEngine()
        proposal = engine.create_proposal(
            proposal_type=PatternProposalType.PROMOTE,
            pattern_name="TradeOff",
            proposed_by="analyst",
            rationale="High acceptance rate",
        )

        assert proposal.proposal_id.startswith("proposal-")
        assert proposal.status == PatternProposalStatus.PENDING
        assert proposal.pattern_name == "TradeOff"

    def test_vote_on_proposal(self):
        engine = PatternPromotionEngine()
        proposal = engine.create_proposal(
            PatternProposalType.PROMOTE, "P", "analyst", "reason",
        )

        updated = engine.vote(proposal.proposal_id, "reviewer", True, "LGTM")
        assert updated.approval_count == 1
        assert updated.rejection_count == 0
        assert len(updated.votes) == 1

    def test_approve_proposal(self):
        engine = PatternPromotionEngine()
        proposal = engine.create_proposal(
            PatternProposalType.PROMOTE, "P", "analyst", "reason",
        )

        approved = engine.approve_proposal(
            proposal.proposal_id, "admin", "Approved",
        )
        assert approved.status == PatternProposalStatus.APPROVED
        assert approved.resolved_by == "admin"

    def test_reject_proposal(self):
        engine = PatternPromotionEngine()
        proposal = engine.create_proposal(
            PatternProposalType.DEPRECATE, "P", "analyst", "reason",
        )

        rejected = engine.reject_proposal(
            proposal.proposal_id, "admin", "Not ready",
        )
        assert rejected.status == PatternProposalStatus.REJECTED

    def test_apply_proposal(self):
        engine = PatternPromotionEngine()
        proposal = engine.create_proposal(
            PatternProposalType.PROMOTE, "P", "analyst", "reason",
        )
        engine.approve_proposal(proposal.proposal_id, "admin")

        applied = engine.apply_proposal(proposal.proposal_id, "deployer")
        assert applied.status == PatternProposalStatus.APPLIED

    def test_apply_unapproved_raises(self):
        engine = PatternPromotionEngine()
        proposal = engine.create_proposal(
            PatternProposalType.PROMOTE, "P", "analyst", "reason",
        )

        with pytest.raises(ValueError, match="APPROVED"):
            engine.apply_proposal(proposal.proposal_id, "deployer")

    def test_vote_on_resolved_raises(self):
        engine = PatternPromotionEngine()
        proposal = engine.create_proposal(
            PatternProposalType.PROMOTE, "P", "analyst", "reason",
        )
        engine.approve_proposal(proposal.proposal_id, "admin")

        with pytest.raises(ValueError, match="already resolved"):
            engine.vote(proposal.proposal_id, "latecomer", True)

    def test_approve_resolved_raises(self):
        engine = PatternPromotionEngine()
        proposal = engine.create_proposal(
            PatternProposalType.PROMOTE, "P", "analyst", "reason",
        )
        engine.reject_proposal(proposal.proposal_id, "admin")

        with pytest.raises(ValueError, match="already resolved"):
            engine.approve_proposal(proposal.proposal_id, "admin")

    def test_get_proposal(self):
        engine = PatternPromotionEngine()
        proposal = engine.create_proposal(
            PatternProposalType.PROMOTE, "P", "analyst", "reason",
        )

        got = engine.get_proposal(proposal.proposal_id)
        assert got is not None
        assert got.pattern_name == "P"

        assert engine.get_proposal("nonexistent") is None

    def test_list_proposals(self):
        engine = PatternPromotionEngine()
        engine.create_proposal(
            PatternProposalType.PROMOTE, "A", "analyst", "reason",
        )
        p2 = engine.create_proposal(
            PatternProposalType.DEPRECATE, "B", "analyst", "reason",
        )
        engine.approve_proposal(p2.proposal_id, "admin")

        all_proposals = engine.list_proposals()
        assert len(all_proposals) == 2

        pending = engine.list_proposals(PatternProposalStatus.PENDING)
        assert len(pending) == 1

        approved = engine.list_proposals(PatternProposalStatus.APPROVED)
        assert len(approved) == 1

    def test_nonexistent_proposal_raises(self):
        engine = PatternPromotionEngine()
        with pytest.raises(ValueError, match="not found"):
            engine.vote("nonexistent", "voter", True)

    def test_proposal_can_be_approved(self):
        engine = PatternPromotionEngine()
        proposal = engine.create_proposal(
            PatternProposalType.PROMOTE, "P", "analyst", "reason",
            required_approvals=2,
        )
        assert proposal.can_be_approved is False

        engine.vote(proposal.proposal_id, "reviewer1", True)
        updated = engine.vote(proposal.proposal_id, "reviewer2", True)
        assert updated.can_be_approved is True
