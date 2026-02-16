"""Workflow Promotion Engine — S5 Evolution for Flow Layer.

Workflow promotion and change proposal management.
Provides:
- WorkflowPromotionCriteria: 승격 기준
- WorkflowChangeProposal: 워크플로 변경 제안
- WorkflowPromotionEngine: 승격 엔진

References:
- ea_kernel/promotion_engine.py: S5 승격 패턴
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_flow.flow_analyzer import FlowAnalysisReport, StepEffectiveness


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"


# ═══════════════════════════════════════════════════════════════════════════════
# Promotion Criteria
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class WorkflowPromotionCriteria:
    """워크플로 승격 기준."""
    min_executions: int = 20
    min_success_rate: float = 0.7
    max_rollback_rate: float = 0.1
    min_age_days: int = 7

    def evaluate(
        self,
        effectiveness: StepEffectiveness,
        created_at: str = "",
    ) -> tuple[bool, list[str]]:
        """승격 기준 평가.

        Returns:
            (승격 가능 여부, 불충족 사유 목록)
        """
        reasons: list[str] = []

        if effectiveness.total_executions < self.min_executions:
            reasons.append(
                f"Insufficient executions: {effectiveness.total_executions} "
                f"< {self.min_executions}"
            )

        if effectiveness.success_rate < self.min_success_rate:
            reasons.append(
                f"Success rate too low: {effectiveness.success_rate:.2%} "
                f"< {self.min_success_rate:.2%}"
            )

        if effectiveness.rollback_trigger_rate > self.max_rollback_rate:
            reasons.append(
                f"Rollback trigger rate too high: "
                f"{effectiveness.rollback_trigger_rate:.2%} "
                f"> {self.max_rollback_rate:.2%}"
            )

        if created_at:
            try:
                created = datetime.fromisoformat(created_at.rstrip("Z"))
                now = datetime.now(UTC).replace(tzinfo=None)
                age_days = (now - created).days
                if age_days < self.min_age_days:
                    reasons.append(
                        f"Step too young: {age_days} days "
                        f"< {self.min_age_days} days"
                    )
            except (ValueError, TypeError):
                pass

        return (len(reasons) == 0, reasons)


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow Change Proposal
# ═══════════════════════════════════════════════════════════════════════════════

class WorkflowProposalType(StrEnum):
    """변경 제안 유형."""
    PROMOTE = "promote"
    DEPRECATE = "deprecate"
    MODIFY = "modify"
    CREATE = "create"


class WorkflowProposalStatus(StrEnum):
    """변경 제안 상태."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True)
class WorkflowProposalVote:
    """투표 기록."""
    voter: str
    approve: bool
    timestamp: str
    comment: str = ""


@dataclass(frozen=True)
class WorkflowChangeProposal:
    """워크플로 변경 제안."""
    proposal_id: str
    proposal_type: WorkflowProposalType
    workflow_name: str

    proposed_by: str
    proposed_at: str

    status: WorkflowProposalStatus = WorkflowProposalStatus.PENDING

    rationale: str = ""
    evidence_report_id: str = ""

    votes: tuple[WorkflowProposalVote, ...] = ()
    required_approvals: int = 1

    resolved_at: str = ""
    resolved_by: str = ""
    resolution_comment: str = ""

    @property
    def approval_count(self) -> int:
        return sum(1 for v in self.votes if v.approve)

    @property
    def rejection_count(self) -> int:
        return sum(1 for v in self.votes if not v.approve)

    @property
    def can_be_approved(self) -> bool:
        return self.approval_count >= self.required_approvals

    @property
    def is_resolved(self) -> bool:
        return self.status != WorkflowProposalStatus.PENDING

    def with_vote(self, vote: WorkflowProposalVote) -> WorkflowChangeProposal:
        return WorkflowChangeProposal(
            proposal_id=self.proposal_id,
            proposal_type=self.proposal_type,
            workflow_name=self.workflow_name,
            proposed_by=self.proposed_by,
            proposed_at=self.proposed_at,
            status=self.status,
            rationale=self.rationale,
            evidence_report_id=self.evidence_report_id,
            votes=(*self.votes, vote),
            required_approvals=self.required_approvals,
            resolved_at=self.resolved_at,
            resolved_by=self.resolved_by,
            resolution_comment=self.resolution_comment,
        )

    def resolve(
        self,
        status: WorkflowProposalStatus,
        resolved_by: str,
        comment: str = "",
    ) -> WorkflowChangeProposal:
        now = _utc_now_iso()
        return WorkflowChangeProposal(
            proposal_id=self.proposal_id,
            proposal_type=self.proposal_type,
            workflow_name=self.workflow_name,
            proposed_by=self.proposed_by,
            proposed_at=self.proposed_at,
            status=status,
            rationale=self.rationale,
            evidence_report_id=self.evidence_report_id,
            votes=self.votes,
            required_approvals=self.required_approvals,
            resolved_at=now,
            resolved_by=resolved_by,
            resolution_comment=comment,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Promotion/Deprecation Candidates
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class WorkflowPromotionCandidate:
    """승격 후보."""
    step_name: str
    effectiveness: StepEffectiveness
    meets_criteria: bool
    failure_reasons: tuple[str, ...]
    score: float


@dataclass(frozen=True)
class WorkflowDeprecationCandidate:
    """폐기 후보."""
    step_name: str
    effectiveness: StepEffectiveness
    deprecation_reasons: tuple[str, ...]
    severity: str


# ═══════════════════════════════════════════════════════════════════════════════
# WorkflowPromotionEngine
# ═══════════════════════════════════════════════════════════════════════════════

class WorkflowPromotionEngine:
    """워크플로 승격 엔진.

    FlowAnalysisReport 기반으로 승격/폐기 후보 식별 + 제안 워크플로.
    """

    __slots__ = ("_criteria", "_proposals")

    def __init__(
        self,
        criteria: WorkflowPromotionCriteria | None = None,
    ) -> None:
        self._criteria = criteria or WorkflowPromotionCriteria()
        self._proposals: dict[str, WorkflowChangeProposal] = {}

    @property
    def criteria(self) -> WorkflowPromotionCriteria:
        return self._criteria

    def identify_promotion_candidates(
        self,
        report: FlowAnalysisReport,
    ) -> tuple[WorkflowPromotionCandidate, ...]:
        """분석 보고서에서 승격 후보 식별."""
        candidates: list[WorkflowPromotionCandidate] = []

        for eff in report.step_effectiveness:
            meets, reasons = self._criteria.evaluate(eff)
            score = self._calculate_promotion_score(eff)

            candidates.append(WorkflowPromotionCandidate(
                step_name=eff.step_name,
                effectiveness=eff,
                meets_criteria=meets,
                failure_reasons=tuple(reasons),
                score=score,
            ))

        return tuple(sorted(candidates, key=lambda c: -c.score))

    def identify_deprecation_candidates(
        self,
        report: FlowAnalysisReport,
    ) -> tuple[WorkflowDeprecationCandidate, ...]:
        """분석 보고서에서 폐기 후보 식별."""
        from ea_flow.flow_analyzer import StepEffectivenessGrade

        candidates: list[WorkflowDeprecationCandidate] = []

        for eff in report.step_effectiveness:
            reasons: list[str] = []
            severity = "low"

            if eff.grade == StepEffectivenessGrade.UNUSED:
                reasons.append("Step has never been executed (UNUSED)")
                severity = "high"
            elif eff.grade == StepEffectivenessGrade.BROKEN:
                reasons.append("Step consistently fails (BROKEN)")
                severity = "critical"
            elif eff.grade == StepEffectivenessGrade.FRAGILE:
                reasons.append("Step frequently fails (FRAGILE)")
                severity = "medium"

            if eff.rollback_trigger_rate > 0.3:
                reasons.append(
                    f"High rollback trigger rate: "
                    f"{eff.rollback_trigger_rate:.2%}"
                )
                if severity != "critical":
                    severity = "critical" if severity == "high" else "high"

            if reasons:
                candidates.append(WorkflowDeprecationCandidate(
                    step_name=eff.step_name,
                    effectiveness=eff,
                    deprecation_reasons=tuple(reasons),
                    severity=severity,
                ))

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return tuple(sorted(
            candidates,
            key=lambda c: severity_order.get(c.severity, 4),
        ))

    def create_proposal(
        self,
        proposal_type: WorkflowProposalType,
        workflow_name: str,
        proposed_by: str,
        rationale: str,
        evidence_report_id: str = "",
        required_approvals: int = 1,
    ) -> WorkflowChangeProposal:
        """변경 제안 생성."""
        now = _utc_now_iso()
        proposal_id = f"proposal-{uuid.uuid4().hex[:8]}"

        proposal = WorkflowChangeProposal(
            proposal_id=proposal_id,
            proposal_type=proposal_type,
            workflow_name=workflow_name,
            proposed_by=proposed_by,
            proposed_at=now,
            rationale=rationale,
            evidence_report_id=evidence_report_id,
            required_approvals=required_approvals,
        )

        self._proposals[proposal_id] = proposal
        return proposal

    def vote(
        self,
        proposal_id: str,
        voter: str,
        approve: bool,
        comment: str = "",
    ) -> WorkflowChangeProposal:
        """제안에 투표."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.is_resolved:
            raise ValueError(f"Proposal {proposal_id} is already resolved")

        now = _utc_now_iso()
        vote = WorkflowProposalVote(
            voter=voter,
            approve=approve,
            timestamp=now,
            comment=comment,
        )

        updated = proposal.with_vote(vote)
        self._proposals[proposal_id] = updated
        return updated

    def approve_proposal(
        self,
        proposal_id: str,
        approved_by: str,
        comment: str = "",
    ) -> WorkflowChangeProposal:
        """제안 승인."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.is_resolved:
            raise ValueError(f"Proposal {proposal_id} is already resolved")

        resolved = proposal.resolve(
            WorkflowProposalStatus.APPROVED, approved_by, comment,
        )
        self._proposals[proposal_id] = resolved
        return resolved

    def reject_proposal(
        self,
        proposal_id: str,
        rejected_by: str,
        comment: str = "",
    ) -> WorkflowChangeProposal:
        """제안 거부."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.is_resolved:
            raise ValueError(f"Proposal {proposal_id} is already resolved")

        resolved = proposal.resolve(
            WorkflowProposalStatus.REJECTED, rejected_by, comment,
        )
        self._proposals[proposal_id] = resolved
        return resolved

    def apply_proposal(
        self,
        proposal_id: str,
        applied_by: str,
    ) -> WorkflowChangeProposal:
        """승인된 제안 적용."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.status != WorkflowProposalStatus.APPROVED:
            raise ValueError(
                f"Proposal must be APPROVED to apply, got {proposal.status}"
            )

        applied = proposal.resolve(
            WorkflowProposalStatus.APPLIED, applied_by, "Applied",
        )
        self._proposals[proposal_id] = applied
        return applied

    def get_proposal(self, proposal_id: str) -> WorkflowChangeProposal | None:
        return self._proposals.get(proposal_id)

    def list_proposals(
        self,
        status: WorkflowProposalStatus | None = None,
    ) -> tuple[WorkflowChangeProposal, ...]:
        if status is None:
            return tuple(self._proposals.values())
        return tuple(
            p for p in self._proposals.values() if p.status == status
        )

    def _calculate_promotion_score(
        self,
        eff: StepEffectiveness,
    ) -> float:
        """승격 점수 계산 (0-100)."""
        score = 0.0

        # Execution volume (0-30)
        score += min(30, eff.total_executions / 5)

        # Success rate (0-40)
        score += eff.success_rate * 40

        # Low rollback trigger rate (0-15)
        score += (1 - eff.rollback_trigger_rate) * 15

        # Low failure rate (0-15)
        score += (1 - eff.failure_rate) * 15

        return min(100, max(0, score))
