"""Needs Promotion Engine — S5 Evolution for Needs Layer.

Need promotion and change proposal management.
Provides:
- NeedPromotionCriteria: 승격 기준
- NeedChangeProposal: 니즈 변경 제안
- NeedPromotionEngine: 승격 엔진

References:
- ea_kernel/promotion_engine.py: S5 승격 패턴
- ea_decision/pattern_promotion.py: S5 도메인 번역 패턴
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_needs.needs_analyzer import NeedsAnalysisReport, StakeholderCoverage


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"


# ═══════════════════════════════════════════════════════════════════════════════
# Promotion Criteria
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class NeedPromotionCriteria:
    """니즈(이해관계자) 승격 기준."""
    min_needs: int = 10
    min_addressed_rate: float = 0.5
    max_withdrawn_rate: float = 0.2
    min_avg_justification_count: float = 1.0
    min_age_days: int = 7

    def evaluate(
        self,
        coverage: StakeholderCoverage,
        created_at: str = "",
    ) -> tuple[bool, list[str]]:
        """승격 기준 평가.

        Returns:
            (승격 가능 여부, 불충족 사유 목록)
        """
        reasons: list[str] = []

        if coverage.total_needs < self.min_needs:
            reasons.append(
                f"Insufficient needs: {coverage.total_needs} "
                f"< {self.min_needs}"
            )

        if coverage.addressed_rate < self.min_addressed_rate:
            reasons.append(
                f"Addressed rate too low: {coverage.addressed_rate:.2%} "
                f"< {self.min_addressed_rate:.2%}"
            )

        if coverage.withdrawn_rate > self.max_withdrawn_rate:
            reasons.append(
                f"Withdrawn rate too high: {coverage.withdrawn_rate:.2%} "
                f"> {self.max_withdrawn_rate:.2%}"
            )

        if coverage.avg_justification_count < self.min_avg_justification_count:
            reasons.append(
                f"Avg justification count too low: "
                f"{coverage.avg_justification_count:.1f} "
                f"< {self.min_avg_justification_count:.1f}"
            )

        if created_at:
            try:
                created = datetime.fromisoformat(created_at.rstrip("Z"))
                now = datetime.now(UTC).replace(tzinfo=None)
                age_days = (now - created).days
                if age_days < self.min_age_days:
                    reasons.append(
                        f"Stakeholder too young: {age_days} days "
                        f"< {self.min_age_days} days"
                    )
            except (ValueError, TypeError):
                pass

        return (len(reasons) == 0, reasons)


# ═══════════════════════════════════════════════════════════════════════════════
# Need Change Proposal
# ═══════════════════════════════════════════════════════════════════════════════

class NeedProposalType(StrEnum):
    """변경 제안 유형."""
    PROMOTE = "promote"
    DEPRECATE = "deprecate"
    MODIFY = "modify"
    CREATE = "create"


class NeedProposalStatus(StrEnum):
    """변경 제안 상태."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True)
class NeedProposalVote:
    """투표 기록."""
    voter: str
    approve: bool
    timestamp: str
    comment: str = ""


@dataclass(frozen=True)
class NeedChangeProposal:
    """니즈 변경 제안."""
    proposal_id: str
    proposal_type: NeedProposalType
    stakeholder_id: str

    proposed_by: str
    proposed_at: str

    status: NeedProposalStatus = NeedProposalStatus.PENDING

    rationale: str = ""
    evidence_report_id: str = ""

    votes: tuple[NeedProposalVote, ...] = ()
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
        return self.status != NeedProposalStatus.PENDING

    def with_vote(self, vote: NeedProposalVote) -> NeedChangeProposal:
        return NeedChangeProposal(
            proposal_id=self.proposal_id,
            proposal_type=self.proposal_type,
            stakeholder_id=self.stakeholder_id,
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
        status: NeedProposalStatus,
        resolved_by: str,
        comment: str = "",
    ) -> NeedChangeProposal:
        now = _utc_now_iso()
        return NeedChangeProposal(
            proposal_id=self.proposal_id,
            proposal_type=self.proposal_type,
            stakeholder_id=self.stakeholder_id,
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
class NeedPromotionCandidate:
    """승격 후보."""
    stakeholder_id: str
    coverage: StakeholderCoverage
    meets_criteria: bool
    failure_reasons: tuple[str, ...]
    score: float


@dataclass(frozen=True)
class NeedDeprecationCandidate:
    """폐기 후보."""
    stakeholder_id: str
    coverage: StakeholderCoverage
    deprecation_reasons: tuple[str, ...]
    severity: str


# ═══════════════════════════════════════════════════════════════════════════════
# NeedPromotionEngine
# ═══════════════════════════════════════════════════════════════════════════════

class NeedPromotionEngine:
    """니즈 승격 엔진.

    NeedsAnalysisReport 기반으로 승격/폐기 후보 식별 + 제안 워크플로.
    """

    __slots__ = ("_criteria", "_proposals")

    def __init__(
        self,
        criteria: NeedPromotionCriteria | None = None,
    ) -> None:
        self._criteria = criteria or NeedPromotionCriteria()
        self._proposals: dict[str, NeedChangeProposal] = {}

    @property
    def criteria(self) -> NeedPromotionCriteria:
        return self._criteria

    def identify_promotion_candidates(
        self,
        report: NeedsAnalysisReport,
    ) -> tuple[NeedPromotionCandidate, ...]:
        """분석 보고서에서 승격 후보 식별."""
        candidates: list[NeedPromotionCandidate] = []

        for cov in report.stakeholder_coverage:
            meets, reasons = self._criteria.evaluate(cov)
            score = self._calculate_promotion_score(cov)

            candidates.append(NeedPromotionCandidate(
                stakeholder_id=cov.stakeholder_id,
                coverage=cov,
                meets_criteria=meets,
                failure_reasons=tuple(reasons),
                score=score,
            ))

        return tuple(sorted(candidates, key=lambda c: -c.score))

    def identify_deprecation_candidates(
        self,
        report: NeedsAnalysisReport,
    ) -> tuple[NeedDeprecationCandidate, ...]:
        """분석 보고서에서 폐기 후보 식별."""
        from ea_needs.needs_analyzer import StakeholderCoverageGrade

        candidates: list[NeedDeprecationCandidate] = []

        for cov in report.stakeholder_coverage:
            reasons: list[str] = []
            severity = "low"

            if cov.grade == StakeholderCoverageGrade.UNSERVED:
                reasons.append(
                    "Stakeholder has no needs recorded (UNSERVED)"
                )
                severity = "high"
            elif cov.grade == StakeholderCoverageGrade.UNDERSERVED:
                reasons.append(
                    "Stakeholder's needs are mostly unresolved (UNDERSERVED)"
                )
                severity = "medium"

            if cov.withdrawn_rate > 0.5:
                reasons.append(
                    f"Very high withdrawal rate: "
                    f"{cov.withdrawn_rate:.2%}"
                )
                if severity != "critical":
                    severity = "critical" if severity == "high" else "high"

            if reasons:
                candidates.append(NeedDeprecationCandidate(
                    stakeholder_id=cov.stakeholder_id,
                    coverage=cov,
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
        proposal_type: NeedProposalType,
        stakeholder_id: str,
        proposed_by: str,
        rationale: str,
        evidence_report_id: str = "",
        required_approvals: int = 1,
    ) -> NeedChangeProposal:
        """변경 제안 생성."""
        now = _utc_now_iso()
        proposal_id = f"proposal-{uuid.uuid4().hex[:8]}"

        proposal = NeedChangeProposal(
            proposal_id=proposal_id,
            proposal_type=proposal_type,
            stakeholder_id=stakeholder_id,
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
    ) -> NeedChangeProposal:
        """제안에 투표."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.is_resolved:
            raise ValueError(
                f"Proposal {proposal_id} is already resolved"
            )

        now = _utc_now_iso()
        vote = NeedProposalVote(
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
    ) -> NeedChangeProposal:
        """제안 승인."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.is_resolved:
            raise ValueError(
                f"Proposal {proposal_id} is already resolved"
            )

        resolved = proposal.resolve(
            NeedProposalStatus.APPROVED, approved_by, comment,
        )
        self._proposals[proposal_id] = resolved
        return resolved

    def reject_proposal(
        self,
        proposal_id: str,
        rejected_by: str,
        comment: str = "",
    ) -> NeedChangeProposal:
        """제안 거부."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.is_resolved:
            raise ValueError(
                f"Proposal {proposal_id} is already resolved"
            )

        resolved = proposal.resolve(
            NeedProposalStatus.REJECTED, rejected_by, comment,
        )
        self._proposals[proposal_id] = resolved
        return resolved

    def apply_proposal(
        self,
        proposal_id: str,
        applied_by: str,
    ) -> NeedChangeProposal:
        """승인된 제안 적용."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.status != NeedProposalStatus.APPROVED:
            raise ValueError(
                f"Proposal must be APPROVED to apply, got {proposal.status}"
            )

        applied = proposal.resolve(
            NeedProposalStatus.APPLIED, applied_by, "Applied",
        )
        self._proposals[proposal_id] = applied
        return applied

    def get_proposal(
        self, proposal_id: str,
    ) -> NeedChangeProposal | None:
        return self._proposals.get(proposal_id)

    def list_proposals(
        self,
        status: NeedProposalStatus | None = None,
    ) -> tuple[NeedChangeProposal, ...]:
        if status is None:
            return tuple(self._proposals.values())
        return tuple(
            p for p in self._proposals.values() if p.status == status
        )

    def _calculate_promotion_score(
        self,
        cov: StakeholderCoverage,
    ) -> float:
        """승격 점수 계산 (0-100)."""
        score = 0.0

        # Need volume (0-30)
        score += min(30, cov.total_needs / 3)

        # Addressed rate (0-40)
        score += cov.addressed_rate * 40

        # Low withdrawn rate (0-15)
        score += (1 - cov.withdrawn_rate) * 15

        # Justification quality (0-15)
        score += min(15, cov.avg_justification_count * 5)

        return min(100, max(0, score))
