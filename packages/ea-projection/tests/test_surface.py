"""Tests for surface.py — SurfaceRelationProfile formal types."""

from ea_projection.surface import DEFAULT_SURFACE_PROFILE, SurfaceRelationProfile


class TestSurfaceRelationProfile:

    def test_default_surface_relations(self):
        surface = DEFAULT_SURFACE_PROFILE.surface_relations
        assert len(surface) == 5
        assert set(surface) == {"contains", "depends_on", "next", "triggers", "constrains"}

    def test_is_surface_exposed_true(self):
        for rel in ("contains", "depends_on", "next", "triggers", "constrains"):
            assert DEFAULT_SURFACE_PROFILE.is_surface_exposed(rel) is True

    def test_is_surface_exposed_false(self):
        for rel in ("produces", "consumes", "coordinates", "registers", "available_in"):
            assert DEFAULT_SURFACE_PROFILE.is_surface_exposed(rel) is False

    def test_depth_axis_structural(self):
        for rel in ("contains", "depends_on", "next"):
            assert DEFAULT_SURFACE_PROFILE.depth_axis(rel) == "structural"

    def test_depth_axis_causal(self):
        for rel in ("triggers", "constrains"):
            assert DEFAULT_SURFACE_PROFILE.depth_axis(rel) == "causal"

    def test_depth_axis_operational(self):
        for rel in ("produces", "consumes", "coordinates"):
            assert DEFAULT_SURFACE_PROFILE.depth_axis(rel) == "operational"

    def test_depth_axis_self_description(self):
        for rel in ("registers", "available_in"):
            assert DEFAULT_SURFACE_PROFILE.depth_axis(rel) == "self_description"

    def test_depth_axis_inheritance_meta(self):
        for rel in ("specialization", "redefinition", "subsetting", "feature_typing"):
            assert DEFAULT_SURFACE_PROFILE.depth_axis(rel) == "inheritance_meta"

    def test_depth_axis_unknown(self):
        assert DEFAULT_SURFACE_PROFILE.depth_axis("nonexistent") == "unknown"

    def test_frozen_dataclass(self):
        profile = SurfaceRelationProfile(structural=("a",))
        try:
            profile.structural = ("b",)  # type: ignore[misc]
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass


class TestSurfaceDepthSemantic:

    def test_structural_contains_existence(self):
        assert DEFAULT_SURFACE_PROFILE.depth_semantic("contains") == "existence"

    def test_causal_triggers_execution(self):
        assert DEFAULT_SURFACE_PROFILE.depth_semantic("triggers") == "execution"

    def test_operational_produces_trace(self):
        assert DEFAULT_SURFACE_PROFILE.depth_semantic("produces") == "trace"

    def test_self_desc_registers_instance(self):
        assert DEFAULT_SURFACE_PROFILE.depth_semantic("registers") == "instance"

    def test_unknown_relation(self):
        assert DEFAULT_SURFACE_PROFILE.depth_semantic("nonexistent") == "unknown"
