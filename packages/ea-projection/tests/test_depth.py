"""Tests for depth.py — DepthLevel and DepthLevelRegistry formal types."""

from ea_projection.depth import (
    DepthLevel,
    DepthLevelRegistry,
    PROJECTION_BASE_VIEW_MODES,
    PROJECTION_FOCUS_MODES,
)


class TestDepthLevelRegistry:

    def test_depth_level_registry_keys(self):
        registry = DepthLevelRegistry.from_hardcoded()
        keys = registry.keys()
        assert len(keys) == 5
        assert set(keys) == {"l0", "l1", "l2", "l3", "l4"}

    def test_l0_panorama_spec(self):
        registry = DepthLevelRegistry.from_hardcoded()
        l0 = registry.get("l0")
        assert l0 is not None
        assert l0.lens == "panorama"
        assert l0.base_view_mode == "focus"
        assert l0.base_focus == "core"
        structural_causal = {"contains", "depends_on", "next", "triggers", "constrains"}
        assert l0.allowed_relations == frozenset(structural_causal)
        assert l0.max_edges == 180
        assert l0.next_levels == ("L1",)

    def test_l4_trace_spec(self):
        registry = DepthLevelRegistry.from_hardcoded()
        l4 = registry.get("l4")
        assert l4 is not None
        assert l4.lens == "trace"
        assert l4.base_view_mode == "summary"
        assert l4.next_levels == ()
        assert "produces" in l4.allowed_relations
        assert "consumes" in l4.allowed_relations
        assert "registers" in l4.allowed_relations
        assert "available_in" in l4.allowed_relations
        assert l4.max_edges == 980

    def test_depth_level_immutability(self):
        level = DepthLevel(
            key="test",
            lens="test_lens",
            description="test",
            base_view_mode="summary",
        )
        try:
            level.key = "modified"  # type: ignore[misc]
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass

    def test_get_unknown_level(self):
        registry = DepthLevelRegistry.from_hardcoded()
        assert registry.get("l99") is None

    def test_to_level_specs(self):
        registry = DepthLevelRegistry.from_hardcoded()
        specs = registry.to_level_specs()
        assert set(specs.keys()) == {"l0", "l1", "l2", "l3", "l4"}
        l0_spec = specs["l0"]
        assert l0_spec["level"] == "L0"
        assert l0_spec["lens"] == "panorama"
        assert isinstance(l0_spec["allowed_relations"], tuple)

    def test_base_view_modes(self):
        assert PROJECTION_BASE_VIEW_MODES == frozenset({"raw", "summary", "focus"})

    def test_focus_modes(self):
        assert "core" in PROJECTION_FOCUS_MODES
        assert "actor" in PROJECTION_FOCUS_MODES
        assert "topic" in PROJECTION_FOCUS_MODES
        assert "seed" in PROJECTION_FOCUS_MODES


class TestDepthLevelDEDS:

    def test_l0_depth_semantic(self):
        registry = DepthLevelRegistry.from_hardcoded()
        l0 = registry.get("l0")
        assert l0 is not None
        assert l0.depth_semantic == "existence"

    def test_l4_depth_semantic(self):
        registry = DepthLevelRegistry.from_hardcoded()
        l4 = registry.get("l4")
        assert l4 is not None
        assert l4.depth_semantic == "trace"

    def test_entry_question_non_empty(self):
        registry = DepthLevelRegistry.from_hardcoded()
        for key in registry.keys():
            level = registry.get(key)
            assert level is not None
            assert level.entry_question != ""

    def test_to_level_specs_includes_deds_fields(self):
        registry = DepthLevelRegistry.from_hardcoded()
        specs = registry.to_level_specs()
        l0_spec = specs["l0"]
        assert "depth_semantic" in l0_spec
        assert "entry_question" in l0_spec
        assert "entry_intent" in l0_spec
        assert l0_spec["depth_semantic"] == "existence"

    def test_backward_compat_deds_defaults(self):
        level = DepthLevel(
            key="test",
            lens="test_lens",
            description="test",
            base_view_mode="summary",
        )
        assert level.depth_semantic == ""
        assert level.entry_question == ""
        assert level.entry_intent == ""


class TestContainmentDepth:

    def test_l0_max_containment_depth_none(self):
        registry = DepthLevelRegistry.from_hardcoded()
        l0 = registry.get("l0")
        assert l0 is not None
        assert l0.max_containment_depth is None

    def test_l1_max_containment_depth_none(self):
        registry = DepthLevelRegistry.from_hardcoded()
        l1 = registry.get("l1")
        assert l1 is not None
        assert l1.max_containment_depth is None

    def test_l2_max_containment_depth_none(self):
        registry = DepthLevelRegistry.from_hardcoded()
        l2 = registry.get("l2")
        assert l2 is not None
        assert l2.max_containment_depth is None

    def test_l4_max_containment_depth_none(self):
        registry = DepthLevelRegistry.from_hardcoded()
        l4 = registry.get("l4")
        assert l4 is not None
        assert l4.max_containment_depth is None

    def test_to_level_specs_includes_max_containment_depth(self):
        registry = DepthLevelRegistry.from_hardcoded()
        specs = registry.to_level_specs()
        l0_spec = specs["l0"]
        assert "max_containment_depth" in l0_spec
        assert l0_spec["max_containment_depth"] is None
        l2_spec = specs["l2"]
        assert l2_spec["max_containment_depth"] is None

    def test_default_max_containment_depth_none(self):
        level = DepthLevel(
            key="test",
            lens="test_lens",
            description="test",
            base_view_mode="summary",
        )
        assert level.max_containment_depth is None
