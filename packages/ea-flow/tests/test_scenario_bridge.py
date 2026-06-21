"""Tests for scenario_bridge — converters from ea-needs to ea-flow."""

from __future__ import annotations

import pytest

from ea_flow.scenario_bridge import (
    SimpleStepSpec,
    scenario_to_use_case_spec,
    scenarios_to_process_spec,
)
from ea_flow.spec import FlowMetaStep, KernelGroundedStepSpec
from ea_needs.types import ScenarioFlow, ScenarioStep, ScenarioType, UseCase


def _make_use_case(
    uc_id: str = "uc-001",
    title: str = "Register User",
    actor: str = "User",
    purpose: str = "Allow user registration",
    postconditions: tuple[str, ...] = ("User account created",),
) -> UseCase:
    return UseCase(
        id=uc_id,
        title=title,
        actor=actor,
        situation="User visits registration page",
        purpose=purpose,
        postconditions=postconditions,
    )


def _make_main_scenario(
    sc_id: str = "sc-main-001",
    use_case_id: str = "uc-001",
    steps: tuple[ScenarioStep, ...] | None = None,
) -> ScenarioFlow:
    if steps is None:
        steps = (
            ScenarioStep(order=1, actor="User", action="Fill form", system_response="Show form", kernel_ref="k-form"),
            ScenarioStep(order=2, actor="System", action="Validate data", system_response="Data valid", kernel_ref="k-validate"),
            ScenarioStep(order=3, actor="System", action="Create account", system_response="Account created"),
        )
    return ScenarioFlow(
        id=sc_id,
        use_case_id=use_case_id,
        title="Main Registration Flow",
        scenario_type=ScenarioType.MAIN,
        steps=steps,
        preconditions=("User is not logged in",),
        postconditions=("User account exists",),
        trigger="User clicks register",
    )


def _make_alt_scenario(
    sc_id: str = "sc-alt-001",
    use_case_id: str = "uc-001",
    branch_from: int = 2,
) -> ScenarioFlow:
    return ScenarioFlow(
        id=sc_id,
        use_case_id=use_case_id,
        title="Email Already Exists",
        scenario_type=ScenarioType.ALTERNATIVE,
        steps=(
            ScenarioStep(order=1, actor="System", action="Show duplicate error", system_response="Error displayed"),
            ScenarioStep(order=2, actor="User", action="Change email", system_response="Form updated"),
        ),
        trigger="Email already registered",
        branch_from_step=branch_from,
    )


def _make_exc_scenario(
    sc_id: str = "sc-exc-001",
    use_case_id: str = "uc-001",
    branch_from: int = 2,
) -> ScenarioFlow:
    return ScenarioFlow(
        id=sc_id,
        use_case_id=use_case_id,
        title="Database Connection Failed",
        scenario_type=ScenarioType.EXCEPTION,
        steps=(
            ScenarioStep(order=1, actor="System", action="Log error", system_response="Error logged"),
            ScenarioStep(order=2, actor="System", action="Show error page", system_response="Error page shown"),
        ),
        trigger="DB connection timeout",
        branch_from_step=branch_from,
    )


class TestScenarioToUseCaseSpec:
    """Tests for scenario_to_use_case_spec."""

    def test_basic_conversion(self) -> None:
        """AC-20: Step count, primary_actor, kernel_anchor."""
        uc = _make_use_case()
        sc = _make_main_scenario()

        spec = scenario_to_use_case_spec(uc, sc)

        assert spec.name == "Register User"
        assert spec.primary_actor == "User"
        assert spec.description == "Allow user registration"
        assert spec.kernel_anchor == "uc-001"
        assert len(spec.get_steps()) == 3
        assert spec.success_criteria == ["User account created"]

    def test_kernel_grounded_steps(self) -> None:
        """Steps with kernel_ref produce KernelGroundedStepSpec."""
        uc = _make_use_case()
        sc = _make_main_scenario()

        spec = scenario_to_use_case_spec(uc, sc)
        steps = spec.get_steps()

        # First two steps have kernel_ref
        assert isinstance(steps[0], KernelGroundedStepSpec)
        assert steps[0].kernel_anchor == "k-form"
        assert isinstance(steps[1], KernelGroundedStepSpec)
        assert steps[1].kernel_anchor == "k-validate"

        # Third step has no kernel_ref
        assert isinstance(steps[2], SimpleStepSpec)
        assert steps[2].kernel_anchor is None

    def test_meta_step_registry_reuse(self) -> None:
        """When meta_step_registry has matching actor, reuse that FlowMetaStep."""
        uc = _make_use_case()
        sc = _make_main_scenario()
        registry = {
            "User": FlowMetaStep(name="UserAction", description="User-initiated action"),
        }

        spec = scenario_to_use_case_spec(uc, sc, meta_step_registry=registry)
        steps = spec.get_steps()

        # First step actor is "User" -> should use registry FlowMetaStep
        assert isinstance(steps[0], KernelGroundedStepSpec)
        assert steps[0].meta_type.name == "UserAction"

    def test_postconditions_as_success_criteria(self) -> None:
        uc = _make_use_case(postconditions=("Account created", "Email sent"))
        sc = _make_main_scenario()

        spec = scenario_to_use_case_spec(uc, sc)
        assert spec.success_criteria == ["Account created", "Email sent"]


class TestScenariosToProcessSpec:
    """Tests for scenarios_to_process_spec."""

    def test_linear_main_chain(self) -> None:
        """AC-21: Linear chain from MAIN scenario."""
        uc = _make_use_case()
        sc = _make_main_scenario()

        proc = scenarios_to_process_spec(uc, [sc])

        assert proc.id == "uc-001"
        assert proc.name == "Register User"
        assert len(proc.steps) == 3

        # Verify linear chain
        assert proc.steps[0].id == "uc-001-main-step-1"
        assert proc.steps[0].next_step_ids == ["uc-001-main-step-2"]
        assert proc.steps[1].id == "uc-001-main-step-2"
        assert proc.steps[1].next_step_ids == ["uc-001-main-step-3"]
        assert proc.steps[2].id == "uc-001-main-step-3"
        assert proc.steps[2].next_step_ids == []

    def test_alternative_scenario_branching(self) -> None:
        """AC-28: Alternative scenario generates LogicCondition branch."""
        uc = _make_use_case()
        main = _make_main_scenario()
        alt = _make_alt_scenario(branch_from=2)

        proc = scenarios_to_process_spec(uc, [main, alt])

        # Main chain + 2 alt steps = 5 total
        assert len(proc.steps) == 5

        # Main step 2 should have branching
        main_step_2 = proc.steps[1]
        assert main_step_2.id == "uc-001-main-step-2"
        # next_step_ids should include both main-step-3 and alt first step
        assert "uc-001-main-step-3" in main_step_2.next_step_ids
        alt_first_id = f"uc-001-alt-sc-alt-001-step-1"
        assert alt_first_id in main_step_2.next_step_ids

        # LogicCondition should be set
        assert main_step_2.condition is not None
        assert main_step_2.condition.engine == "scenario"
        assert main_step_2.condition.expression == "Email already registered"

    def test_exception_scenario_on_failure(self) -> None:
        """AC-29: Exception scenario generates on_failure_step_id."""
        uc = _make_use_case()
        main = _make_main_scenario()
        exc = _make_exc_scenario(branch_from=2)

        proc = scenarios_to_process_spec(uc, [main, exc])

        # Main chain + 2 exc steps = 5 total
        assert len(proc.steps) == 5

        # Main step 2 should have on_failure_step_id
        main_step_2 = proc.steps[1]
        assert main_step_2.id == "uc-001-main-step-2"
        exc_first_id = f"uc-001-exc-sc-exc-001-step-1"
        assert main_step_2.on_failure_step_id == exc_first_id

    def test_no_main_raises_value_error(self) -> None:
        """AC-22: No MAIN scenario raises ValueError."""
        uc = _make_use_case()
        alt = _make_alt_scenario()

        with pytest.raises(ValueError, match="Expected exactly 1 MAIN scenario"):
            scenarios_to_process_spec(uc, [alt])

    def test_multiple_main_raises_value_error(self) -> None:
        uc = _make_use_case()
        main1 = _make_main_scenario(sc_id="sc-main-001")
        main2 = _make_main_scenario(sc_id="sc-main-002")

        with pytest.raises(ValueError, match="Expected exactly 1 MAIN scenario"):
            scenarios_to_process_spec(uc, [main1, main2])

    def test_empty_kernel_ref_raises_value_error(self) -> None:
        """Empty kernel_ref string raises ValueError."""
        uc = _make_use_case()
        bad_steps = (
            ScenarioStep(order=1, actor="User", action="Do something", system_response="Done", kernel_ref=""),
        )
        main = _make_main_scenario(steps=bad_steps)

        with pytest.raises(ValueError, match="kernel_ref must be non-empty"):
            scenarios_to_process_spec(uc, [main])

    def test_combined_alt_and_exc_scenarios(self) -> None:
        """Test both alternative and exception scenarios together."""
        uc = _make_use_case()
        main = _make_main_scenario()
        alt = _make_alt_scenario(branch_from=2)
        exc = _make_exc_scenario(branch_from=1)

        proc = scenarios_to_process_spec(uc, [main, alt, exc])

        # 3 main + 2 alt + 2 exc = 7 steps
        assert len(proc.steps) == 7

        # Main step 2 has alt branch
        main_step_2 = proc.steps[1]
        assert main_step_2.condition is not None

        # Main step 1 has exc on_failure
        main_step_1 = proc.steps[0]
        assert main_step_1.on_failure_step_id is not None

    def test_invalid_branch_from_step_raises(self) -> None:
        """branch_from_step referencing non-existent main step raises."""
        uc = _make_use_case()
        main = _make_main_scenario()
        alt = _make_alt_scenario(branch_from=99)

        with pytest.raises(ValueError, match="does not reference a valid main step"):
            scenarios_to_process_spec(uc, [main, alt])
