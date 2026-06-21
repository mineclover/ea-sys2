"""Scenario Bridge — Converters from ea-needs Scenario to ea-flow Specs.

Converts ScenarioFlow and UseCase from the needs layer into
UseCaseSpec and ProcessSpec for the flow layer.

Provides:
- SimpleStepSpec: Lightweight step spec for non-kernel-grounded steps
- scenario_to_use_case_spec: Convert UseCase + ScenarioFlow -> UseCaseSpec
- scenarios_to_process_spec: Convert UseCase + scenarios -> ProcessSpec

References:
- ea_flow/spec.py: UseCaseSpec, KernelGroundedStepSpec, FlowMetaStep
- ea_flow/topology.py: ProcessSpec, StepDefinition, LogicCondition
- ea_needs/types.py: UseCase, ScenarioFlow, ScenarioStep, ScenarioType
"""

from __future__ import annotations

from ea_flow.spec import (
    FlowMetaStep,
    KernelGroundedStepSpec,
    StepSpec,
    UseCaseSpec,
)
from ea_flow.topology import (
    LogicCondition,
    ProcessSpec,
    StepDefinition,
)
from ea_flow.types import FlowStepCategory
from ea_needs.types import ScenarioFlow, ScenarioStep, ScenarioType, UseCase


# ═══════════════════════════════════════════════════════════════════════════════
# SimpleStepSpec — Non-kernel-grounded step
# ═══════════════════════════════════════════════════════════════════════════════

class SimpleStepSpec(StepSpec):
    """A step spec for scenario steps without kernel references."""

    def __init__(self, step_name: str) -> None:
        self._name = step_name

    @property
    def name(self) -> str:
        return self._name

    @property
    def kernel_anchor(self) -> str | None:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# scenario_to_use_case_spec
# ═══════════════════════════════════════════════════════════════════════════════

def scenario_to_use_case_spec(
    use_case: UseCase,
    scenario: ScenarioFlow,
    meta_step_registry: dict[str, FlowMetaStep] | None = None,
) -> UseCaseSpec:
    """Convert a UseCase and ScenarioFlow into a UseCaseSpec.

    Args:
        use_case: The use case from the needs layer.
        scenario: The scenario flow describing interaction steps.
        meta_step_registry: Optional registry mapping actor names to FlowMetaStep.

    Returns:
        UseCaseSpec with all steps in order.
    """
    if meta_step_registry is None:
        meta_step_registry = {}

    steps: list[StepSpec] = []

    for step in scenario.steps:
        steps.append(_convert_scenario_step(step, meta_step_registry))

    success_criteria: list[str] = list(use_case.postconditions)

    return UseCaseSpec(
        name=use_case.title,
        description=use_case.purpose,
        primary_actor=use_case.actor,
        success_criteria=success_criteria,
        steps=steps,
        kernel_anchor=use_case.id,
    )


def _convert_scenario_step(
    step: ScenarioStep,
    meta_step_registry: dict[str, FlowMetaStep],
) -> StepSpec:
    """Convert a single ScenarioStep into a StepSpec."""
    if step.kernel_ref is not None:
        meta = meta_step_registry.get(step.actor)
        if meta is None:
            meta = FlowMetaStep(
                name=step.actor,
                description=step.action,
            )
        return KernelGroundedStepSpec(
            anchor=step.kernel_ref,
            meta_type=meta,
        )
    return SimpleStepSpec(step_name=step.action)


# ═══════════════════════════════════════════════════════════════════════════════
# scenarios_to_process_spec
# ═══════════════════════════════════════════════════════════════════════════════

def scenarios_to_process_spec(
    use_case: UseCase,
    scenarios: list[ScenarioFlow],
) -> ProcessSpec:
    """Convert a UseCase and its scenarios into a ProcessSpec.

    Args:
        use_case: The use case from the needs layer.
        scenarios: All scenario flows for this use case.

    Returns:
        ProcessSpec with linear chain + branching topology.

    Raises:
        ValueError: If there is not exactly one MAIN scenario.
        ValueError: If branch_from_step references invalid main steps.
        ValueError: If kernel_ref is an empty string.
    """
    # Validate: exactly one MAIN scenario
    main_scenarios = [
        s for s in scenarios if s.scenario_type == ScenarioType.MAIN
    ]
    if len(main_scenarios) != 1:
        raise ValueError(
            f"Expected exactly 1 MAIN scenario, got {len(main_scenarios)}"
        )

    main_scenario = main_scenarios[0]
    alt_scenarios = [
        s for s in scenarios if s.scenario_type == ScenarioType.ALTERNATIVE
    ]
    exc_scenarios = [
        s for s in scenarios if s.scenario_type == ScenarioType.EXCEPTION
    ]

    # Validate kernel_ref values
    for sc in scenarios:
        for step in sc.steps:
            if step.kernel_ref is not None and step.kernel_ref == "":
                raise ValueError(
                    f"kernel_ref must be non-empty if present, "
                    f"found empty string in scenario '{sc.id}' "
                    f"step order {step.order}"
                )

    # Build main chain step definitions
    main_steps = _build_main_chain(use_case, main_scenario)

    # Build a mapping from main step order -> step definition ID
    main_order_to_id: dict[int, str] = {}
    main_order_to_idx: dict[int, int] = {}
    for idx, (step, step_def) in enumerate(
        zip(main_scenario.steps, main_steps, strict=True)
    ):
        main_order_to_id[step.order] = step_def.id
        main_order_to_idx[step.order] = idx

    # Validate branch_from_step references
    all_branch_scenarios = alt_scenarios + exc_scenarios
    for sc in all_branch_scenarios:
        if sc.branch_from_step is not None:
            if sc.branch_from_step not in main_order_to_id:
                raise ValueError(
                    f"branch_from_step {sc.branch_from_step} in scenario "
                    f"'{sc.id}' does not reference a valid main step. "
                    f"Valid orders: {sorted(main_order_to_id.keys())}"
                )

    # Process alternative scenarios
    alt_step_defs: list[StepDefinition] = []
    for sc in alt_scenarios:
        branch_steps = _build_branch_chain(use_case, sc, "alt")
        if branch_steps and sc.branch_from_step is not None:
            # Add branch to main step's next_step_ids
            main_idx = main_order_to_idx[sc.branch_from_step]
            main_step = main_steps[main_idx]
            # Add LogicCondition to the main step
            condition = LogicCondition(
                expression=sc.trigger or sc.title,
                engine="scenario",
            )
            main_steps[main_idx] = StepDefinition(
                id=main_step.id,
                name=main_step.name,
                category=main_step.category,
                description=main_step.description,
                condition=condition,
                transformation=main_step.transformation,
                schema_usage=main_step.schema_usage,
                next_step_ids=[*main_step.next_step_ids, branch_steps[0].id],
                on_failure_step_id=main_step.on_failure_step_id,
            )
        alt_step_defs.extend(branch_steps)

    # Process exception scenarios
    exc_step_defs: list[StepDefinition] = []
    for sc in exc_scenarios:
        branch_steps = _build_branch_chain(use_case, sc, "exc")
        if branch_steps and sc.branch_from_step is not None:
            main_idx = main_order_to_idx[sc.branch_from_step]
            main_step = main_steps[main_idx]
            main_steps[main_idx] = StepDefinition(
                id=main_step.id,
                name=main_step.name,
                category=main_step.category,
                description=main_step.description,
                condition=main_step.condition,
                transformation=main_step.transformation,
                schema_usage=main_step.schema_usage,
                next_step_ids=main_step.next_step_ids,
                on_failure_step_id=branch_steps[0].id,
            )
        exc_step_defs.extend(branch_steps)

    all_steps = main_steps + alt_step_defs + exc_step_defs

    return ProcessSpec(
        id=use_case.id,
        name=use_case.title,
        version=str(use_case.version),
        steps=all_steps,
    )


def _build_main_chain(
    use_case: UseCase,
    scenario: ScenarioFlow,
) -> list[StepDefinition]:
    """Build linear StepDefinition chain for the MAIN scenario."""
    steps: list[StepDefinition] = []
    sorted_scenario_steps = sorted(scenario.steps, key=lambda s: s.order)

    for i, step in enumerate(sorted_scenario_steps):
        step_id = f"{use_case.id}-main-step-{step.order}"
        next_step_ids: list[str] = []
        if i < len(sorted_scenario_steps) - 1:
            next_step = sorted_scenario_steps[i + 1]
            next_step_ids = [f"{use_case.id}-main-step-{next_step.order}"]

        steps.append(StepDefinition(
            id=step_id,
            name=step.action,
            category=FlowStepCategory.ACTION,
            description=f"{step.actor}: {step.action} -> {step.system_response}",
            next_step_ids=next_step_ids,
        ))

    return steps


def _build_branch_chain(
    use_case: UseCase,
    scenario: ScenarioFlow,
    branch_prefix: str,
) -> list[StepDefinition]:
    """Build StepDefinition chain for a branch scenario."""
    steps: list[StepDefinition] = []
    sorted_scenario_steps = sorted(scenario.steps, key=lambda s: s.order)

    for i, step in enumerate(sorted_scenario_steps):
        step_id = f"{use_case.id}-{branch_prefix}-{scenario.id}-step-{step.order}"
        next_step_ids: list[str] = []
        if i < len(sorted_scenario_steps) - 1:
            next_step = sorted_scenario_steps[i + 1]
            next_step_ids = [
                f"{use_case.id}-{branch_prefix}-{scenario.id}-step-{next_step.order}"
            ]

        steps.append(StepDefinition(
            id=step_id,
            name=step.action,
            category=FlowStepCategory.ACTION,
            description=f"{step.actor}: {step.action} -> {step.system_response}",
            next_step_ids=next_step_ids,
        ))

    return steps
