"""Needs-layer condition vocabulary for profile rules.

Extends the kernel default conditions with needs-specific conditions.
Follows the same lazy import pattern as kernel_bridge.py.
"""

from __future__ import annotations


def needs_condition_registry():
    """Create a ConditionRegistry with kernel defaults + needs conditions.

    Returns:
        ConditionRegistry with kernel defaults + 4 needs-specific conditions.
    """
    from ea_profile.types import ConditionRegistry

    reg = ConditionRegistry.kernel_default()
    reg.register("SAME_STATUS", "same_status")
    reg.register("SAME_PRIORITY", "same_priority")
    reg.register("SAME_USE_CASE", "same_use_case")
    reg.register("SAME_STAKEHOLDER", "same_stakeholder")
    return reg
