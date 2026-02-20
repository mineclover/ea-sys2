"""Tests for SDLC native layer stack TOML metadata."""

from ea_kernel.profiles.ea_sys.layer_stack import load_layer_stack as load_governance_layer_stack
from ea_kernel.profiles.sdlc.layer_stack import (
    load_layer_stack_profile as load_sdlc_symmetric_layer_stack_profile,
)
from ea_kernel.profiles.sdlc.layer_stack import (
    validate_loaded_layer_stack as validate_sdlc_symmetric_loaded_layer_stack,
)
from ea_kernel.profiles.sdlc_native.layer_stack import (
    load_layer_stack,
    load_layer_stack_profile,
    ordered_layer_definitions,
    validate_dependency_direction,
    validate_loaded_layer_stack,
)
from ea_profile.profile_validator import validate_profile
from ea_profile.types import LayerStack


def _dependency_edges(layer_stack: LayerStack) -> set[tuple[str, str]]:
    return {
        (layer.name, dependency)
        for layer in layer_stack.layers
        for dependency in layer.depends_on
    }


def test_sdlc_native_layer_stack_profile_loads_native_layers() -> None:
    profile = load_layer_stack_profile()

    assert profile.name == "SDLC-Native-LayerStack"
    assert profile.layer_stack is not None
    assert profile.layer_stack.definition_flow
    assert profile.layer_stack.runtime_flow
    assert profile.layer_stack.feedback_flow

    layers = ordered_layer_definitions()
    assert [layer.name for layer in layers] == [
        "Planning",
        "Implementation",
        "Verification",
        "Deployment",
        "Monitoring",
    ]


def test_sdlc_native_layer_stack_differs_from_governance_domain_shape() -> None:
    native_stack = load_layer_stack()
    governance_stack = load_governance_layer_stack()

    assert len(native_stack.layers) != len(governance_stack.layers)
    assert _dependency_edges(native_stack) != _dependency_edges(governance_stack)


def test_sdlc_native_layer_stack_dependency_direction_is_valid() -> None:
    layer_stack = load_layer_stack()
    assert validate_dependency_direction(layer_stack) == ()


def test_both_sdlc_layer_stacks_are_valid_on_same_kernel_m2() -> None:
    symmetric_profile = load_sdlc_symmetric_layer_stack_profile(validate=False)
    native_profile = load_layer_stack_profile(validate=False)

    symmetric_result = validate_profile(symmetric_profile)
    native_result = validate_profile(native_profile)

    assert symmetric_result.passed is True, symmetric_result.errors
    assert native_result.passed is True, native_result.errors
    assert validate_sdlc_symmetric_loaded_layer_stack(symmetric_profile) == ()
    assert validate_loaded_layer_stack(native_profile) == ()
