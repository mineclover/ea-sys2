"""Tests for SDLC symmetric layer stack TOML metadata."""

from ea_kernel.profiles.sdlc.layer_stack import (
    load_layer_stack,
    load_layer_stack_profile,
    ordered_layer_definitions,
    validate_dependency_direction,
    validate_loaded_layer_stack,
)
from ea_profile.profile_validator import validate_profile


def test_sdlc_layer_stack_profile_loads_six_symmetric_layers() -> None:
    profile = load_layer_stack_profile()

    assert profile.name == "SDLC-Symmetric-LayerStack"
    assert profile.layer_stack is not None
    assert profile.layer_stack.definition_flow
    assert profile.layer_stack.runtime_flow
    assert profile.layer_stack.feedback_flow

    layers = ordered_layer_definitions()
    assert [layer.name for layer in layers] == [
        "DevInfra",
        "ArchDecision",
        "Requirements",
        "DomainModel",
        "Pipeline",
        "DevGovernance",
    ]


def test_sdlc_layer_stack_dependency_direction_is_valid() -> None:
    layer_stack = load_layer_stack()
    assert validate_dependency_direction(layer_stack) == ()


def test_sdlc_layer_stack_has_no_cycle_and_passes_validator() -> None:
    profile = load_layer_stack_profile(validate=False)
    errors = validate_loaded_layer_stack(profile)
    validation_result = validate_profile(profile)

    assert errors == ()
    assert not any("cycle detected" in error for error in errors)
    assert validation_result.passed is True, validation_result.errors
