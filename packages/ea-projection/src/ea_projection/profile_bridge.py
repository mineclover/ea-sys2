"""Projection-layer profile loading bridge.

Provides convenience functions for loading projection-layer profiles from TOML.
All ea-profile imports are lazy (function-internal) following the same pattern.
"""

from __future__ import annotations

from pathlib import Path

from ea_projection.condition_registry import projection_condition_registry
from ea_projection.projection_schema import PROJECTION_SCHEMA


def load_projection_profile(path: Path, *, validate: bool = True):
    """Load a projection-layer profile from a TOML file.

    Args:
        path: Path to the TOML profile file.
        validate: If True, validate against PROJECTION_SCHEMA.

    Returns:
        KernelProfile instance.
    """
    from ea_profile.loader import load_profile

    schema = PROJECTION_SCHEMA if validate else None
    return load_profile(path, kernel=schema, condition_registry=projection_condition_registry())


def load_projection_profile_from_content(content: str, *, validate: bool = True):
    """Load a projection-layer profile from a TOML string.

    Args:
        content: TOML content string.
        validate: If True, validate against PROJECTION_SCHEMA.

    Returns:
        KernelProfile instance.
    """
    from ea_profile.loader import load_profile_from_content

    schema = PROJECTION_SCHEMA if validate else None
    return load_profile_from_content(content, schema, projection_condition_registry())
