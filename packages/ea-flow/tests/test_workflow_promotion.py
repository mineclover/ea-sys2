"""Tests for WorkflowPromotionEngine — S5 Evolution."""

from __future__ import annotations

import pytest

from ea_flow.flow_analyzer import (
    FlowAnalysisReport,
    StepEffectiveness,
    StepEffectivenessGrade,
)
from ea_flow.workflow_promotion import (
    WorkflowChangeProposal,
    WorkflowDeprecationCandidate,
    WorkflowPromotionCandidate,
    WorkflowPromotionCriteria,
    WorkflowPromotionEngine,
    WorkflowProposalStatus,
    WorkflowProposalType,
    WorkflowProposalVote,
)


# ── Factory ─────────────────────────────────────────────────────────────

def _make_effectiveness(
    step_name: str = "step-a",
    total_executions: int = 30,
    success_count: int = 28,
    failure_count: int = 2,
    rollback_trigger_count: int = 0,
) -> StepEffectiveness:
    return StepEffectiveness(
        step_name=step_name,
        total_executions=total_executions,
        success_count=success_count,
        failure_count=failure_count,
        rollback_trigger_count=rollback_trigger_count,
    )


def _make_report(
    effectiveness: tuple[StepEffectiveness, ...] | None = None,
) -> FlowAnalysisReport:
    if effectiveness is None:
        effectiveness = (
            _make_effectiveness("reliable", 30, 29, 1, 0),
            _make_effectiveness("unused", 0, 0, 0, 0),
            _make_effectiveness("broken", 20, 2, 18, 10),
        )
    return FlowAnalysisReport(
        report_id="test-report",
        created_at="2025-01-01T00:00:00Z",
        total_executions_analyzed=50,
        step_effectiveness=effectiveness,
        broken_steps=("broken",),
        unused_steps=("unused",),
    )


# ── WorkflowPromotionCriteria Tests ────────────────────────────────────

class TestWorkflowPromotionCriteria:
    def test_evaluate_passes_all(self):
        criteria = WorkflowPromotionCriteria()
        eff = _make_effectiveness(total_executions=30, success_count=28)
        meets, reasons = criteria.evaluate(eff)
        assert meets is True
        assert len(reasons) == 0

    def test_evaluate_insufficient_executions(self):
        criteria = WorkflowPromotionCriteria(min_executions=50)
        eff = _make_effectiveness(total_executions=30)
        meets, reasons = criteria.evaluate(eff)
        assert meets is False
        assert any("Insufficient executions" in r for r in reasons)

    def test_evaluate_low_success_rate(self):
        criteria = WorkflowPromotionCriteria()
        eff = _make_effectiveness(total_executions=30, success_count=5, failure_count=25)
        meets, reasons = criteria.evaluate(eff)
        assert meets is False
        assert any("Success rate" in r for r in reasons)

    def test_evaluate_high_rollback_rate(self):
        criteria = WorkflowPromotionCriteria(max_rollback_rate=0.05)
        eff = _make_effectiveness(
            total_executions=30, rollback_trigger_count=5,
        )
        meets, reasons = criteria.evaluate(eff)
        assert meets is False
        assert any("Rollback trigger rate" in r for r in reasons)

    def test_evaluate_age_check(self):
        criteria = WorkflowPromotionCriteria(min_age_days=30)
        eff = _make_effectiveness()
        meets, reasons = criteria.evaluate(eff, created_at="2099-01-01T00:00:00Z")
        assert meets is False
        assert any("too young" in r for r in reasons)


# ── WorkflowPromotionEngine Tests ──────────────────────────────────────

class TestWorkflowPromotionEngine:
    def test_identify_promotion_candidates(self):
        engine = WorkflowPromotionEngine()
        report = _make_report()

        candidates = engine.identify_promotion_candidates(report)
        assert len(candidates) == 3

        # "reliable" should score highest
        assert candidates[0].step_name == "reliable"
        assert candidates[0].meets_criteria is True

    def test_identify_deprecation_candidates(self):
        engine = WorkflowPromotionEngine()
        report = _make_report()

        candidates = engine.identify_deprecation_candidates(report)
        assert len(candidates) >= 2

        # Broken should be critical
        broken = next(
            (c for c in candidates if c.step_name == "broken"), None,
        )
        assert broken is not None
        assert broken.severity == "critical"

    def test_create_proposal(self):
        engine = WorkflowPromotionEngine()
        proposal = engine.create_proposal(
            proposal_type=WorkflowProposalType.PROMOTE,
            workflow_name="validate-model",
            proposed_by="analyst",
            rationale="High success rate",
        )

        assert proposal.proposal_id.startswith("proposal-")
        assert proposal.status == WorkflowProposalStatus.PENDING

    def test_vote_on_proposal(self):
        engine = WorkflowPromotionEngine()
        proposal = engine.create_proposal(
            WorkflowProposalType.PROMOTE, "wf", "analyst", "reason",
        )

        updated = engine.vote(proposal.proposal_id, "reviewer", True)
        assert updated.approval_count == 1

    def test_approve_proposal(self):
        engine = WorkflowPromotionEngine()
        proposal = engine.create_proposal(
            WorkflowProposalType.PROMOTE, "wf", "analyst", "reason",
        )

        approved = engine.approve_proposal(
            proposal.proposal_id, "admin", "OK",
        )
        assert approved.status == WorkflowProposalStatus.APPROVED

    def test_reject_proposal(self):
        engine = WorkflowPromotionEngine()
        proposal = engine.create_proposal(
            WorkflowProposalType.DEPRECATE, "wf", "analyst", "reason",
        )

        rejected = engine.reject_proposal(
            proposal.proposal_id, "admin", "No",
        )
        assert rejected.status == WorkflowProposalStatus.REJECTED

    def test_apply_proposal(self):
        engine = WorkflowPromotionEngine()
        proposal = engine.create_proposal(
            WorkflowProposalType.PROMOTE, "wf", "analyst", "reason",
        )
        engine.approve_proposal(proposal.proposal_id, "admin")

        applied = engine.apply_proposal(proposal.proposal_id, "deployer")
        assert applied.status == WorkflowProposalStatus.APPLIED

    def test_apply_unapproved_raises(self):
        engine = WorkflowPromotionEngine()
        proposal = engine.create_proposal(
            WorkflowProposalType.PROMOTE, "wf", "analyst", "reason",
        )

        with pytest.raises(ValueError, match="APPROVED"):
            engine.apply_proposal(proposal.proposal_id, "deployer")

    def test_vote_on_resolved_raises(self):
        engine = WorkflowPromotionEngine()
        proposal = engine.create_proposal(
            WorkflowProposalType.PROMOTE, "wf", "analyst", "reason",
        )
        engine.approve_proposal(proposal.proposal_id, "admin")

        with pytest.raises(ValueError, match="already resolved"):
            engine.vote(proposal.proposal_id, "latecomer", True)

    def test_get_proposal(self):
        engine = WorkflowPromotionEngine()
        proposal = engine.create_proposal(
            WorkflowProposalType.PROMOTE, "wf", "analyst", "reason",
        )

        got = engine.get_proposal(proposal.proposal_id)
        assert got is not None
        assert got.workflow_name == "wf"
        assert engine.get_proposal("nonexistent") is None

    def test_list_proposals(self):
        engine = WorkflowPromotionEngine()
        engine.create_proposal(
            WorkflowProposalType.PROMOTE, "A", "analyst", "reason",
        )
        p2 = engine.create_proposal(
            WorkflowProposalType.DEPRECATE, "B", "analyst", "reason",
        )
        engine.approve_proposal(p2.proposal_id, "admin")

        assert len(engine.list_proposals()) == 2
        assert len(engine.list_proposals(WorkflowProposalStatus.PENDING)) == 1
        assert len(engine.list_proposals(WorkflowProposalStatus.APPROVED)) == 1

    def test_nonexistent_proposal_raises(self):
        engine = WorkflowPromotionEngine()
        with pytest.raises(ValueError, match="not found"):
            engine.vote("nonexistent", "voter", True)

    def test_proposal_can_be_approved(self):
        engine = WorkflowPromotionEngine()
        proposal = engine.create_proposal(
            WorkflowProposalType.PROMOTE, "wf", "analyst", "reason",
            required_approvals=2,
        )
        assert proposal.can_be_approved is False

        engine.vote(proposal.proposal_id, "r1", True)
        updated = engine.vote(proposal.proposal_id, "r2", True)
        assert updated.can_be_approved is True

    def test_promotion_score_calculation(self):
        engine = WorkflowPromotionEngine()
        report = _make_report()

        candidates = engine.identify_promotion_candidates(report)
        reliable = next(c for c in candidates if c.step_name == "reliable")
        broken = next(c for c in candidates if c.step_name == "broken")

        assert reliable.score > broken.score
