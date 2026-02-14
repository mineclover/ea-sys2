"""Promotion Engine — Phase 3 Governance (S5 Evolution).

Rule promotion and change proposal management.
Provides:
- PromotionCriteria: 승격 기준 표현식
- RuleChangeProposal: 규칙 변경 제안
- PromotionEngine: 승격 엔진

References:
- governance_lifecycle.toml: Evolution 레이어 (PromotionEngine, PromotionCriteria)
- governance_lifecycle.md: S5 Rule Evolution
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_kernel.evidence_analyzer import AnalysisReport, RuleEffectiveness
    from ea_kernel.rule_asset_store import RuleAssetStore


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _utc_now_iso() -> str:
    return _utc_now_naive().isoformat() + "Z"


# ═══════════════════════════════════════════════════════════════════════════════
# Promotion Criteria — 승격 기준
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PromotionCriteria:
    """규칙 승격 기준.

    governance_lifecycle.toml의 PromotionCriteria(expression) 매핑.
    """
    # Minimum evaluation counts
    min_evaluations: int = 50
    min_matches: int = 20
    min_wins: int = 10

    # Rate thresholds
    max_override_rate: float = 0.1  # 10% 이하여야 승격
    max_shadow_rate: float = 0.3   # 30% 이하여야 승격
    min_win_rate: float = 0.5      # 50% 이상이어야 승격

    # Time requirements (in days)
    min_age_days: int = 7  # 최소 7일 경과 후 승격 가능

    def evaluate(
        self,
        effectiveness: RuleEffectiveness,
        created_at: str,
    ) -> tuple[bool, list[str]]:
        """승격 기준 평가.

        Args:
            effectiveness: 규칙 실효성 데이터
            created_at: 규칙 생성 시각 (ISO 8601)

        Returns:
            (승격 가능 여부, 불충족 사유 목록)
        """
        reasons: list[str] = []

        # Evaluation counts
        if effectiveness.total_evaluations < self.min_evaluations:
            reasons.append(
                f"Insufficient evaluations: {effectiveness.total_evaluations} < {self.min_evaluations}"
            )

        if effectiveness.match_count < self.min_matches:
            reasons.append(
                f"Insufficient matches: {effectiveness.match_count} < {self.min_matches}"
            )

        if effectiveness.win_count < self.min_wins:
            reasons.append(
                f"Insufficient wins: {effectiveness.win_count} < {self.min_wins}"
            )

        # Rate thresholds
        if effectiveness.override_rate > self.max_override_rate:
            reasons.append(
                f"Override rate too high: {effectiveness.override_rate:.2%} > {self.max_override_rate:.2%}"
            )

        if effectiveness.shadow_rate > self.max_shadow_rate:
            reasons.append(
                f"Shadow rate too high: {effectiveness.shadow_rate:.2%} > {self.max_shadow_rate:.2%}"
            )

        if effectiveness.win_rate < self.min_win_rate:
            reasons.append(
                f"Win rate too low: {effectiveness.win_rate:.2%} < {self.min_win_rate:.2%}"
            )

        # Age check
        try:
            created = datetime.fromisoformat(created_at.rstrip("Z"))
            now = _utc_now_naive()
            age_days = (now - created).days
            if age_days < self.min_age_days:
                reasons.append(
                    f"Rule too young: {age_days} days < {self.min_age_days} days"
                )
        except (ValueError, TypeError):
            # If we can't parse the date, skip age check
            pass

        return (len(reasons) == 0, reasons)


# ═══════════════════════════════════════════════════════════════════════════════
# Rule Change Proposal — 규칙 변경 제안
# ═══════════════════════════════════════════════════════════════════════════════

class ProposalType(StrEnum):
    """변경 제안 유형."""
    PROMOTE = "promote"           # Empirical → Approved 승격
    DEPRECATE = "deprecate"       # Approved → Deprecated 폐기
    MODIFY = "modify"             # 규칙 내용 수정
    CREATE = "create"             # 새 규칙 생성


class ProposalStatus(StrEnum):
    """변경 제안 상태."""
    PENDING = "pending"           # 검토 대기
    APPROVED = "approved"         # 승인됨
    REJECTED = "rejected"         # 거부됨
    APPLIED = "applied"           # 적용 완료
    WITHDRAWN = "withdrawn"       # 철회됨


@dataclass(frozen=True)
class ProposalVote:
    """투표 기록."""
    voter: str
    approve: bool
    timestamp: str
    comment: str = ""


@dataclass(frozen=True)
class RuleChangeProposal:
    """규칙 변경 제안.

    governance_lifecycle.toml의 RuleChangeProposal(item) 매핑.
    """
    proposal_id: str
    proposal_type: ProposalType
    rule_id: str

    # Proposer info
    proposed_by: str
    proposed_at: str

    # Status
    status: ProposalStatus = ProposalStatus.PENDING

    # Justification
    rationale: str = ""
    evidence_report_id: str = ""  # AnalysisReport ID reference

    # Voting
    votes: tuple[ProposalVote, ...] = ()
    required_approvals: int = 1

    # Resolution
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
        return self.status not in (ProposalStatus.PENDING,)

    def with_vote(self, vote: ProposalVote) -> RuleChangeProposal:
        """새 투표 추가."""
        return RuleChangeProposal(
            proposal_id=self.proposal_id,
            proposal_type=self.proposal_type,
            rule_id=self.rule_id,
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
        status: ProposalStatus,
        resolved_by: str,
        comment: str = "",
    ) -> RuleChangeProposal:
        """제안 해결."""
        now = _utc_now_iso()
        return RuleChangeProposal(
            proposal_id=self.proposal_id,
            proposal_type=self.proposal_type,
            rule_id=self.rule_id,
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
# Promotion Engine — 승격 엔진
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PromotionCandidate:
    """승격 후보."""
    rule_id: str
    effectiveness: RuleEffectiveness
    meets_criteria: bool
    failure_reasons: tuple[str, ...]
    score: float  # 0-100, higher is better


@dataclass(frozen=True)
class DeprecationCandidate:
    """폐기 후보."""
    rule_id: str
    effectiveness: RuleEffectiveness
    deprecation_reasons: tuple[str, ...]
    severity: str  # "critical", "high", "medium", "low"


class PromotionEngine:
    """승격 엔진.

    governance_lifecycle.toml의 PromotionEngine(structure) 매핑.
    AnalysisReport 기반으로 승격/폐기 후보 식별.
    """

    __slots__ = ("_asset_store", "_criteria", "_proposals")

    def __init__(
        self,
        asset_store: RuleAssetStore,
        criteria: PromotionCriteria | None = None,
    ) -> None:
        self._asset_store = asset_store
        self._criteria = criteria or PromotionCriteria()
        self._proposals: dict[str, RuleChangeProposal] = {}

    @property
    def criteria(self) -> PromotionCriteria:
        return self._criteria

    def identify_promotion_candidates(
        self,
        report: AnalysisReport,
    ) -> tuple[PromotionCandidate, ...]:
        """분석 보고서에서 승격 후보 식별.

        Args:
            report: AnalysisReport from EvidenceAnalyzer

        Returns:
            승격 후보 목록 (점수 내림차순)
        """
        from ea_kernel.governance_types import RuleLifecycleState

        candidates: list[PromotionCandidate] = []

        # Get rules that are in REVIEW state (candidates for promotion)
        review_rules = self._asset_store.list_by_state(RuleLifecycleState.REVIEW)
        review_rule_ids = {r.id for r in review_rules}

        for eff in report.rule_effectiveness:
            # Only consider rules in REVIEW state
            if eff.rule_id not in review_rule_ids:
                continue

            # Get the asset to check creation time
            asset = self._asset_store.get(eff.rule_id)
            if asset is None:
                continue

            meets, reasons = self._criteria.evaluate(
                eff,
                asset.provenance.created_at,
            )

            # Calculate score
            score = self._calculate_promotion_score(eff)

            candidates.append(PromotionCandidate(
                rule_id=eff.rule_id,
                effectiveness=eff,
                meets_criteria=meets,
                failure_reasons=tuple(reasons),
                score=score,
            ))

        return tuple(sorted(candidates, key=lambda c: -c.score))

    def identify_deprecation_candidates(
        self,
        report: AnalysisReport,
    ) -> tuple[DeprecationCandidate, ...]:
        """분석 보고서에서 폐기 후보 식별.

        Args:
            report: AnalysisReport from EvidenceAnalyzer

        Returns:
            폐기 후보 목록 (심각도 순)
        """
        from ea_kernel.evidence_analyzer import EffectivenessGrade
        from ea_kernel.governance_types import RuleLifecycleState

        candidates: list[DeprecationCandidate] = []

        # Get approved rules
        approved_rules = self._asset_store.list_by_state(RuleLifecycleState.APPROVED)
        approved_ids = {r.id for r in approved_rules}

        for eff in report.rule_effectiveness:
            if eff.rule_id not in approved_ids:
                continue

            reasons: list[str] = []
            severity = "low"

            # Check for deprecation indicators
            if eff.grade == EffectivenessGrade.DEAD:
                reasons.append("Rule has never been evaluated (DEAD)")
                severity = "high"
            elif eff.grade == EffectivenessGrade.SHADOWED:
                reasons.append("Rule is always shadowed by higher priority rules")
                severity = "medium"
            elif eff.grade == EffectivenessGrade.INEFFECTIVE:
                reasons.append("Rule is frequently overridden or never wins")
                severity = "medium"

            # High override rate
            if eff.override_rate > 0.5:
                reasons.append(f"Very high override rate: {eff.override_rate:.2%}")
                severity = "critical" if severity == "high" else "high"

            if reasons:
                candidates.append(DeprecationCandidate(
                    rule_id=eff.rule_id,
                    effectiveness=eff,
                    deprecation_reasons=tuple(reasons),
                    severity=severity,
                ))

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return tuple(sorted(
            candidates,
            key=lambda c: severity_order.get(c.severity, 4)
        ))

    def create_proposal(
        self,
        proposal_type: ProposalType,
        rule_id: str,
        proposed_by: str,
        rationale: str,
        evidence_report_id: str = "",
        required_approvals: int = 1,
    ) -> RuleChangeProposal:
        """변경 제안 생성.

        Args:
            proposal_type: 제안 유형
            rule_id: 대상 규칙 ID
            proposed_by: 제안자
            rationale: 제안 사유
            evidence_report_id: 근거 보고서 ID
            required_approvals: 필요 승인 수

        Returns:
            생성된 RuleChangeProposal
        """
        import uuid

        now = _utc_now_iso()
        proposal_id = f"proposal-{uuid.uuid4().hex[:8]}"

        proposal = RuleChangeProposal(
            proposal_id=proposal_id,
            proposal_type=proposal_type,
            rule_id=rule_id,
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
    ) -> RuleChangeProposal:
        """제안에 투표.

        Args:
            proposal_id: 제안 ID
            voter: 투표자
            approve: 승인 여부
            comment: 투표 코멘트

        Returns:
            업데이트된 RuleChangeProposal

        Raises:
            ValueError: 제안이 없거나 이미 해결됨
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.is_resolved:
            raise ValueError(f"Proposal {proposal_id} is already resolved")

        now = _utc_now_iso()
        vote = ProposalVote(
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
    ) -> RuleChangeProposal:
        """제안 승인.

        Args:
            proposal_id: 제안 ID
            approved_by: 승인자
            comment: 승인 코멘트

        Returns:
            업데이트된 RuleChangeProposal

        Raises:
            ValueError: 제안이 없거나 이미 해결됨
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.is_resolved:
            raise ValueError(f"Proposal {proposal_id} is already resolved")

        resolved = proposal.resolve(
            ProposalStatus.APPROVED,
            approved_by,
            comment,
        )
        self._proposals[proposal_id] = resolved
        return resolved

    def reject_proposal(
        self,
        proposal_id: str,
        rejected_by: str,
        comment: str = "",
    ) -> RuleChangeProposal:
        """제안 거부."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.is_resolved:
            raise ValueError(f"Proposal {proposal_id} is already resolved")

        resolved = proposal.resolve(
            ProposalStatus.REJECTED,
            rejected_by,
            comment,
        )
        self._proposals[proposal_id] = resolved
        return resolved

    def apply_proposal(
        self,
        proposal_id: str,
        applied_by: str,
    ) -> RuleChangeProposal:
        """승인된 제안 적용.

        실제로 RuleAssetStore의 상태를 변경.

        Raises:
            ValueError: 제안이 APPROVED 상태가 아닌 경우
        """
        from ea_kernel.governance_types import RuleLifecycleState

        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.status != ProposalStatus.APPROVED:
            raise ValueError(f"Proposal must be APPROVED to apply, got {proposal.status}")

        # Apply the change based on proposal type
        if proposal.proposal_type == ProposalType.PROMOTE:
            self._asset_store.transition(
                proposal.rule_id,
                RuleLifecycleState.APPROVED,
                applied_by,
                f"Promoted via proposal {proposal_id}",
            )
        elif proposal.proposal_type == ProposalType.DEPRECATE:
            self._asset_store.transition(
                proposal.rule_id,
                RuleLifecycleState.DEPRECATED,
                applied_by,
                f"Deprecated via proposal {proposal_id}",
            )

        # Mark as applied
        applied = proposal.resolve(
            ProposalStatus.APPLIED,
            applied_by,
            "Applied to RuleAssetStore",
        )
        self._proposals[proposal_id] = applied
        return applied

    def get_proposal(self, proposal_id: str) -> RuleChangeProposal | None:
        return self._proposals.get(proposal_id)

    def list_proposals(
        self,
        status: ProposalStatus | None = None,
    ) -> tuple[RuleChangeProposal, ...]:
        """제안 목록 조회."""
        if status is None:
            return tuple(self._proposals.values())
        return tuple(p for p in self._proposals.values() if p.status == status)

    def _calculate_promotion_score(
        self,
        eff: RuleEffectiveness,
    ) -> float:
        """승격 점수 계산 (0-100).

        Higher is better:
        - More evaluations = higher score
        - Higher win rate = higher score
        - Lower override rate = higher score
        - Lower shadow rate = higher score
        """
        score = 0.0

        # Evaluation volume (0-30 points)
        eval_score = min(30, eff.total_evaluations / 10)
        score += eval_score

        # Win rate (0-40 points)
        score += eff.win_rate * 40

        # Low override rate (0-15 points)
        score += (1 - eff.override_rate) * 15

        # Low shadow rate (0-15 points)
        score += (1 - eff.shadow_rate) * 15

        return min(100, max(0, score))
