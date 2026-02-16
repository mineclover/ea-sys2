"""Decision-layer condition vocabulary for profile rules.

Extends the kernel default conditions with decision-specific conditions.
Follows the same lazy import pattern as profile_bridge.py.
"""

from __future__ import annotations


def decision_condition_registry():
    """Create a ConditionRegistry with kernel defaults + decision conditions.

    Returns:
        ConditionRegistry with kernel defaults + 5 decision-specific conditions.
    """
    from ea_profile.types import ConditionRegistry

    reg = ConditionRegistry.kernel_default()
    reg.register("SAME_LIFECYCLE_STATE", "same_lifecycle_state")
    reg.register("SAME_DECISION_PATTERN", "same_decision_pattern")
    reg.register("SAME_TOPIC", "same_topic")
    reg.register("SAME_EVALUATION_DIMENSION", "same_evaluation_dimension")
    reg.register("SAME_COMPLEXITY", "same_complexity")
    return reg
