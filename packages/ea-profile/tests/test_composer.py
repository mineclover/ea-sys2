"""Tests for profile composition: extend and subset."""

from __future__ import annotations

import pytest

from ea_profile.builder import ProfileBuilder
from ea_profile.composer import extend, subset
from ea_profile.types import (
    KernelProfile,
    ProfileElement,
    ProfileMetadata,
    ProfileRelation,
    ProfileRule,
)


def _make_profile(name="TestProfile", version="1.0") -> KernelProfile:
    """Build a test profile with elements, relations, and rules."""
    b = ProfileBuilder(name, version=version, kernel_version="1.0")
    b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
    b.element("ElemB", kernel_type="item", layer="Business", category="Structure")
    b.element("ElemC", kernel_type="step", layer="Application", category="Behavior")
    b.relation("Rel1", kernel_relation="association")
    b.relation("Rel2", kernel_relation="composition")
    b.allow("@Structure", "@Structure", "Rel1", priority=50, rule_id="r-01")
    b.deny("@Behavior", "@Structure", "Rel1", priority=40, rule_id="r-02")
    return b.build()


class TestExtend:
    """Tests for extend() function."""

    def test_extend_adds_new_elements(self):
        base = _make_profile()
        new_elem = ProfileElement(
            name="ElemD",
            kernel_type="structure",
            layer="Business",
            category="Structure",
        )
        extended = extend(
            base,
            name="Extended",
            version="2.0",
            add_elements=(new_elem,),
        )

        assert extended.name == "Extended"
        assert extended.version == "2.0"
        assert len(extended.elements) == 4
        assert extended.get_element("ElemD") == new_elem

    def test_extend_adds_new_relations(self):
        base = _make_profile()
        new_rel = ProfileRelation(
            name="Rel3",
            kernel_relation="dependency",
        )
        extended = extend(
            base,
            name="Extended",
            version="2.0",
            add_relations=(new_rel,),
        )

        assert len(extended.relations) == 3
        assert extended.get_relation("Rel3") == new_rel

    def test_extend_adds_new_rules(self):
        base = _make_profile()
        base_rule_count = len(base.validity_rules)
        new_rule = ProfileRule(
            id="r-03",
            source_pattern="*",
            target_pattern="*",
            relationship_name="Rel1",
            valid=True,
            priority=10,
        )
        extended = extend(
            base,
            name="Extended",
            version="2.0",
            add_rules=(new_rule,),
        )

        assert len(extended.validity_rules) == base_rule_count + 1
        rule_ids = {r.id for r in extended.validity_rules}
        assert "r-03" in rule_ids

    def test_extend_overrides_existing_rules_by_id(self):
        base = _make_profile()
        base_rule_count = len(base.validity_rules)
        override_rule = ProfileRule(
            id="r-01",
            source_pattern="*",
            target_pattern="*",
            relationship_name="Rel1",
            valid=False,
            priority=100,
            notes="Overridden rule",
        )
        extended = extend(
            base,
            name="Extended",
            version="2.0",
            override_rules=(override_rule,),
        )

        assert len(extended.validity_rules) == base_rule_count
        overridden = next(r for r in extended.validity_rules if r.id == "r-01")
        assert overridden.valid is False
        assert overridden.priority == 100
        assert overridden.notes == "Overridden rule"

    def test_extend_preserves_base_metadata_and_kernel_version(self):
        b = ProfileBuilder("Base", version="1.0", kernel_version="1.0")
        b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
        b.relation("Rel1", kernel_relation="association")
        b.allow("@Structure", "@Structure", "Rel1", priority=50, rule_id="r-01")
        base = b.build()

        metadata = ProfileMetadata(standard="Test Standard", organization="Test Org")
        base = KernelProfile(
            name=base.name,
            version=base.version,
            kernel_version="1.5.0",
            elements=base.elements,
            relations=base.relations,
            validity_rules=base.validity_rules,
            metadata=metadata,
        )

        extended = extend(
            base,
            name="Extended",
            version="2.0",
        )

        assert extended.kernel_version == "1.5.0"
        assert extended.metadata == metadata


class TestSubset:
    """Tests for subset() function."""

    def test_subset_filters_by_layers(self):
        base = _make_profile()
        sub = subset(
            base,
            name="BusinessOnly",
            version="1.0-subset",
            layers={"Business"},
        )

        assert len(sub.elements) == 2
        assert all(e.layer == "Business" for e in sub.elements)

    def test_subset_filters_by_categories(self):
        base = _make_profile()
        sub = subset(
            base,
            name="BehaviorOnly",
            version="1.0-subset",
            categories={"Behavior"},
        )

        assert len(sub.elements) == 1
        assert sub.elements[0].name == "ElemC"
        assert sub.elements[0].category == "Behavior"

    def test_subset_filters_by_relations_and_rules_follow(self):
        base = _make_profile()
        sub = subset(
            base,
            name="AssociationOnly",
            version="1.0-subset",
            relations={"Rel1"},
        )

        assert len(sub.relations) == 1
        assert sub.relations[0].name == "Rel1"

        # Rules should only include those referencing Rel1
        for rule in sub.validity_rules:
            assert rule.relationship_name == "Rel1"

    def test_subset_no_filters_returns_everything(self):
        base = _make_profile()
        sub = subset(
            base,
            name="FullCopy",
            version="1.0-copy",
        )

        assert len(sub.elements) == len(base.elements)
        assert len(sub.relations) == len(base.relations)
        assert len(sub.validity_rules) == len(base.validity_rules)

    def test_subset_preserves_metadata_and_kernel_version(self):
        base = _make_profile()
        metadata = ProfileMetadata(standard="Test", organization="Org")
        base = KernelProfile(
            name=base.name,
            version=base.version,
            kernel_version="2.0.0",
            elements=base.elements,
            relations=base.relations,
            validity_rules=base.validity_rules,
            metadata=metadata,
        )

        sub = subset(
            base,
            name="Subset",
            version="1.0-sub",
            layers={"Business"},
        )

        assert sub.kernel_version == "2.0.0"
        assert sub.metadata == metadata

    def test_subset_combined_layer_and_category_filters(self):
        base = _make_profile()
        sub = subset(
            base,
            name="BusinessStructure",
            version="1.0-subset",
            layers={"Business"},
            categories={"Structure"},
        )

        assert len(sub.elements) == 2
        assert all(e.layer == "Business" and e.category == "Structure" for e in sub.elements)
