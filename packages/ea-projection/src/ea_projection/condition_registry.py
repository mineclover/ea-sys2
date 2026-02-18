"""Projection-layer condition vocabulary for profile rules.

Extends the kernel default conditions with projection-specific conditions.
Follows the same lazy import pattern as other layer bridges.
"""

from __future__ import annotations


def projection_condition_registry():
    """Create a ConditionRegistry with kernel defaults + projection conditions.

    Returns:
        ConditionRegistry with kernel defaults + 3 projection-specific conditions.
    """
    from ea_profile.types import ConditionRegistry

    reg = ConditionRegistry.kernel_default()
    reg.register("SAME_PROJECTION_LEVEL", "same_projection_level")
    reg.register("SAME_LENS_TYPE", "same_lens_type")
    reg.register("SAME_VIEW_MODE", "same_view_mode")
    return reg
