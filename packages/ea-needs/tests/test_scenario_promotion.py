"""Tests for ScenarioPromotionEngine — S5 Evolution for Scenario Flows."""

from __future__ import annotations

from ea_needs.scenario_analyzer import ScenarioCoverage
from ea_needs.scenario_promotion import (
    ScenarioChangeProposal,
    ScenarioPromotionCriteria,
    ScenarioPromotionEngine,
    ScenarioVote,
)


def _make_coverage(
    use_case_id: str = "uc-001",
    total_scenarios: int = 3,
    main_count: int = 1,
    alternative_count: int = 1,
    exception_count: int = 1,
    total_steps: int = 10,
    kernel_grounded_steps: int = 8,
) -> ScenarioCoverage:
    return ScenarioCoverage(
        use_case_id=use_case_id,
        total_scenarios=total_scenarios,
        main_count=main_count,
        alternative_count=alternative_count,
        exception_count=exception_count,
        total_steps=total_steps,
        kernel_grounded_steps=kernel_grounded_steps,
    )


class TestScenarioPromotionEngine:
    """Tests for ScenarioPromotionEngine."""

    def test_identify_promotion_candidates_complete_coverage(self) -> None:
        """AC-27: Identify promotion candidates with complete coverage."""
        engine = ScenarioPromotionEngine()
        coverages = (
            _make_coverage(
                use_case_id="uc-001",
                total_scenarios=3,
                main_count=1,
                total_steps=10,
                kernel_grounded_steps=9,
            ),
        )

        candidates = engine.identify_promotion_candidates(coverages)

        assert len(candidates) == 1
        assert candidates[0].use_case_id == "uc-001"
        assert candidates[0].scenario_count == 3
        assert candidates[0].kernel_ref_rate == 0.9
        assert candidates[0].has_main is True

    def test_identify_promotion_candidates_below_threshold(self) -> None:
        """Use case with low kernel_ref_rate should not be promoted."""
        engine = ScenarioPromotionEngine()
        coverages = (
            _make_coverage(
                use_case_id="uc-001",
                total_scenarios=3,
                main_count=1,
                total_steps=10,
                kernel_grounded_steps=2,  # 0.2 < 0.8
            ),
        )

        candidates = engine.identify_promotion_candidates(coverages)
        assert len(candidates) == 0

    def test_identify_promotion_candidates_no_main(self) -> None:
        """Use case without MAIN scenario should not be promoted (default)."""
        engine = ScenarioPromotionEngine()
        coverages = (
            _make_coverage(
                use_case_id="uc-001",
                total_scenarios=3,
                main_count=0,
                total_steps=10,
                kernel_grounded_steps=9,
            ),
        )

        candidates = engine.identify_promotion_candidates(coverages)
        assert len(candidates) == 0

    def test_identify_promotion_candidates_no_main_optional(self) -> None:
        """With require_main_scenario=False, no-main can still be promoted."""
        criteria = ScenarioPromotionCriteria(require_main_scenario=False)
        engine = ScenarioPromotionEngine(criteria=criteria)
        coverages = (
            _make_coverage(
                use_case_id="uc-001",
                total_scenarios=3,
                main_count=0,
                total_steps=10,
                kernel_grounded_steps=9,
            ),
        )

        candidates = engine.identify_promotion_candidates(coverages)
        assert len(candidates) == 1

    def test_identify_deprecation_candidates_zero_kernel_refs(self) -> None:
        """Use case with 0 kernel refs should be deprecated."""
        engine = ScenarioPromotionEngine()
        coverages = (
            _make_coverage(
                use_case_id="uc-bad",
                total_steps=5,
                kernel_grounded_steps=0,
            ),
        )

        candidates = engine.identify_deprecation_candidates(coverages)
        assert len(candidates) == 1
        assert candidates[0].use_case_id == "uc-bad"
        assert "kernel_ref_rate=0.0" in candidates[0].reason

    def test_identify_deprecation_candidates_no_main(self) -> None:
        """Use case without MAIN should be deprecated."""
        engine = ScenarioPromotionEngine()
        coverages = (
            _make_coverage(
                use_case_id="uc-no-main",
                main_count=0,
                total_steps=5,
                kernel_grounded_steps=5,
            ),
        )

        candidates = engine.identify_deprecation_candidates(coverages)
        assert len(candidates) == 1
        assert "No MAIN scenario" in candidates[0].reason

    def test_create_proposal(self) -> None:
        """Test proposal creation workflow."""
        engine = ScenarioPromotionEngine()
        coverages = (
            _make_coverage(
                use_case_id="uc-good",
                total_scenarios=3,
                main_count=1,
                total_steps=10,
                kernel_grounded_steps=9,
            ),
            _make_coverage(
                use_case_id="uc-bad",
                total_scenarios=1,
                main_count=0,
                total_steps=5,
                kernel_grounded_steps=0,
            ),
        )

        proposal = engine.create_proposal(coverages)

        assert proposal.proposal_id.startswith("scenario-proposal-")
        assert proposal.created_at != ""
        assert proposal.status == "PENDING"
        assert len(proposal.promotion_candidates) == 1
        assert proposal.promotion_candidates[0].use_case_id == "uc-good"
        assert len(proposal.deprecation_candidates) == 1
        assert proposal.deprecation_candidates[0].use_case_id == "uc-bad"

    def test_proposal_voting_workflow(self) -> None:
        """Test voting on a change proposal."""
        engine = ScenarioPromotionEngine()
        coverages = (
            _make_coverage(use_case_id="uc-001"),
        )

        proposal = engine.create_proposal(coverages)
        assert proposal.approval_count == 0
        assert proposal.rejection_count == 0

        # Add approval vote
        vote1 = ScenarioVote(voter="alice", approve=True, comment="LGTM")
        proposal.add_vote(vote1)
        assert proposal.approval_count == 1

        # Add rejection vote
        vote2 = ScenarioVote(voter="bob", approve=False, comment="Need more review")
        proposal.add_vote(vote2)
        assert proposal.rejection_count == 1

        # Approve the proposal
        proposal.approve()
        assert proposal.status == "APPROVED"

    def test_proposal_reject(self) -> None:
        engine = ScenarioPromotionEngine()
        proposal = engine.create_proposal(())
        proposal.reject()
        assert proposal.status == "REJECTED"

    def test_custom_criteria(self) -> None:
        criteria = ScenarioPromotionCriteria(
            min_scenarios=5,
            min_kernel_ref_rate=0.9,
        )
        engine = ScenarioPromotionEngine(criteria=criteria)

        coverages = (
            _make_coverage(
                total_scenarios=3,  # below min_scenarios=5
                total_steps=10,
                kernel_grounded_steps=10,
            ),
        )

        candidates = engine.identify_promotion_candidates(coverages)
        assert len(candidates) == 0
