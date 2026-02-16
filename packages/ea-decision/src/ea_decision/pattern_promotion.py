"""Pattern Promotion Engine — S5 Evolution for Decision Layer.

Pattern promotion and change proposal management.
Provides:
- PatternPromotionCriteria: 승격 기준
- PatternChangeProposal: 패턴 변경 제안
- PatternPromotionEngine: 승격 엔진

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
    from ea_decision.decision_analyzer import (
        DecisionAnalysisReport,
        PatternEffectiveness,
    )


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"


# ═══════════════════════════════════════════════════════════════════════════════
# Promotion Criteria
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PatternPromotionCriteria:
    """패턴 승격 기준."""
    min_decisions: int = 20
    min_acceptance_rate: float = 0.6
    max_revision_rate: float = 0.2
    min_avg_evaluation_score: float = 0.5
    min_age_days: int = 7

    def evaluate(
        self,
        effectiveness: PatternEffectiveness,
        created_at: str = "",
    ) -> tuple[bool, list[str]]:
        """승격 기준 평가.

        Returns:
            (승격 가능 여부, 불충족 사유 목록)
        """
        reasons: list[str] = []

        if effectiveness.total_decisions < self.min_decisions:
            reasons.append(
                f"Insufficient decisions: {effectiveness.total_decisions} "
                f"< {self.min_decisions}"
            )

        if effectiveness.acceptance_rate < self.min_acceptance_rate:
            reasons.append(
                f"Acceptance rate too low: {effectiveness.acceptance_rate:.2%} "
                f"< {self.min_acceptance_rate:.2%}"
            )

        if effectiveness.revision_rate > self.max_revision_rate:
            reasons.append(
                f"Revision rate too high: {effectiveness.revision_rate:.2%} "
                f"> {self.max_revision_rate:.2%}"
            )

        if effectiveness.avg_evaluation_score < self.min_avg_evaluation_score:
            reasons.append(
                f"Avg evaluation score too low: "
                f"{effectiveness.avg_evaluation_score:.2f} "
                f"< {self.min_avg_evaluation_score:.2f}"
            )

        if created_at:
            try:
                created = datetime.fromisoformat(created_at.rstrip("Z"))
                now = datetime.now(UTC).replace(tzinfo=None)
                age_days = (now - created).days
                if age_days < self.min_age_days:
                    reasons.append(
                        f"Pattern too young: {age_days} days "
                        f"< {self.min_age_days} days"
                    )
            except (ValueError, TypeError):
                pass

        return (len(reasons) == 0, reasons)


# ═══════════════════════════════════════════════════════════════════════════════
# Pattern Change Proposal
# ═══════════════════════════════════════════════════════════════════════════════

class PatternProposalType(StrEnum):
    """변경 제안 유형."""
    PROMOTE = "promote"
    DEPRECATE = "deprecate"
    MODIFY = "modify"
    CREATE = "create"


class PatternProposalStatus(StrEnum):
    """변경 제안 상태."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True)
class PatternProposalVote:
    """투표 기록."""
    voter: str
    approve: bool
    timestamp: str
    comment: str = ""


@dataclass(frozen=True)
class PatternChangeProposal:
    """패턴 변경 제안."""
    proposal_id: str
    proposal_type: PatternProposalType
    pattern_name: str

    proposed_by: str
    proposed_at: str

    status: PatternProposalStatus = PatternProposalStatus.PENDING

    rationale: str = ""
    evidence_report_id: str = ""

    votes: tuple[PatternProposalVote, ...] = ()
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
        return self.status != PatternProposalStatus.PENDING

    def with_vote(self, vote: PatternProposalVote) -> PatternChangeProposal:
        return PatternChangeProposal(
            proposal_id=self.proposal_id,
            proposal_type=self.proposal_type,
            pattern_name=self.pattern_name,
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
        status: PatternProposalStatus,
        resolved_by: str,
        comment: str = "",
    ) -> PatternChangeProposal:
        now = _utc_now_iso()
        return PatternChangeProposal(
            proposal_id=self.proposal_id,
            proposal_type=self.proposal_type,
            pattern_name=self.pattern_name,
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
class PromotionCandidate:
    """승격 후보."""
    pattern_name: str
    effectiveness: PatternEffectiveness
    meets_criteria: bool
    failure_reasons: tuple[str, ...]
    score: float


@dataclass(frozen=True)
class DeprecationCandidate:
    """폐기 후보."""
    pattern_name: str
    effectiveness: PatternEffectiveness
    deprecation_reasons: tuple[str, ...]
    severity: str


# ═══════════════════════════════════════════════════════════════════════════════
# PatternPromotionEngine
# ═══════════════════════════════════════════════════════════════════════════════

class PatternPromotionEngine:
    """패턴 승격 엔진.

    DecisionAnalysisReport 기반으로 승격/폐기 후보 식별 + 제안 워크플로.
    """

    __slots__ = ("_criteria", "_proposals")

    def __init__(
        self,
        criteria: PatternPromotionCriteria | None = None,
    ) -> None:
        self._criteria = criteria or PatternPromotionCriteria()
        self._proposals: dict[str, PatternChangeProposal] = {}

    @property
    def criteria(self) -> PatternPromotionCriteria:
        return self._criteria

    def identify_promotion_candidates(
        self,
        report: DecisionAnalysisReport,
    ) -> tuple[PromotionCandidate, ...]:
        """분석 보고서에서 승격 후보 식별."""
        candidates: list[PromotionCandidate] = []

        for eff in report.pattern_effectiveness:
            meets, reasons = self._criteria.evaluate(eff)
            score = self._calculate_promotion_score(eff)

            candidates.append(PromotionCandidate(
                pattern_name=eff.pattern_name,
                effectiveness=eff,
                meets_criteria=meets,
                failure_reasons=tuple(reasons),
                score=score,
            ))

        return tuple(sorted(candidates, key=lambda c: -c.score))

    def identify_deprecation_candidates(
        self,
        report: DecisionAnalysisReport,
    ) -> tuple[DeprecationCandidate, ...]:
        """분석 보고서에서 폐기 후보 식별."""
        from ea_decision.decision_analyzer import PatternEffectivenessGrade

        candidates: list[DeprecationCandidate] = []

        for eff in report.pattern_effectiveness:
            reasons: list[str] = []
            severity = "low"

            if eff.grade == PatternEffectivenessGrade.UNUSED:
                reasons.append("Pattern has never been used (UNUSED)")
                severity = "high"
            elif eff.grade == PatternEffectivenessGrade.INEFFECTIVE:
                reasons.append("Pattern is frequently rejected or deprecated")
                severity = "medium"

            if eff.rejection_rate > 0.5:
                reasons.append(
                    f"Very high rejection rate: {eff.rejection_rate:.2%}"
                )
                severity = "critical" if severity == "high" else "high"

            if reasons:
                candidates.append(DeprecationCandidate(
                    pattern_name=eff.pattern_name,
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
        proposal_type: PatternProposalType,
        pattern_name: str,
        proposed_by: str,
        rationale: str,
        evidence_report_id: str = "",
        required_approvals: int = 1,
    ) -> PatternChangeProposal:
        """변경 제안 생성."""
        now = _utc_now_iso()
        proposal_id = f"proposal-{uuid.uuid4().hex[:8]}"

        proposal = PatternChangeProposal(
            proposal_id=proposal_id,
            proposal_type=proposal_type,
            pattern_name=pattern_name,
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
    ) -> PatternChangeProposal:
        """제안에 투표."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.is_resolved:
            raise ValueError(f"Proposal {proposal_id} is already resolved")

        now = _utc_now_iso()
        vote = PatternProposalVote(
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
    ) -> PatternChangeProposal:
        """제안 승인."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.is_resolved:
            raise ValueError(f"Proposal {proposal_id} is already resolved")

        resolved = proposal.resolve(
            PatternProposalStatus.APPROVED, approved_by, comment,
        )
        self._proposals[proposal_id] = resolved
        return resolved

    def reject_proposal(
        self,
        proposal_id: str,
        rejected_by: str,
        comment: str = "",
    ) -> PatternChangeProposal:
        """제안 거부."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.is_resolved:
            raise ValueError(f"Proposal {proposal_id} is already resolved")

        resolved = proposal.resolve(
            PatternProposalStatus.REJECTED, rejected_by, comment,
        )
        self._proposals[proposal_id] = resolved
        return resolved

    def apply_proposal(
        self,
        proposal_id: str,
        applied_by: str,
    ) -> PatternChangeProposal:
        """승인된 제안 적용."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.status != PatternProposalStatus.APPROVED:
            raise ValueError(
                f"Proposal must be APPROVED to apply, got {proposal.status}"
            )

        applied = proposal.resolve(
            PatternProposalStatus.APPLIED, applied_by, "Applied",
        )
        self._proposals[proposal_id] = applied
        return applied

    def get_proposal(self, proposal_id: str) -> PatternChangeProposal | None:
        return self._proposals.get(proposal_id)

    def list_proposals(
        self,
        status: PatternProposalStatus | None = None,
    ) -> tuple[PatternChangeProposal, ...]:
        if status is None:
            return tuple(self._proposals.values())
        return tuple(
            p for p in self._proposals.values() if p.status == status
        )

    def _calculate_promotion_score(
        self,
        eff: PatternEffectiveness,
    ) -> float:
        """승격 점수 계산 (0-100)."""
        score = 0.0

        # Decision volume (0-30)
        score += min(30, eff.total_decisions / 5)

        # Acceptance rate (0-40)
        score += eff.acceptance_rate * 40

        # Low revision rate (0-15)
        score += (1 - eff.revision_rate) * 15

        # Evaluation quality (0-15)
        score += eff.avg_evaluation_score * 15

        return min(100, max(0, score))
