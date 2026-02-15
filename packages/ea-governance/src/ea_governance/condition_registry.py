"""Governance-layer condition vocabulary for profile rules.

Extends the kernel default conditions with governance-specific conditions.
Follows the same lazy import pattern as profile_bridge.py.
"""

from __future__ import annotations


def governance_condition_registry():
    """Create a ConditionRegistry with kernel defaults + governance conditions.

    Returns:
        ConditionRegistry with kernel defaults + 4 governance-specific conditions.
    """
    from ea_profile.types import ConditionRegistry

    reg = ConditionRegistry.kernel_default()
    reg.register("SAME_LAYER", "same_layer")
    reg.register("SAME_LIFECYCLE", "same_lifecycle")
    reg.register("SAME_POLICY_SCOPE", "same_policy_scope")
    reg.register("SAME_TRANSACTION", "same_transaction")
    return reg
