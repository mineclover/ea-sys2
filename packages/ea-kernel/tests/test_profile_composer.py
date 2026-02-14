"""Tests for profile_composer — extend and subset operations."""

from __future__ import annotations

from ea_kernel.profile_composer import extend, subset
from ea_kernel.profile_types import KernelProfile, ProfileElement, ProfileRelation
from ea_kernel.types import KernelValidityRule


def _base_profile() -> KernelProfile:
    return KernelProfile(
        name="Base",
        version="1.0",
        kernel_version="2.5.0",
        elements=(
            ProfileElement("E1", "structure", "LayerA", "Cat1"),
            ProfileElement("E2", "step", "LayerA", "Cat2"),
            ProfileElement("E3", "item", "LayerB", "Cat1"),
        ),
        relations=(
            ProfileRelation("rel1", "association"),
            ProfileRelation("rel2", "composition"),
        ),
        validity_rules=(
            KernelValidityRule(
                id="r1", source_pattern="@Cat1", target_pattern="@Cat2",
                relationship_name="rel1", valid=True, priority=40,
            ),
            KernelValidityRule(
                id="r2", source_pattern="*", target_pattern="*",
                relationship_name="rel1", valid=False, priority=1,
            ),
            KernelValidityRule(
                id="r3", source_pattern="E1", target_pattern="E3",
                relationship_name="rel2", valid=True, priority=50,
            ),
        ),
    )


class TestExtend:
    def test_add_elements(self):
        base = _base_profile()
        ext = extend(
            base,
            name="Extended",
            version="2.0",
            add_elements=(ProfileElement("E4", "feature", "LayerC", "Cat3"),),
        )
        assert ext.name == "Extended"
        assert ext.version == "2.0"
        assert len(ext.elements) == 4
        assert ext.get_element("E4") is not None

    def test_add_relations(self):
        base = _base_profile()
        ext = extend(
            base,
            name="Extended",
            version="2.0",
            add_relations=(ProfileRelation("rel3", "specialization"),),
        )
        assert len(ext.relations) == 3

    def test_add_rules(self):
        base = _base_profile()
        new_rule = KernelValidityRule(
            id="r4", source_pattern="E4", target_pattern="E1",
            relationship_name="rel1", valid=True, priority=60,
        )
        ext = extend(
            base,
            name="Extended",
            version="2.0",
            add_rules=(new_rule,),
        )
        assert len(ext.validity_rules) == 4
        assert ext.validity_rules[-1].id == "r4"

    def test_override_rules(self):
        base = _base_profile()
        override = KernelValidityRule(
            id="r1", source_pattern="@Cat1", target_pattern="@Cat2",
            relationship_name="rel1", valid=False, priority=80,
        )
        ext = extend(
            base,
            name="Extended",
            version="2.0",
            override_rules=(override,),
        )
        assert len(ext.validity_rules) == 3  # same count
        r1 = next(r for r in ext.validity_rules if r.id == "r1")
        assert r1.valid is False
        assert r1.priority == 80

    def test_preserves_kernel_version(self):
        base = _base_profile()
        ext = extend(base, name="Ext", version="2.0")
        assert ext.kernel_version == base.kernel_version

    def test_preserves_metadata(self):
        from ea_kernel.profile_types import ProfileMetadata
        base = KernelProfile(
            name="Base",
            version="1.0",
            kernel_version="2.5.0",
            elements=(ProfileElement("E1", "structure", "L1", "C1"),),
            relations=(),
            metadata=ProfileMetadata("Std 1.0", "Org"),
        )
        ext = extend(base, name="Ext", version="2.0")
        assert ext.metadata == base.metadata


class TestSubset:
    def test_filter_by_layer(self):
        base = _base_profile()
        sub = subset(base, name="Sub", version="1.0", layers={"LayerA"})
        assert len(sub.elements) == 2
        assert all(e.layer == "LayerA" for e in sub.elements)

    def test_filter_by_category(self):
        base = _base_profile()
        sub = subset(base, name="Sub", version="1.0", categories={"Cat1"})
        assert len(sub.elements) == 2
        assert all(e.category == "Cat1" for e in sub.elements)

    def test_filter_by_layer_and_category(self):
        base = _base_profile()
        sub = subset(
            base, name="Sub", version="1.0",
            layers={"LayerA"}, categories={"Cat1"},
        )
        assert len(sub.elements) == 1
        assert sub.elements[0].name == "E1"

    def test_filter_by_relations(self):
        base = _base_profile()
        sub = subset(base, name="Sub", version="1.0", relations={"rel1"})
        assert len(sub.relations) == 1
        assert sub.relations[0].name == "rel1"
        # Rules for rel2 should be excluded
        rule_rels = {r.relationship_name for r in sub.validity_rules}
        assert "rel2" not in rule_rels
        assert "rel1" in rule_rels

    def test_no_filters_returns_full(self):
        base = _base_profile()
        sub = subset(base, name="Sub", version="1.0")
        assert len(sub.elements) == len(base.elements)
        assert len(sub.relations) == len(base.relations)
        assert len(sub.validity_rules) == len(base.validity_rules)

    def test_preserves_kernel_version(self):
        base = _base_profile()
        sub = subset(base, name="Sub", version="1.0", layers={"LayerA"})
        assert sub.kernel_version == base.kernel_version


class TestBuiltinComposition:
    def test_extend_archimate(self):
        from ea_kernel.profiles.archimate import ARCHIMATE_PROFILE
        ext = extend(
            ARCHIMATE_PROFILE,
            name="ArchiMate Extended",
            version="3.3",
            add_elements=(ProfileElement("CustomElement", "structure", "Extension", "Custom"),),
        )
        assert len(ext.elements) == len(ARCHIMATE_PROFILE.elements) + 1

    def test_subset_archimate_business(self):
        from ea_kernel.profiles.archimate import ARCHIMATE_PROFILE
        sub = subset(
            ARCHIMATE_PROFILE,
            name="ArchiMate Business",
            version="3.2-biz",
            layers={"Business"},
        )
        assert len(sub.elements) > 0
        assert all(e.layer == "Business" for e in sub.elements)
