"""Flow-layer condition vocabulary for profile rules.

Extends the kernel default conditions with flow-specific conditions.
Follows the same lazy import pattern as profile_bridge.py.
"""

from __future__ import annotations


def flow_condition_registry():
    """Create a ConditionRegistry with kernel defaults + flow conditions.

    Returns:
        ConditionRegistry with kernel defaults + 4 flow-specific conditions.
    """
    from ea_profile.types import ConditionRegistry

    reg = ConditionRegistry.kernel_default()
    reg.register("SAME_PLANE", "same_plane")
    reg.register("SAME_STEP_CATEGORY", "same_step_category")
    reg.register("SAME_WORKFLOW", "same_workflow")
    reg.register("SEQUENTIAL_ORDER", "sequential_order")
    return reg
