"""Projection Promotion Engine — S5 Evolution for Projection Layer.

Policy promotion and change proposal management.
Provides:
- PolicyPromotionCriteria: 승격 기준
- PolicyChangeProposal: 정책 변경 제안
- PolicyPromotionEngine: 승격 엔진

References:
- ea_needs/needs_promotion.py: S5 승격 패턴
- ea_decision/pattern_promotion.py: S5 도메인 번역 패턴
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_projection.projection_analyzer import (
        LevelCoverage,
        ProjectionAnalysisReport,
    )


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"


# ═══════════════════════════════════════════════════════════════════════════════
# Promotion Criteria
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PolicyPromotionCriteria:
    """프로젝션 정책(레벨) 승격 기준."""
    min_projections: int = 10
    min_freshness_rate: float = 0.5
    max_stale_rate: float = 0.2
    min_avg_node_count: float = 1.0
    min_age_days: int = 7

    def evaluate(
        self,
        coverage: LevelCoverage,
        created_at: str = "",
    ) -> tuple[bool, list[str]]:
        """승격 기준 평가.

        Returns:
            (승격 가능 여부, 불충족 사유 목록)
        """
        reasons: list[str] = []

        if coverage.total_projections < self.min_projections:
            reasons.append(
                f"Insufficient projections: {coverage.total_projections} "
                f"< {self.min_projections}"
            )

        if coverage.freshness_rate < self.min_freshness_rate:
            reasons.append(
                f"Freshness rate too low: {coverage.freshness_rate:.2%} "
                f"< {self.min_freshness_rate:.2%}"
            )

        if coverage.stale_rate > self.max_stale_rate:
            reasons.append(
                f"Stale rate too high: {coverage.stale_rate:.2%} "
                f"> {self.max_stale_rate:.2%}"
            )

        if coverage.avg_node_count < self.min_avg_node_count:
            reasons.append(
                f"Avg node count too low: "
                f"{coverage.avg_node_count:.1f} "
                f"< {self.min_avg_node_count:.1f}"
            )

        if created_at:
            try:
                created = datetime.fromisoformat(created_at.rstrip("Z"))
                now = datetime.now(UTC).replace(tzinfo=None)
                age_days = (now - created).days
                if age_days < self.min_age_days:
                    reasons.append(
                        f"Level too young: {age_days} days "
                        f"< {self.min_age_days} days"
                    )
            except (ValueError, TypeError):
                pass

        return (len(reasons) == 0, reasons)


# ═══════════════════════════════════════════════════════════════════════════════
# Policy Change Proposal
# ═══════════════════════════════════════════════════════════════════════════════

class PolicyProposalType(StrEnum):
    """변경 제안 유형."""
    PROMOTE = "promote"
    DEPRECATE = "deprecate"
    MODIFY = "modify"
    CREATE = "create"


class PolicyProposalStatus(StrEnum):
    """변경 제안 상태."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True)
class PolicyProposalVote:
    """투표 기록."""
    voter: str
    approve: bool
    timestamp: str
    comment: str = ""


@dataclass(frozen=True)
class PolicyChangeProposal:
    """프로젝션 정책 변경 제안."""
    proposal_id: str
    proposal_type: PolicyProposalType
    level: str

    proposed_by: str
    proposed_at: str

    status: PolicyProposalStatus = PolicyProposalStatus.PENDING

    rationale: str = ""
    evidence_report_id: str = ""

    votes: tuple[PolicyProposalVote, ...] = ()
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
        return self.status != PolicyProposalStatus.PENDING

    def with_vote(self, vote: PolicyProposalVote) -> PolicyChangeProposal:
        return PolicyChangeProposal(
            proposal_id=self.proposal_id,
            proposal_type=self.proposal_type,
            level=self.level,
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
        status: PolicyProposalStatus,
        resolved_by: str,
        comment: str = "",
    ) -> PolicyChangeProposal:
        now = _utc_now_iso()
        return PolicyChangeProposal(
            proposal_id=self.proposal_id,
            proposal_type=self.proposal_type,
            level=self.level,
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
class PolicyPromotionCandidate:
    """승격 후보."""
    level: str
    coverage: LevelCoverage
    meets_criteria: bool
    failure_reasons: tuple[str, ...]
    score: float


@dataclass(frozen=True)
class PolicyDeprecationCandidate:
    """폐기 후보."""
    level: str
    coverage: LevelCoverage
    deprecation_reasons: tuple[str, ...]
    severity: str


# ═══════════════════════════════════════════════════════════════════════════════
# PolicyPromotionEngine
# ═══════════════════════════════════════════════════════════════════════════════

class PolicyPromotionEngine:
    """프로젝션 정책 승격 엔진.

    ProjectionAnalysisReport 기반으로 승격/폐기 후보 식별 + 제안 워크플로.
    """

    __slots__ = ("_criteria", "_proposals")

    def __init__(
        self,
        criteria: PolicyPromotionCriteria | None = None,
    ) -> None:
        self._criteria = criteria or PolicyPromotionCriteria()
        self._proposals: dict[str, PolicyChangeProposal] = {}

    @property
    def criteria(self) -> PolicyPromotionCriteria:
        return self._criteria

    def identify_promotion_candidates(
        self,
        report: ProjectionAnalysisReport,
    ) -> tuple[PolicyPromotionCandidate, ...]:
        """분석 보고서에서 승격 후보 식별."""
        candidates: list[PolicyPromotionCandidate] = []

        for cov in report.level_coverage:
            meets, reasons = self._criteria.evaluate(cov)
            score = self._calculate_promotion_score(cov)

            candidates.append(PolicyPromotionCandidate(
                level=cov.level,
                coverage=cov,
                meets_criteria=meets,
                failure_reasons=tuple(reasons),
                score=score,
            ))

        return tuple(sorted(candidates, key=lambda c: -c.score))

    def identify_deprecation_candidates(
        self,
        report: ProjectionAnalysisReport,
    ) -> tuple[PolicyDeprecationCandidate, ...]:
        """분석 보고서에서 폐기 후보 식별."""
        from ea_projection.projection_analyzer import LevelCoverageGrade

        candidates: list[PolicyDeprecationCandidate] = []

        for cov in report.level_coverage:
            reasons: list[str] = []
            severity = "low"

            if cov.grade == LevelCoverageGrade.UNCOVERED:
                reasons.append(
                    "Level has no projections recorded (UNCOVERED)"
                )
                severity = "high"
            elif cov.grade == LevelCoverageGrade.SPARSE:
                reasons.append(
                    "Level has very few or mostly stale projections (SPARSE)"
                )
                severity = "medium"

            if cov.stale_rate > 0.5:
                reasons.append(
                    f"Very high stale rate: {cov.stale_rate:.2%}"
                )
                if severity != "critical":
                    severity = "critical" if severity == "high" else "high"

            if reasons:
                candidates.append(PolicyDeprecationCandidate(
                    level=cov.level,
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
        proposal_type: PolicyProposalType,
        level: str,
        proposed_by: str,
        rationale: str,
        evidence_report_id: str = "",
        required_approvals: int = 1,
    ) -> PolicyChangeProposal:
        """변경 제안 생성."""
        now = _utc_now_iso()
        proposal_id = f"proposal-{uuid.uuid4().hex[:8]}"

        proposal = PolicyChangeProposal(
            proposal_id=proposal_id,
            proposal_type=proposal_type,
            level=level,
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
    ) -> PolicyChangeProposal:
        """제안에 투표."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.is_resolved:
            raise ValueError(
                f"Proposal {proposal_id} is already resolved"
            )

        now = _utc_now_iso()
        vote = PolicyProposalVote(
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
    ) -> PolicyChangeProposal:
        """제안 승인."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.is_resolved:
            raise ValueError(
                f"Proposal {proposal_id} is already resolved"
            )

        resolved = proposal.resolve(
            PolicyProposalStatus.APPROVED, approved_by, comment,
        )
        self._proposals[proposal_id] = resolved
        return resolved

    def reject_proposal(
        self,
        proposal_id: str,
        rejected_by: str,
        comment: str = "",
    ) -> PolicyChangeProposal:
        """제안 거부."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.is_resolved:
            raise ValueError(
                f"Proposal {proposal_id} is already resolved"
            )

        resolved = proposal.resolve(
            PolicyProposalStatus.REJECTED, rejected_by, comment,
        )
        self._proposals[proposal_id] = resolved
        return resolved

    def apply_proposal(
        self,
        proposal_id: str,
        applied_by: str,
    ) -> PolicyChangeProposal:
        """승인된 제안 적용."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.status != PolicyProposalStatus.APPROVED:
            raise ValueError(
                f"Proposal must be APPROVED to apply, got {proposal.status}"
            )

        applied = proposal.resolve(
            PolicyProposalStatus.APPLIED, applied_by, "Applied",
        )
        self._proposals[proposal_id] = applied
        return applied

    def get_proposal(
        self, proposal_id: str,
    ) -> PolicyChangeProposal | None:
        return self._proposals.get(proposal_id)

    def list_proposals(
        self,
        status: PolicyProposalStatus | None = None,
    ) -> tuple[PolicyChangeProposal, ...]:
        if status is None:
            return tuple(self._proposals.values())
        return tuple(
            p for p in self._proposals.values() if p.status == status
        )

    def _calculate_promotion_score(
        self,
        cov: LevelCoverage,
    ) -> float:
        """승격 점수 계산 (0-100)."""
        score = 0.0

        # Projection volume (0-30)
        score += min(30, cov.total_projections * 3)

        # Freshness rate (0-40)
        score += cov.freshness_rate * 40

        # Low stale rate (0-15)
        score += (1 - cov.stale_rate) * 15

        # Filter effectiveness (0-15)
        score += min(15, cov.avg_filter_reduction_rate * 30)

        return min(100, max(0, score))
