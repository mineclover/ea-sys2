"""Infra-layer condition vocabulary for profile rules.

Extends the kernel default conditions with infra-specific conditions.
Follows the same lazy import pattern as other layer bridges.
"""

from __future__ import annotations


def infra_condition_registry():
    """Create a ConditionRegistry with kernel defaults + infra conditions.

    Returns:
        ConditionRegistry with kernel defaults + 3 infra-specific conditions.
    """
    from ea_profile.types import ConditionRegistry

    reg = ConditionRegistry.kernel_default()
    reg.register("SAME_STORAGE_TIER", "same_storage_tier")
    reg.register("SAME_DATA_DOMAIN", "same_data_domain")
    reg.register("SAME_LIFECYCLE_PHASE", "same_lifecycle_phase")
    return reg
