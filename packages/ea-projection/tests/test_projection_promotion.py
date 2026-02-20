"""Tests for ProjectionPromotionEngine — S5 Evolution Promotion."""

from __future__ import annotations

import pytest

from ea_projection.projection_analyzer import (
    LevelCoverage,
    LevelCoverageGrade,
    ProjectionAnalysisReport,
)
from ea_projection.projection_promotion import (
    PolicyChangeProposal,
    PolicyDeprecationCandidate,
    PolicyPromotionCandidate,
    PolicyPromotionCriteria,
    PolicyPromotionEngine,
    PolicyProposalStatus,
    PolicyProposalType,
    PolicyProposalVote,
)


# ── Factory ─────────────────────────────────────────────────────────────

def _make_report(
    coverages: tuple[LevelCoverage, ...] = (),
) -> ProjectionAnalysisReport:
    return ProjectionAnalysisReport(
        report_id="test-report",
        created_at="2025-01-15T10:00:00Z",
        total_projections_analyzed=sum(c.total_projections for c in coverages),
        level_coverage=coverages,
    )


# ── PolicyPromotionCriteria Tests ───────────────────────────────────────

class TestPolicyPromotionCriteria:
    def test_evaluate_passes(self):
        criteria = PolicyPromotionCriteria()
        cov = LevelCoverage(
            level="l0",
            total_projections=15,
            projected_count=12,
            stale_count=1,
            avg_node_count=10.0,
        )
        meets, reasons = criteria.evaluate(cov)
        assert meets is True
        assert len(reasons) == 0

    def test_evaluate_insufficient_projections(self):
        criteria = PolicyPromotionCriteria(min_projections=10)
        cov = LevelCoverage(level="l0", total_projections=3)
        meets, reasons = criteria.evaluate(cov)
        assert meets is False
        assert any("Insufficient" in r for r in reasons)

    def test_evaluate_low_freshness(self):
        criteria = PolicyPromotionCriteria(min_freshness_rate=0.5)
        cov = LevelCoverage(
            level="l0",
            total_projections=10,
            projected_count=2,
            avg_node_count=5.0,
        )
        meets, reasons = criteria.evaluate(cov)
        assert meets is False
        assert any("Freshness" in r for r in reasons)

    def test_evaluate_high_stale_rate(self):
        criteria = PolicyPromotionCriteria(max_stale_rate=0.2)
        cov = LevelCoverage(
            level="l0",
            total_projections=10,
            projected_count=5,
            stale_count=5,
            avg_node_count=5.0,
        )
        meets, reasons = criteria.evaluate(cov)
        assert meets is False
        assert any("Stale" in r for r in reasons)


# ── PolicyPromotionEngine Tests ─────────────────────────────────────────

class TestPolicyPromotionEngine:
    def test_identify_promotion_candidates(self):
        engine = PolicyPromotionEngine()
        report = _make_report(coverages=(
            LevelCoverage(
                level="l0", total_projections=15,
                projected_count=12, stale_count=1, avg_node_count=10.0,
            ),
            LevelCoverage(
                level="l1", total_projections=3,
                projected_count=2, stale_count=1, avg_node_count=5.0,
            ),
        ))

        candidates = engine.identify_promotion_candidates(report)
        assert len(candidates) == 2

        # Sorted by score desc
        assert candidates[0].score >= candidates[1].score

        # L0 should meet criteria
        l0 = next(c for c in candidates if c.level == "l0")
        assert l0.meets_criteria is True

    def test_identify_deprecation_candidates(self):
        engine = PolicyPromotionEngine()
        report = _make_report(coverages=(
            LevelCoverage(
                level="l0", total_projections=10,
                projected_count=9, stale_count=1,
            ),
            LevelCoverage(
                level="l3", total_projections=2,
                projected_count=0, stale_count=2,
            ),
        ))

        candidates = engine.identify_deprecation_candidates(report)
        assert len(candidates) >= 1

        # L3 should be flagged (SPARSE with high stale rate)
        l3 = next(
            (c for c in candidates if c.level == "l3"), None,
        )
        assert l3 is not None

    def test_deprecation_high_stale_rate(self):
        engine = PolicyPromotionEngine()
        report = _make_report(coverages=(
            LevelCoverage(
                level="l0", total_projections=10,
                projected_count=3, stale_count=7,
            ),
        ))

        candidates = engine.identify_deprecation_candidates(report)
        assert len(candidates) == 1
        assert any("stale" in r.lower() for r in candidates[0].deprecation_reasons)


# ── Proposal Workflow Tests ─────────────────────────────────────────────

class TestProposalWorkflow:
    def test_create_proposal(self):
        engine = PolicyPromotionEngine()
        proposal = engine.create_proposal(
            proposal_type=PolicyProposalType.PROMOTE,
            level="l0",
            proposed_by="architect",
            rationale="Well covered",
        )

        assert proposal.proposal_id.startswith("proposal-")
        assert proposal.status == PolicyProposalStatus.PENDING
        assert proposal.level == "l0"

    def test_vote_on_proposal(self):
        engine = PolicyPromotionEngine()
        proposal = engine.create_proposal(
            proposal_type=PolicyProposalType.PROMOTE,
            level="l0",
            proposed_by="architect",
            rationale="Promote",
        )

        updated = engine.vote(
            proposal.proposal_id, "reviewer", approve=True,
        )
        assert updated.approval_count == 1
        assert updated.can_be_approved is True

    def test_approve_proposal(self):
        engine = PolicyPromotionEngine()
        proposal = engine.create_proposal(
            proposal_type=PolicyProposalType.PROMOTE,
            level="l0",
            proposed_by="architect",
            rationale="Promote",
        )

        approved = engine.approve_proposal(
            proposal.proposal_id, "lead",
        )
        assert approved.status == PolicyProposalStatus.APPROVED
        assert approved.resolved_by == "lead"

    def test_reject_proposal(self):
        engine = PolicyPromotionEngine()
        proposal = engine.create_proposal(
            proposal_type=PolicyProposalType.DEPRECATE,
            level="l3",
            proposed_by="architect",
            rationale="Sparse",
        )

        rejected = engine.reject_proposal(
            proposal.proposal_id, "lead", "Not yet",
        )
        assert rejected.status == PolicyProposalStatus.REJECTED

    def test_apply_proposal(self):
        engine = PolicyPromotionEngine()
        proposal = engine.create_proposal(
            proposal_type=PolicyProposalType.PROMOTE,
            level="l0",
            proposed_by="architect",
            rationale="Promote",
        )
        engine.approve_proposal(proposal.proposal_id, "lead")

        applied = engine.apply_proposal(
            proposal.proposal_id, "operator",
        )
        assert applied.status == PolicyProposalStatus.APPLIED

    def test_apply_unapproved_raises(self):
        engine = PolicyPromotionEngine()
        proposal = engine.create_proposal(
            proposal_type=PolicyProposalType.PROMOTE,
            level="l0",
            proposed_by="architect",
            rationale="Promote",
        )

        with pytest.raises(ValueError, match="APPROVED"):
            engine.apply_proposal(proposal.proposal_id, "operator")

    def test_vote_on_resolved_raises(self):
        engine = PolicyPromotionEngine()
        proposal = engine.create_proposal(
            proposal_type=PolicyProposalType.PROMOTE,
            level="l0",
            proposed_by="architect",
            rationale="Promote",
        )
        engine.approve_proposal(proposal.proposal_id, "lead")

        with pytest.raises(ValueError, match="already resolved"):
            engine.vote(proposal.proposal_id, "late-voter", approve=True)

    def test_list_proposals_by_status(self):
        engine = PolicyPromotionEngine()
        p1 = engine.create_proposal(
            proposal_type=PolicyProposalType.PROMOTE,
            level="l0", proposed_by="a", rationale="R1",
        )
        engine.create_proposal(
            proposal_type=PolicyProposalType.DEPRECATE,
            level="l3", proposed_by="b", rationale="R2",
        )
        engine.approve_proposal(p1.proposal_id, "lead")

        pending = engine.list_proposals(PolicyProposalStatus.PENDING)
        assert len(pending) == 1

        approved = engine.list_proposals(PolicyProposalStatus.APPROVED)
        assert len(approved) == 1

    def test_get_proposal(self):
        engine = PolicyPromotionEngine()
        proposal = engine.create_proposal(
            proposal_type=PolicyProposalType.PROMOTE,
            level="l0", proposed_by="a", rationale="R",
        )

        retrieved = engine.get_proposal(proposal.proposal_id)
        assert retrieved is not None
        assert retrieved.proposal_id == proposal.proposal_id

    def test_get_nonexistent_proposal(self):
        engine = PolicyPromotionEngine()
        assert engine.get_proposal("nonexistent") is None


# ── PolicyChangeProposal Tests ──────────────────────────────────────────

class TestPolicyChangeProposal:
    def test_approval_count(self):
        proposal = PolicyChangeProposal(
            proposal_id="p-1",
            proposal_type=PolicyProposalType.PROMOTE,
            level="l0",
            proposed_by="a",
            proposed_at="2025-01-15T10:00:00Z",
            votes=(
                PolicyProposalVote("v1", True, "2025-01-15T10:00:00Z"),
                PolicyProposalVote("v2", False, "2025-01-15T10:00:00Z"),
                PolicyProposalVote("v3", True, "2025-01-15T10:00:00Z"),
            ),
        )
        assert proposal.approval_count == 2
        assert proposal.rejection_count == 1

    def test_can_be_approved(self):
        proposal = PolicyChangeProposal(
            proposal_id="p-1",
            proposal_type=PolicyProposalType.PROMOTE,
            level="l0",
            proposed_by="a",
            proposed_at="2025-01-15T10:00:00Z",
            required_approvals=2,
            votes=(
                PolicyProposalVote("v1", True, "2025-01-15T10:00:00Z"),
                PolicyProposalVote("v2", True, "2025-01-15T10:00:00Z"),
            ),
        )
        assert proposal.can_be_approved is True

    def test_is_resolved(self):
        pending = PolicyChangeProposal(
            proposal_id="p-1",
            proposal_type=PolicyProposalType.PROMOTE,
            level="l0",
            proposed_by="a",
            proposed_at="2025-01-15T10:00:00Z",
        )
        assert pending.is_resolved is False

        approved = PolicyChangeProposal(
            proposal_id="p-2",
            proposal_type=PolicyProposalType.PROMOTE,
            level="l0",
            proposed_by="a",
            proposed_at="2025-01-15T10:00:00Z",
            status=PolicyProposalStatus.APPROVED,
        )
        assert approved.is_resolved is True
