"""Decision-layer profile loading bridge (D3).

Provides convenience functions for loading decision-layer profiles from TOML.
All ea-profile imports are lazy (function-internal) following kernel_bridge.py pattern.
"""

from __future__ import annotations

from pathlib import Path

from ea_decision.condition_registry import decision_condition_registry
from ea_decision.decision_schema import DECISION_SCHEMA


def load_decision_profile(path: Path, *, validate: bool = True):
    """Load a decision-layer profile from a TOML file.

    Args:
        path: Path to the TOML profile file.
        validate: If True, validate against DECISION_SCHEMA.

    Returns:
        KernelProfile instance.
    """
    from ea_profile.loader import load_profile

    schema = DECISION_SCHEMA if validate else None
    return load_profile(path, kernel=schema, condition_registry=decision_condition_registry())


def load_decision_profile_from_content(content: str, *, validate: bool = True):
    """Load a decision-layer profile from a TOML string.

    Args:
        content: TOML content string.
        validate: If True, validate against DECISION_SCHEMA.

    Returns:
        KernelProfile instance.
    """
    from ea_profile.loader import load_profile_from_content

    schema = DECISION_SCHEMA if validate else None
    return load_profile_from_content(content, schema, decision_condition_registry())
