"""Needs-layer profile loading bridge (N3).

Provides convenience functions for loading needs-layer profiles from TOML.
All ea-kernel imports are lazy (function-internal) following kernel_bridge.py pattern.
"""

from __future__ import annotations

from pathlib import Path

from ea_needs.condition_registry import needs_condition_registry
from ea_needs.needs_schema import NEEDS_SCHEMA


def load_needs_profile(path: Path, *, validate: bool = True):
    """Load a needs-layer profile from a TOML file.

    Args:
        path: Path to the TOML profile file.
        validate: If True, validate against NEEDS_SCHEMA.

    Returns:
        KernelProfile instance.
    """
    from ea_profile.loader import load_profile

    schema = NEEDS_SCHEMA if validate else None
    return load_profile(path, kernel=schema, condition_registry=needs_condition_registry())


def load_needs_profile_from_content(content: str, *, validate: bool = True):
    """Load a needs-layer profile from a TOML string.

    Args:
        content: TOML content string.
        validate: If True, validate against NEEDS_SCHEMA.

    Returns:
        KernelProfile instance.
    """
    from ea_profile.loader import load_profile_from_content

    schema = NEEDS_SCHEMA if validate else None
    return load_profile_from_content(content, schema, needs_condition_registry())
