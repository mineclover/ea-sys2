"""Governance-layer profile loading bridge.

Provides convenience functions for loading governance-layer profiles from TOML.
All ea-profile imports are lazy (function-internal) following the same pattern.
"""

from __future__ import annotations

from pathlib import Path

from ea_governance.condition_registry import governance_condition_registry
from ea_governance.governance_schema import GOVERNANCE_SCHEMA


def load_governance_profile(path: Path, *, validate: bool = True):
    """Load a governance-layer profile from a TOML file.

    Args:
        path: Path to the TOML profile file.
        validate: If True, validate against GOVERNANCE_SCHEMA.

    Returns:
        KernelProfile instance.
    """
    from ea_profile.loader import load_profile

    schema = GOVERNANCE_SCHEMA if validate else None
    return load_profile(path, kernel=schema, condition_registry=governance_condition_registry())


def load_governance_profile_from_content(content: str, *, validate: bool = True):
    """Load a governance-layer profile from a TOML string.

    Args:
        content: TOML content string.
        validate: If True, validate against GOVERNANCE_SCHEMA.

    Returns:
        KernelProfile instance.
    """
    from ea_profile.loader import load_profile_from_content

    schema = GOVERNANCE_SCHEMA if validate else None
    return load_profile_from_content(content, schema, governance_condition_registry())
