"""SDLC symmetric layer stack metadata loader.

Loads ``00-layer-stack.toml`` and exposes layer metadata for SDLC-domain
tools that need explicit M1 layer structure decisions.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ea_profile.loader import load_profile
from ea_profile.profile_validator import validate_layer_stack
from ea_profile.types import KernelProfile, LayerDefinition, LayerStack

from ea_kernel.spec import KERNEL_SPEC

from . import PROFILE_DIR

LAYER_STACK_FILE = "00-layer-stack.toml"


class LayerStackProfileError(ValueError):
    """Raised when layer stack TOML metadata is missing or invalid."""

    def __init__(self, errors: tuple[str, ...]) -> None:
        self.errors = errors
        message = "; ".join(errors) if errors else "Layer stack profile validation failed."
        super().__init__(message)


def layer_stack_path() -> Path:
    """Return the path to ``00-layer-stack.toml``."""
    return PROFILE_DIR / LAYER_STACK_FILE


@lru_cache(maxsize=1)
def _cached_layer_stack_profile() -> KernelProfile:
    return load_profile(layer_stack_path(), KERNEL_SPEC)


def load_layer_stack_profile(*, validate: bool = True) -> KernelProfile:
    """Load the SDLC symmetric layer stack profile from TOML."""
    profile = _cached_layer_stack_profile()
    if not validate:
        return profile

    errors = validate_loaded_layer_stack(profile)
    if errors:
        raise LayerStackProfileError(errors)
    return profile


def load_layer_stack(*, validate: bool = True) -> LayerStack:
    """Return the ``layer_stack`` metadata from the loaded profile."""
    profile = load_layer_stack_profile(validate=validate)
    layer_stack = profile.layer_stack
    if layer_stack is None:
        raise LayerStackProfileError(
            ("Profile is missing required [layer_stack] metadata.",)
        )
    return layer_stack


def ordered_layer_definitions(*, validate: bool = True) -> tuple[LayerDefinition, ...]:
    """Return layer definitions sorted by order."""
    stack = load_layer_stack(validate=validate)
    return tuple(sorted(stack.layers, key=lambda layer: layer.order))


def validate_dependency_direction(layer_stack: LayerStack) -> tuple[str, ...]:
    """Validate that dependencies always point to lower-order layers."""
    order_by_name = {layer.name: layer.order for layer in layer_stack.layers}
    errors: list[str] = []
    for layer in layer_stack.layers:
        for dependency in layer.depends_on:
            dep_order = order_by_name.get(dependency)
            if dep_order is None:
                continue
            if dep_order >= layer.order:
                errors.append(
                    "Invalid layer dependency direction: "
                    f"'{layer.name}'(order={layer.order}) depends_on "
                    f"'{dependency}'(order={dep_order})."
                )
    return tuple(errors)


def validate_loaded_layer_stack(profile: KernelProfile) -> tuple[str, ...]:
    """Run static layer stack checks for a loaded profile."""
    if profile.layer_stack is None:
        return ("Profile is missing required [layer_stack] metadata.",)

    errors = list(validate_layer_stack(profile))
    errors.extend(validate_dependency_direction(profile.layer_stack))
    return tuple(errors)


__all__ = [
    "LAYER_STACK_FILE",
    "LayerStackProfileError",
    "layer_stack_path",
    "load_layer_stack_profile",
    "load_layer_stack",
    "ordered_layer_definitions",
    "validate_dependency_direction",
    "validate_loaded_layer_stack",
]
