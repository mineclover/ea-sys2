"""Scenario Promotion Engine — S5 Evolution for Scenario Flows.

Scenario promotion, deprecation, and change proposal management.

Provides:
- ScenarioPromotionCriteria: Promotion threshold criteria
- ScenarioPromotionCandidate: Promotion candidate
- ScenarioDeprecationCandidate: Deprecation candidate
- ScenarioVote: Vote on a change proposal
- ScenarioChangeProposal: Change proposal with voting workflow
- ScenarioPromotionEngine: Promotion/deprecation engine

References:
- ea_needs/needs_promotion.py: S5 promotion pattern
- ea_needs/scenario_analyzer.py: S4 analysis types
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_needs.scenario_analyzer import ScenarioCoverage


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"


# ═══════════════════════════════════════════════════════════════════════════════
# Promotion Criteria
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ScenarioPromotionCriteria:
    """Promotion threshold criteria for scenario use cases."""
    min_scenarios: int = 2
    min_kernel_ref_rate: float = 0.8
    require_main_scenario: bool = True


# ═══════════════════════════════════════════════════════════════════════════════
# Promotion/Deprecation Candidates
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ScenarioPromotionCandidate:
    """A use case that qualifies for promotion."""
    use_case_id: str
    scenario_count: int
    kernel_ref_rate: float
    has_main: bool


@dataclass(frozen=True)
class ScenarioDeprecationCandidate:
    """A use case that should be deprecated."""
    use_case_id: str
    reason: str


# ═══════════════════════════════════════════════════════════════════════════════
# Voting
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ScenarioVote:
    """A vote on a change proposal."""
    voter: str
    approve: bool
    comment: str = ""
    voted_at: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Change Proposal
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ScenarioChangeProposal:
    """A change proposal with voting workflow."""
    proposal_id: str
    created_at: str
    promotion_candidates: tuple[ScenarioPromotionCandidate, ...]
    deprecation_candidates: tuple[ScenarioDeprecationCandidate, ...]
    votes: list[ScenarioVote] = field(default_factory=list)
    status: str = "PENDING"

    @property
    def approval_count(self) -> int:
        return sum(1 for v in self.votes if v.approve)

    @property
    def rejection_count(self) -> int:
        return sum(1 for v in self.votes if not v.approve)

    def add_vote(self, vote: ScenarioVote) -> None:
        """Add a vote to the proposal."""
        self.votes.append(vote)

    def approve(self) -> None:
        """Approve the proposal."""
        self.status = "APPROVED"

    def reject(self) -> None:
        """Reject the proposal."""
        self.status = "REJECTED"


# ═══════════════════════════════════════════════════════════════════════════════
# ScenarioPromotionEngine
# ═══════════════════════════════════════════════════════════════════════════════

class ScenarioPromotionEngine:
    """Scenario promotion engine.

    Identifies promotion and deprecation candidates from ScenarioCoverage
    analysis and manages change proposals.
    """

    __slots__ = ("_criteria",)

    def __init__(
        self,
        criteria: ScenarioPromotionCriteria | None = None,
    ) -> None:
        self._criteria = criteria or ScenarioPromotionCriteria()

    @property
    def criteria(self) -> ScenarioPromotionCriteria:
        return self._criteria

    def identify_promotion_candidates(
        self,
        coverages: tuple[ScenarioCoverage, ...],
    ) -> tuple[ScenarioPromotionCandidate, ...]:
        """Identify use cases that qualify for promotion."""
        candidates: list[ScenarioPromotionCandidate] = []

        for cov in coverages:
            kernel_ref_rate = (
                cov.kernel_grounded_steps / cov.total_steps
                if cov.total_steps > 0
                else 0.0
            )
            has_main = cov.main_count > 0

            meets_criteria = (
                cov.total_scenarios >= self._criteria.min_scenarios
                and kernel_ref_rate >= self._criteria.min_kernel_ref_rate
                and (has_main or not self._criteria.require_main_scenario)
            )

            if meets_criteria:
                candidates.append(ScenarioPromotionCandidate(
                    use_case_id=cov.use_case_id,
                    scenario_count=cov.total_scenarios,
                    kernel_ref_rate=kernel_ref_rate,
                    has_main=has_main,
                ))

        return tuple(sorted(
            candidates,
            key=lambda c: -c.kernel_ref_rate,
        ))

    def identify_deprecation_candidates(
        self,
        coverages: tuple[ScenarioCoverage, ...],
    ) -> tuple[ScenarioDeprecationCandidate, ...]:
        """Identify use cases that should be deprecated."""
        candidates: list[ScenarioDeprecationCandidate] = []

        for cov in coverages:
            kernel_ref_rate = (
                cov.kernel_grounded_steps / cov.total_steps
                if cov.total_steps > 0
                else 0.0
            )

            if cov.kernel_grounded_steps == 0 and cov.total_steps > 0:
                candidates.append(ScenarioDeprecationCandidate(
                    use_case_id=cov.use_case_id,
                    reason=(
                        f"No kernel references in {cov.total_steps} steps "
                        f"(kernel_ref_rate=0.0)"
                    ),
                ))
            elif cov.main_count == 0 and self._criteria.require_main_scenario:
                candidates.append(ScenarioDeprecationCandidate(
                    use_case_id=cov.use_case_id,
                    reason="No MAIN scenario defined",
                ))

        return tuple(candidates)

    def create_proposal(
        self,
        coverages: tuple[ScenarioCoverage, ...],
    ) -> ScenarioChangeProposal:
        """Create a change proposal from coverage analysis."""
        now = _utc_now_iso()
        proposal_id = f"scenario-proposal-{uuid.uuid4().hex[:8]}"

        promotion = self.identify_promotion_candidates(coverages)
        deprecation = self.identify_deprecation_candidates(coverages)

        return ScenarioChangeProposal(
            proposal_id=proposal_id,
            created_at=now,
            promotion_candidates=promotion,
            deprecation_candidates=deprecation,
        )
