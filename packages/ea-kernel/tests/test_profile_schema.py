"""Tests for profile_schema — Profile introspection."""

from __future__ import annotations

import pytest

from ea_kernel.profile_types import KernelProfile, ProfileElement, ProfileRelation
from ea_kernel.types import KernelValidityRule
from ea_kernel.profile_schema import ProfileSchema


def _make_profile() -> KernelProfile:
    return KernelProfile(
        name="Test",
        version="1.0",
        kernel_version="2.5.0",
        elements=(
            ProfileElement("A1", "structure", "LayerA", "Cat1", "desc-a1"),
            ProfileElement("A2", "step", "LayerA", "Cat2"),
            ProfileElement("B1", "item", "LayerB", "Cat1"),
            ProfileElement("B2", "feature", "LayerB", "Cat2"),
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
                id="r2", source_pattern="A1", target_pattern="B1",
                relationship_name="rel2", valid=True, priority=50,
            ),
            KernelValidityRule(
                id="r3", source_pattern="*", target_pattern="*",
                relationship_name="rel1", valid=False, priority=1,
            ),
            KernelValidityRule(
                id="r4", source_pattern="#LayerA", target_pattern="#LayerB",
                relationship_name="rel1", valid=True, priority=30,
            ),
        ),
    )


class TestStructure:
    def test_layers(self):
        schema = ProfileSchema(_make_profile())
        assert schema.layers == ("LayerA", "LayerB")

    def test_categories(self):
        schema = ProfileSchema(_make_profile())
        assert schema.categories == ("Cat1", "Cat2")

    def test_kernel_types_used(self):
        schema = ProfileSchema(_make_profile())
        assert schema.kernel_types_used == ("feature", "item", "step", "structure")

    def test_kernel_relations_used(self):
        schema = ProfileSchema(_make_profile())
        assert schema.kernel_relations_used == ("association", "composition")


class TestPatternResolution:
    def test_wildcard(self):
        schema = ProfileSchema(_make_profile())
        assert len(schema.resolve_pattern("*")) == 4

    def test_category(self):
        schema = ProfileSchema(_make_profile())
        result = schema.resolve_pattern("@Cat1")
        assert {e.name for e in result} == {"A1", "B1"}

    def test_layer(self):
        schema = ProfileSchema(_make_profile())
        result = schema.resolve_pattern("#LayerA")
        assert {e.name for e in result} == {"A1", "A2"}

    def test_exact(self):
        schema = ProfileSchema(_make_profile())
        result = schema.resolve_pattern("A1")
        assert len(result) == 1
        assert result[0].name == "A1"

    def test_not_found(self):
        schema = ProfileSchema(_make_profile())
        assert schema.resolve_pattern("Nonexistent") == ()


class TestCoverage:
    def test_element_coverage(self):
        from ea_kernel.definition import KERNEL_SCHEMA
        schema = ProfileSchema(_make_profile())
        cov = schema.element_coverage(KERNEL_SCHEMA)
        assert 0.0 < cov <= 1.0

    def test_relation_coverage(self):
        from ea_kernel.definition import KERNEL_SCHEMA
        schema = ProfileSchema(_make_profile())
        cov = schema.relation_coverage(KERNEL_SCHEMA)
        assert 0.0 < cov <= 1.0


class TestRuleNavigation:
    def test_rules_for_relation(self):
        schema = ProfileSchema(_make_profile())
        rules = schema.rules_for_relation("rel1")
        assert len(rules) == 3  # r1, r3, r4

    def test_rules_for_relation_empty(self):
        schema = ProfileSchema(_make_profile())
        assert schema.rules_for_relation("nonexistent") == ()

    def test_rules_between_category(self):
        schema = ProfileSchema(_make_profile())
        rules = schema.rules_between("A1", "A2")
        # A1 is Cat1, A2 is Cat2 → r1 (@Cat1→@Cat2) matches
        # Also wildcard r3 matches, also r4 (#LayerA→#LayerB) doesn't match (both LayerA)
        rule_ids = {r.id for r in rules}
        assert "r1" in rule_ids
        assert "r3" in rule_ids

    def test_rules_between_exact(self):
        schema = ProfileSchema(_make_profile())
        rules = schema.rules_between("A1", "B1")
        rule_ids = {r.id for r in rules}
        assert "r2" in rule_ids  # exact match
        assert "r3" in rule_ids  # wildcard
        assert "r4" in rule_ids  # #LayerA → #LayerB

    def test_effective_rule(self):
        schema = ProfileSchema(_make_profile())
        rule = schema.effective_rule("A1", "A2", "rel1")
        assert rule is not None
        assert rule.id == "r1"  # priority 40 > priority 1 (r3)

    def test_effective_rule_not_found(self):
        schema = ProfileSchema(_make_profile())
        assert schema.effective_rule("A1", "A2", "nonexistent") is None


class TestBuiltinProfiles:
    @pytest.mark.parametrize("module_path,var_name", [
        ("ea_kernel.profiles.archimate", "ARCHIMATE_PROFILE"),
        ("ea_kernel.profiles.togaf", "TOGAF_PROFILE"),
        ("ea_kernel.profiles.zachman", "ZACHMAN_PROFILE"),
        ("ea_kernel.profiles.bpmn", "BPMN_PROFILE"),
        ("ea_kernel.profiles.sysml2", "SYSML2_PROFILE"),
    ])
    def test_schema_introspection(self, module_path, var_name):
        import importlib
        mod = importlib.import_module(module_path)
        profile = getattr(mod, var_name)
        schema = ProfileSchema(profile)
        assert len(schema.layers) > 0
        assert len(schema.categories) > 0
        assert len(schema.kernel_types_used) > 0
