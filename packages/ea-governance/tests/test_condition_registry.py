"""Tests for condition_registry.py — Governance condition vocabulary."""

from ea_governance.condition_registry import governance_condition_registry


class TestGovernanceConditionRegistry:
    """governance_condition_registry includes kernel defaults + governance conditions."""

    def test_includes_kernel_defaults(self):
        reg = governance_condition_registry()
        assert reg.resolve("LAYER_ORDER") == "layer_order"
        assert reg.resolve("SAME_LAYER") == "same_layer"
        assert reg.resolve("SAME_BRANCH") == "same_branch"
        assert reg.resolve("ANCESTOR_OF") == "ancestor_of"
        assert reg.resolve("SAME_CATEGORY") == "same_category"

    def test_governance_conditions(self):
        reg = governance_condition_registry()
        assert reg.resolve("SAME_LAYER") == "same_layer"
        assert reg.resolve("SAME_LIFECYCLE") == "same_lifecycle"
        assert reg.resolve("SAME_POLICY_SCOPE") == "same_policy_scope"
        assert reg.resolve("SAME_TRANSACTION") == "same_transaction"

    def test_unknown_returns_none(self):
        reg = governance_condition_registry()
        assert reg.resolve("NONEXISTENT") is None

    def test_total_condition_count(self):
        reg = governance_condition_registry()
        # 5 kernel defaults + 4 governance-specific (SAME_LAYER overlaps with kernel default)
        known = [
            "LAYER_ORDER", "SAME_LAYER", "SAME_BRANCH", "ANCESTOR_OF", "SAME_CATEGORY",
            "SAME_LIFECYCLE", "SAME_POLICY_SCOPE", "SAME_TRANSACTION",
        ]
        resolved = [k for k in known if reg.resolve(k) is not None]
        assert len(resolved) == 8
