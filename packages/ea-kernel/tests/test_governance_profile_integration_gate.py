"""US-010 governance-domain integration gate for M2 profile promotion."""

from __future__ import annotations

from ea_decision.lifecycle import (
    DecisionLifecycleState,
)
from ea_decision.lifecycle import (
    allowed_profile_targets as decision_allowed_profile_targets,
)
from ea_kernel.profiles.ea_sys import layer_path
from ea_kernel.profiles.ea_sys.layer_stack import (
    load_layer_stack_profile,
    ordered_layer_definitions,
    validate_loaded_layer_stack,
)
from ea_kernel.spec import KERNEL_SPEC
from ea_needs.lifecycle import allowed_profile_targets as needs_allowed_profile_targets
from ea_needs.types import NeedStatus
from ea_profile.composer import extend
from ea_profile.loader import load_profile
from ea_profile.profile_validator import validate_profile
from ea_profile.types import KernelProfile
from ea_projection.artifacts import ArtifactType
from ea_projection.profile_bridge import load_projection_profile

GOVERNANCE_DOMAIN_LAYERS = (
    "infra",
    "governance",
    "decision",
    "needs",
    "kernel",
    "flow",
    "projection",
)


def _normalize_state_token(token: str) -> str:
    normalized = token.strip()
    if "." in normalized:
        normalized = normalized.rsplit(".", 1)[-1]
    return normalized.upper()


def _expected_profile_targets(profile: KernelProfile, source_state: str) -> tuple[str, ...]:
    source = _normalize_state_token(source_state)
    wildcard_targets: set[str] = set()
    explicit_targets: set[str] = set()

    for transition in profile.state_transitions:
        from_state = _normalize_state_token(transition.from_state)
        to_state = _normalize_state_token(transition.to_state)
        if from_state == "*":
            wildcard_targets.add(to_state)
            continue
        if from_state == source:
            explicit_targets.add(to_state)

    return tuple(sorted(explicit_targets | wildcard_targets))


def _compose_governance_domain_profile() -> KernelProfile:
    loaded_profiles = [
        load_profile(layer_path(layer), KERNEL_SPEC)
        for layer in GOVERNANCE_DOMAIN_LAYERS
    ]
    combined = loaded_profiles[0]

    for profile in loaded_profiles[1:]:
        combined = extend(
            combined,
            name="EASystem-GovernanceDomain-Validation",
            version="0.1.0",
            add_elements=profile.elements,
            add_relations=profile.relations,
            add_state_transitions=profile.state_transitions,
            add_artifact_types=profile.artifact_types,
            add_process_units=profile.process_units,
            add_rules=profile.validity_rules,
        )

    layer_stack_profile = load_layer_stack_profile(validate=False)
    return extend(
        combined,
        name="EASystem-GovernanceDomain-Validation",
        version="0.1.0",
        layer_stack=layer_stack_profile.layer_stack,
    )


def test_decision_state_transitions_are_profile_derived() -> None:
    profile = load_profile(layer_path("decision"), KERNEL_SPEC)

    for state in DecisionLifecycleState:
        expected = _expected_profile_targets(profile, state.value)
        assert decision_allowed_profile_targets(state) == expected


def test_needs_state_transitions_are_profile_derived() -> None:
    profile = load_profile(layer_path("needs"), KERNEL_SPEC)

    for state in NeedStatus:
        expected = _expected_profile_targets(profile, state.value)
        assert needs_allowed_profile_targets(state) == expected


def test_projection_artifact_types_are_profile_derived() -> None:
    profile = load_projection_profile(layer_path("projection"), validate=False)

    declared = {artifact_type.name for artifact_type in profile.artifact_types}
    runtime = set(ArtifactType.names())

    assert declared <= runtime


def test_layer_stack_is_loaded_from_toml() -> None:
    profile = load_layer_stack_profile()

    assert profile.layer_stack is not None
    assert validate_loaded_layer_stack(profile) == ()
    assert [layer.name for layer in ordered_layer_definitions()] == [
        "infra",
        "decision",
        "needs",
        "kernel",
        "flow",
        "governance",
    ]


def test_profile_validator_passes_for_governance_domain_profiles() -> None:
    integrated_profile = _compose_governance_domain_profile()

    result = validate_profile(integrated_profile)

    assert result.passed is True, result.errors
