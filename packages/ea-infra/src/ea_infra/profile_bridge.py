"""Infra-layer profile loading bridge (I3).

Provides convenience functions for loading infra-layer profiles from TOML.
All ea-profile imports are lazy (function-internal) following the same pattern.
"""

from __future__ import annotations

from pathlib import Path

from ea_infra.condition_registry import infra_condition_registry
from ea_infra.infra_schema import INFRA_SCHEMA


def load_infra_profile(path: Path, *, validate: bool = True):
    """Load an infra-layer profile from a TOML file.

    Args:
        path: Path to the TOML profile file.
        validate: If True, validate against INFRA_SCHEMA.

    Returns:
        KernelProfile instance.
    """
    from ea_profile.loader import load_profile

    schema = INFRA_SCHEMA if validate else None
    return load_profile(path, kernel=schema, condition_registry=infra_condition_registry())


def load_infra_profile_from_content(content: str, *, validate: bool = True):
    """Load an infra-layer profile from a TOML string.

    Args:
        content: TOML content string.
        validate: If True, validate against INFRA_SCHEMA.

    Returns:
        KernelProfile instance.
    """
    from ea_profile.loader import load_profile_from_content

    schema = INFRA_SCHEMA if validate else None
    return load_profile_from_content(content, schema, infra_condition_registry())
