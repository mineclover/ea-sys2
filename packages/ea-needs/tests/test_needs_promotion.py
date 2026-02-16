"""Tests for NeedPromotionEngine — S5 Evolution."""

from __future__ import annotations

import pytest

from ea_needs.needs_analyzer import (
    NeedsAnalysisReport,
    StakeholderCoverage,
    StakeholderCoverageGrade,
)
from ea_needs.needs_promotion import (
    NeedChangeProposal,
    NeedDeprecationCandidate,
    NeedPromotionCandidate,
    NeedPromotionCriteria,
    NeedPromotionEngine,
    NeedProposalStatus,
    NeedProposalType,
    NeedProposalVote,
)


# ── Factory ─────────────────────────────────────────────────────────────

def _make_coverage(
    stakeholder_id: str = "sh-cto",
    total_needs: int = 20,
    addressed_count: int = 15,
    withdrawn_count: int = 1,
    acknowledged_count: int = 2,
    expressed_count: int = 1,
    draft_count: int = 1,
    avg_justification_count: float = 2.0,
) -> StakeholderCoverage:
    return StakeholderCoverage(
        stakeholder_id=stakeholder_id,
        total_needs=total_needs,
        addressed_count=addressed_count,
        withdrawn_count=withdrawn_count,
        acknowledged_count=acknowledged_count,
        expressed_count=expressed_count,
        draft_count=draft_count,
        avg_justification_count=avg_justification_count,
    )


def _make_report(
    coverage: tuple[StakeholderCoverage, ...] | None = None,
) -> NeedsAnalysisReport:
    if coverage is None:
        coverage = (
            _make_coverage("sh-good", 20, 15, 1, 2, 1, 1, 2.5),
            _make_coverage("sh-unserved", 0, 0, 0, 0, 0, 0, 0.0),
            _make_coverage("sh-bad", 10, 1, 8, 0, 1, 0, 0.5),
        )
    return NeedsAnalysisReport(
        report_id="test-report",
        created_at="2025-01-01T00:00:00Z",
        total_needs_analyzed=30,
        stakeholder_coverage=coverage,
    )


# ── NeedPromotionCriteria Tests ────────────────────────────────────────

class TestNeedPromotionCriteria:
    def test_evaluate_passes_all(self):
        criteria = NeedPromotionCriteria()
        cov = _make_coverage(total_needs=20, addressed_count=15)
        meets, reasons = criteria.evaluate(cov)
        assert meets is True
        assert len(reasons) == 0

    def test_evaluate_insufficient_needs(self):
        criteria = NeedPromotionCriteria(min_needs=50)
        cov = _make_coverage(total_needs=20)
        meets, reasons = criteria.evaluate(cov)
        assert meets is False
        assert any("Insufficient needs" in r for r in reasons)

    def test_evaluate_low_addressed_rate(self):
        criteria = NeedPromotionCriteria()
        cov = _make_coverage(
            total_needs=20, addressed_count=2, withdrawn_count=15,
        )
        meets, reasons = criteria.evaluate(cov)
        assert meets is False
        assert any("Addressed rate" in r for r in reasons)

    def test_evaluate_high_withdrawn_rate(self):
        criteria = NeedPromotionCriteria(max_withdrawn_rate=0.1)
        cov = _make_coverage(
            total_needs=20, addressed_count=10, withdrawn_count=8,
        )
        meets, reasons = criteria.evaluate(cov)
        assert meets is False
        assert any("Withdrawn rate" in r for r in reasons)

    def test_evaluate_low_justification_count(self):
        criteria = NeedPromotionCriteria(min_avg_justification_count=3.0)
        cov = _make_coverage(avg_justification_count=1.0)
        meets, reasons = criteria.evaluate(cov)
        assert meets is False
        assert any("justification count" in r for r in reasons)

    def test_evaluate_age_check(self):
        criteria = NeedPromotionCriteria(min_age_days=30)
        cov = _make_coverage()
        meets, reasons = criteria.evaluate(
            cov, created_at="2099-01-01T00:00:00Z",
        )
        assert meets is False
        assert any("too young" in r for r in reasons)


# ── NeedPromotionEngine Tests ──────────────────────────────────────────

class TestNeedPromotionEngine:
    def test_identify_promotion_candidates(self):
        engine = NeedPromotionEngine()
        report = _make_report()

        candidates = engine.identify_promotion_candidates(report)
        assert len(candidates) == 3

        # "sh-good" should score highest
        assert candidates[0].stakeholder_id == "sh-good"
        assert candidates[0].meets_criteria is True

    def test_identify_deprecation_candidates(self):
        engine = NeedPromotionEngine()
        report = _make_report()

        candidates = engine.identify_deprecation_candidates(report)
        assert len(candidates) >= 2

        # Unserved should be flagged with high severity
        unserved = next(
            (c for c in candidates if c.stakeholder_id == "sh-unserved"),
            None,
        )
        assert unserved is not None
        assert unserved.severity == "high"

    def test_deprecation_high_withdrawal_severity(self):
        engine = NeedPromotionEngine()
        # Stakeholder with high withdrawal rate
        coverage = (
            _make_coverage("sh-bad", 10, 1, 8, 0, 1, 0, 0.5),
        )
        report = _make_report(coverage=coverage)

        candidates = engine.identify_deprecation_candidates(report)
        assert len(candidates) >= 1

        bad = next(
            (c for c in candidates if c.stakeholder_id == "sh-bad"),
            None,
        )
        assert bad is not None
        assert bad.severity == "high"

    def test_create_proposal(self):
        engine = NeedPromotionEngine()
        proposal = engine.create_proposal(
            proposal_type=NeedProposalType.PROMOTE,
            stakeholder_id="sh-cto",
            proposed_by="analyst",
            rationale="High addressed rate",
        )

        assert proposal.proposal_id.startswith("proposal-")
        assert proposal.status == NeedProposalStatus.PENDING
        assert proposal.stakeholder_id == "sh-cto"

    def test_vote_on_proposal(self):
        engine = NeedPromotionEngine()
        proposal = engine.create_proposal(
            NeedProposalType.PROMOTE, "sh-cto", "analyst", "reason",
        )

        updated = engine.vote(
            proposal.proposal_id, "reviewer", True, "LGTM",
        )
        assert updated.approval_count == 1
        assert updated.rejection_count == 0
        assert len(updated.votes) == 1

    def test_approve_proposal(self):
        engine = NeedPromotionEngine()
        proposal = engine.create_proposal(
            NeedProposalType.PROMOTE, "sh-cto", "analyst", "reason",
        )

        approved = engine.approve_proposal(
            proposal.proposal_id, "admin", "Approved",
        )
        assert approved.status == NeedProposalStatus.APPROVED
        assert approved.resolved_by == "admin"

    def test_reject_proposal(self):
        engine = NeedPromotionEngine()
        proposal = engine.create_proposal(
            NeedProposalType.DEPRECATE, "sh-qa", "analyst", "reason",
        )

        rejected = engine.reject_proposal(
            proposal.proposal_id, "admin", "Not ready",
        )
        assert rejected.status == NeedProposalStatus.REJECTED

    def test_apply_proposal(self):
        engine = NeedPromotionEngine()
        proposal = engine.create_proposal(
            NeedProposalType.PROMOTE, "sh-cto", "analyst", "reason",
        )
        engine.approve_proposal(proposal.proposal_id, "admin")

        applied = engine.apply_proposal(
            proposal.proposal_id, "deployer",
        )
        assert applied.status == NeedProposalStatus.APPLIED

    def test_apply_unapproved_raises(self):
        engine = NeedPromotionEngine()
        proposal = engine.create_proposal(
            NeedProposalType.PROMOTE, "sh-cto", "analyst", "reason",
        )

        with pytest.raises(ValueError, match="APPROVED"):
            engine.apply_proposal(proposal.proposal_id, "deployer")

    def test_vote_on_resolved_raises(self):
        engine = NeedPromotionEngine()
        proposal = engine.create_proposal(
            NeedProposalType.PROMOTE, "sh-cto", "analyst", "reason",
        )
        engine.approve_proposal(proposal.proposal_id, "admin")

        with pytest.raises(ValueError, match="already resolved"):
            engine.vote(proposal.proposal_id, "latecomer", True)

    def test_approve_resolved_raises(self):
        engine = NeedPromotionEngine()
        proposal = engine.create_proposal(
            NeedProposalType.PROMOTE, "sh-cto", "analyst", "reason",
        )
        engine.reject_proposal(proposal.proposal_id, "admin")

        with pytest.raises(ValueError, match="already resolved"):
            engine.approve_proposal(proposal.proposal_id, "admin")

    def test_get_proposal(self):
        engine = NeedPromotionEngine()
        proposal = engine.create_proposal(
            NeedProposalType.PROMOTE, "sh-cto", "analyst", "reason",
        )

        got = engine.get_proposal(proposal.proposal_id)
        assert got is not None
        assert got.stakeholder_id == "sh-cto"

        assert engine.get_proposal("nonexistent") is None

    def test_list_proposals(self):
        engine = NeedPromotionEngine()
        engine.create_proposal(
            NeedProposalType.PROMOTE, "A", "analyst", "reason",
        )
        p2 = engine.create_proposal(
            NeedProposalType.DEPRECATE, "B", "analyst", "reason",
        )
        engine.approve_proposal(p2.proposal_id, "admin")

        all_proposals = engine.list_proposals()
        assert len(all_proposals) == 2

        pending = engine.list_proposals(NeedProposalStatus.PENDING)
        assert len(pending) == 1

        approved = engine.list_proposals(NeedProposalStatus.APPROVED)
        assert len(approved) == 1

    def test_nonexistent_proposal_raises(self):
        engine = NeedPromotionEngine()
        with pytest.raises(ValueError, match="not found"):
            engine.vote("nonexistent", "voter", True)

    def test_proposal_can_be_approved(self):
        engine = NeedPromotionEngine()
        proposal = engine.create_proposal(
            NeedProposalType.PROMOTE, "sh-cto", "analyst", "reason",
            required_approvals=2,
        )
        assert proposal.can_be_approved is False

        engine.vote(proposal.proposal_id, "reviewer1", True)
        updated = engine.vote(proposal.proposal_id, "reviewer2", True)
        assert updated.can_be_approved is True

    def test_promotion_score_calculation(self):
        engine = NeedPromotionEngine()
        report = _make_report()

        candidates = engine.identify_promotion_candidates(report)
        good = next(
            c for c in candidates if c.stakeholder_id == "sh-good"
        )
        unserved = next(
            c for c in candidates if c.stakeholder_id == "sh-unserved"
        )

        assert good.score > unserved.score
