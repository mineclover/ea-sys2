"""Tests for condition_registry.py — Needs condition vocabulary."""

from ea_needs.condition_registry import needs_condition_registry


class TestNeedsConditionRegistry:
    """needs_condition_registry includes kernel defaults + needs conditions."""

    def test_includes_kernel_defaults(self):
        reg = needs_condition_registry()
        assert reg.resolve("LAYER_ORDER") == "layer_order"
        assert reg.resolve("SAME_LAYER") == "same_layer"
        assert reg.resolve("SAME_BRANCH") == "same_branch"
        assert reg.resolve("ANCESTOR_OF") == "ancestor_of"
        assert reg.resolve("SAME_CATEGORY") == "same_category"

    def test_needs_conditions(self):
        reg = needs_condition_registry()
        assert reg.resolve("SAME_STATUS") == "same_status"
        assert reg.resolve("SAME_PRIORITY") == "same_priority"
        assert reg.resolve("SAME_USE_CASE") == "same_use_case"
        assert reg.resolve("SAME_STAKEHOLDER") == "same_stakeholder"

    def test_unknown_returns_none(self):
        reg = needs_condition_registry()
        assert reg.resolve("NONEXISTENT") is None

    def test_total_condition_count(self):
        reg = needs_condition_registry()
        # 5 kernel defaults + 4 needs-specific
        known = [
            "LAYER_ORDER", "SAME_LAYER", "SAME_BRANCH", "ANCESTOR_OF", "SAME_CATEGORY",
            "SAME_STATUS", "SAME_PRIORITY", "SAME_USE_CASE", "SAME_STAKEHOLDER",
        ]
        resolved = [k for k in known if reg.resolve(k) is not None]
        assert len(resolved) == 9
