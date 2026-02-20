"""Tests for EA system layer stack TOML metadata."""

from ea_kernel.profiles.ea_sys.layer_stack import (
    load_layer_stack,
    load_layer_stack_profile,
    ordered_layer_definitions,
    validate_dependency_direction,
    validate_loaded_layer_stack,
)


def test_layer_stack_profile_loads_six_core_layers() -> None:
    profile = load_layer_stack_profile()

    assert profile.name == "EASystem-LayerStack"
    assert profile.layer_stack is not None
    assert profile.layer_stack.definition_flow
    assert profile.layer_stack.runtime_flow
    assert profile.layer_stack.feedback_flow

    layers = ordered_layer_definitions()
    assert [layer.name for layer in layers] == [
        "infra",
        "decision",
        "needs",
        "kernel",
        "flow",
        "governance",
    ]


def test_layer_stack_dependency_direction_is_valid() -> None:
    layer_stack = load_layer_stack()
    assert validate_dependency_direction(layer_stack) == ()


def test_layer_stack_has_no_cycle_and_passes_validator() -> None:
    profile = load_layer_stack_profile(validate=False)
    errors = validate_loaded_layer_stack(profile)

    assert errors == ()
    assert not any("cycle detected" in error for error in errors)
