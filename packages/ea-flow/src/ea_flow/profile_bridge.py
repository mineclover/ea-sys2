"""Flow-layer profile loading bridge (F3).

Provides convenience functions for loading flow-layer profiles from TOML.
All ea-profile imports are lazy (function-internal) following kernel_bridge.py pattern.
"""

from __future__ import annotations

from pathlib import Path

from ea_flow.condition_registry import flow_condition_registry
from ea_flow.flow_schema import FLOW_SCHEMA


def load_flow_profile(path: Path, *, validate: bool = True):
    """Load a flow-layer profile from a TOML file.

    Args:
        path: Path to the TOML profile file.
        validate: If True, validate against FLOW_SCHEMA.

    Returns:
        KernelProfile instance.
    """
    from ea_profile.loader import load_profile

    schema = FLOW_SCHEMA if validate else None
    return load_profile(path, kernel=schema, condition_registry=flow_condition_registry())


def load_flow_profile_from_content(content: str, *, validate: bool = True):
    """Load a flow-layer profile from a TOML string.

    Args:
        content: TOML content string.
        validate: If True, validate against FLOW_SCHEMA.

    Returns:
        KernelProfile instance.
    """
    from ea_profile.loader import load_profile_from_content

    schema = FLOW_SCHEMA if validate else None
    return load_profile_from_content(content, schema, flow_condition_registry())
